#!/usr/bin/env python3
"""Fetch repository metadata from ecosyste.ms for the nodes of the graph.

GH Archive stopped carrying repository attributes when GitHub trimmed event
payloads (announced 2025-08-08, live 2025-10-07), so `language`, `created_at`
and star counts have to come from somewhere else. ecosyste.ms serves all of them
without a key, which is why it is preferred here over the GitHub API (needs a
token) and over deps.dev (which has stars and forks but no language, no
`created_at` and no topics).

Writes one Parquet file. Re-running skips repositories already fetched, so an
interrupted run resumes and a rate-limit stop is not a disaster.

Usage:
    python enrich.py --graph ~/data/gh-recs-v2/graph --out ~/data/gh-recs-v2/graph/repo_meta.parquet
"""
import argparse
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import duckdb
import pandas as pd

API = 'https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/'
UA = 'gh-recs-v2/2.0 (+https://github.com/sergibro/github-recommendations)'

# What we keep. `language` and `created_at` are the two the v1 tensors had and
# the v2 ones lack; the rest is cheap to carry and useful for colouring.
FIELDS = ('language', 'created_at', 'updated_at', 'pushed_at', 'stargazers_count',
          'forks_count', 'open_issues_count', 'size', 'license', 'archived',
          'fork', 'description', 'topics')

_lock = threading.Lock()
_state = {'done': 0, 'found': 0, 'missing': 0, 'failed': 0}


def fetch(repo, retries=4):
    """One repository. Returns a dict, or None if the API does not know it."""
    url = API + urllib.parse.quote(repo, safe='')
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            row = {'repo': repo}
            for f in FIELDS:
                v = d.get(f)
                # topics is a list; flatten so the frame stays rectangular.
                row[f] = ' '.join(v) if isinstance(v, list) else v
            return row
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            # 429 and 5xx are worth waiting out; back off and try again.
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt * 5)
                continue
            return None
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            return None
    return None


def run(repo, total):
    row = fetch(repo)
    with _lock:
        _state['done'] += 1
        _state['found' if row else 'missing'] += 1
        if _state['done'] % 500 == 0:
            s = _state
            print(f"  {s['done']:,}/{total:,}  found {s['found']:,}  "
                  f"missing {s['missing']:,}", flush=True)
    return row


# Columns of the Hugging Face `ibragim-bad/github-repos-metadata-40M` dump, mapped
# onto ours. It is a static snapshot (through 2025-07-23) and so covers less than
# the live API, but it is not a subset of it: it holds repositories ecosyste.ms
# never indexed, so it is worth using to fill the gaps rather than as a source.
FILL_MAP = {'repo_name': 'repo', 'language': 'language', 'created_at': 'created_at',
            'description': 'description', 'license_key': 'license',
            'forks_count': 'forks_count', 'watchers_count': 'stargazers_count',
            'size': 'size'}


def fill_from(df, path, repos):
    """Add rows for repositories the API did not know, from a local parquet."""
    con = duckdb.connect()
    cols = ', '.join(f'{src} AS {dst}' for src, dst in FILL_MAP.items())
    glob = os.path.join(os.path.expanduser(path), '*.parquet').replace("'", "''")
    extra = con.execute(f"SELECT {cols} FROM read_parquet('{glob}')").df()

    known = set(df['repo'].str.lower()) if len(df) else set()
    wanted = {r.lower(): r for r in repos if r.lower() not in known}
    extra['_k'] = extra['repo'].str.lower()
    extra = extra[extra['_k'].isin(wanted)].drop_duplicates('_k')
    # Keep the graph's own spelling of the name, not the dump's.
    extra['repo'] = extra['_k'].map(wanted)
    extra = extra.drop(columns=['_k'])
    print(f'filled {len(extra):,} repositories the API did not have')
    return pd.concat([df, extra], ignore_index=True) if len(df) else extra


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--graph', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--fill-from', default='',
                   help='directory of parquet shards of the Hugging Face metadata '
                        'dump, used only for repositories the API did not return')
    p.add_argument('--jobs', type=int, default=4,
                   help='kept low on purpose: the API is free and unmetered, '
                        'and there is no reason to be the one who ruins that')
    args = p.parse_args()

    graph = os.path.expanduser(args.graph)
    out = os.path.expanduser(args.out)

    con = duckdb.connect()
    core = os.path.join(graph, 'core_edges.parquet').replace("'", "''")
    repos = [r[0] for r in con.execute(
        f"SELECT DISTINCT repo FROM read_parquet('{core}') ORDER BY 1").fetchall()]

    have = pd.DataFrame()
    if os.path.exists(out):
        have = pd.read_parquet(out)
        done = set(have['repo'])
        repos = [r for r in repos if r not in done]
        print(f'{len(have):,} already fetched, {len(repos):,} to go')

    if repos:
        t = time.time()
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            rows = list(pool.map(lambda r: run(r, len(repos)), repos))
        rows = [r for r in rows if r]
        print(f'\nfetched {len(rows):,} in {time.time() - t:.0f}s '
              f'({_state["missing"]:,} not indexed)')
        df = pd.concat([have, pd.DataFrame(rows)], ignore_index=True) if len(have) else pd.DataFrame(rows)
    else:
        df = have

    all_repos = [r[0] for r in con.execute(
        f"SELECT DISTINCT repo FROM read_parquet('{core}')").fetchall()]
    if args.fill_from:
        df = fill_from(df, args.fill_from, all_repos)
    df.to_parquet(out, index=False)

    total = con.execute(f"SELECT count(DISTINCT repo) FROM read_parquet('{core}')").fetchone()[0]
    print(f'\n{len(df):,} / {total:,} repositories = {100 * len(df) / total:.1f}% covered')
    for col in ('language', 'created_at', 'stargazers_count', 'topics'):
        if col in df:
            n = df[col].replace('', None).notna().sum()
            print(f'  {col:20s} present for {n:,} ({100 * n / len(df):.1f}%)')


if __name__ == '__main__':
    main()
