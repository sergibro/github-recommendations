#!/usr/bin/env python3
"""Build a bipartite user<->repo interaction graph from GH Archive events.

Reads the hourly `.json.gz` files fetched by `fetch.py` and writes:

    events.parquet    one row per kept interaction
    edges.parquet     one row per (user, repo) pair, with a weight
    nodes_*.parquet   surviving users and repos after thresholding, with metadata

Only the top-level `type` / `actor` / `repo` / `created_at` fields are read.
Event payloads are deliberately not parsed: as of 2026 GH Archive ships them
trimmed (a pull request's `base.repo` carries only id/name/url -- no language,
no timestamps, no star count), so there is nothing in them worth the parse cost.

Usage:
    python build_graph.py --raw ~/data/gh-recs-v2/raw --out ~/data/gh-recs-v2/graph
"""
import argparse
import os

import duckdb

# How much each event type says about a user caring for a repo. Stars and forks
# are the cleanest signal but, in the 2026 firehose, also the rarest; code
# contribution carries most of the weight simply because it is what is left.
WEIGHTS = {
    'WatchEvent': 4.0,             # a star
    'ForkEvent': 4.0,
    'PullRequestEvent': 3.0,
    'PullRequestReviewEvent': 3.0,
    'PullRequestReviewCommentEvent': 2.0,
    'IssuesEvent': 2.0,
    'IssueCommentEvent': 1.5,
    'CommitCommentEvent': 1.5,
    'PushEvent': 2.0,              # only kept when pushing to someone else's repo
    'ReleaseEvent': 1.0,
    'MemberEvent': 1.0,
}

# Automation, not people. `[bot]` is GitHub's own marker; the rest are prolific
# service accounts that would otherwise become the highest-degree nodes.
BOT_SQL = """
    actor_login NOT LIKE '%[bot]'
AND actor_login NOT LIKE '%-bot'
AND actor_login NOT LIKE 'bot-%'
AND actor_login NOT ILIKE '%noreply%'
AND actor_login NOT IN (
    'github-actions', 'dependabot', 'renovate', 'renovate-bot', 'greenkeeper',
    'codecov', 'snyk-bot', 'imgbot', 'allcontributors', 'web-flow',
    'pre-commit-ci', 'mergify', 'copybara-service', 'direwolf-github'
)
"""

def q(path):
    """Quote a path as a SQL literal (COPY ... TO does not take a parameter)."""
    return "'" + path.replace("'", "''") + "'"


def read_json(src):
    """A read_json() call that touches only the top-level fields we need."""
    return f"""
    read_json(
        {q(src)},
        columns = {{
            'type': 'VARCHAR',
            'created_at': 'TIMESTAMP',
            'actor': 'STRUCT(login VARCHAR)',
            'repo': 'STRUCT(id BIGINT, name VARCHAR)'
        }},
        format = 'newline_delimited',
        ignore_errors = true
    )
    """


def stage_events(con, raw_glob, out_dir):
    """Filter the firehose down to interactions that imply interest."""
    weights = ', '.join(f"('{k}', {v})" for k, v in WEIGHTS.items())
    con.execute(f"""
        COPY (
            WITH w(type, weight) AS (VALUES {weights}),
            raw AS (
                SELECT created_at AS ts,
                       type,
                       actor.login AS actor_login,
                       repo.id     AS repo_id,
                       repo.name   AS repo_name
                FROM {read_json(raw_glob)}
            )
            SELECT raw.ts, raw.type, raw.actor_login, raw.repo_id, raw.repo_name,
                   split_part(raw.repo_name, '/', 1) AS repo_owner, w.weight
            FROM raw JOIN w USING (type)
            WHERE raw.actor_login IS NOT NULL
              AND raw.repo_name IS NOT NULL
              AND {BOT_SQL}
              -- A push to one's own repository says nothing about shared
              -- interest; it is also the bulk of the 2026 firehose and the
              -- source of almost every degree-1 node.
              AND NOT (raw.type = 'PushEvent'
                       AND lower(split_part(raw.repo_name, '/', 1)) = lower(raw.actor_login))
        ) TO {q(os.path.join(out_dir, 'events.parquet'))} (FORMAT parquet, COMPRESSION zstd)
    """)


def build_edges(con, out_dir):
    """Collapse repeated interactions into one weighted edge per (user, repo)."""
    con.execute(f"""
        COPY (
            SELECT actor_login AS user,
                   repo_name   AS repo,
                   any_value(repo_id) AS repo_id,
                   count(*)           AS n_events,
                   count(DISTINCT type) AS n_kinds,
                   -- Repetition matters, but sub-linearly: 100 pushes is not
                   -- 100x the interest of one star.
                   sum(weight) ^ 0.5  AS weight,
                   max(type = 'WatchEvent' OR type = 'ForkEvent') AS starred_or_forked
            FROM read_parquet({q(os.path.join(out_dir, 'events.parquet'))})
            GROUP BY 1, 2
        ) TO {q(os.path.join(out_dir, 'edges.parquet'))} (FORMAT parquet, COMPRESSION zstd)
    """)


def prune(con, out_dir, k):
    """Reduce the graph to its k-core, writing core_edges.parquet.

    Dropping a low-degree node lowers its neighbours' degrees, so this has to
    repeat until nothing moves. The core is what node2vec can actually learn
    from: a user seen on a single repo contributes no co-occurrence, and a repo
    seen by a single user sits in no neighbourhood.
    """
    con.execute(f"""CREATE OR REPLACE TABLE core AS
                    SELECT * FROM read_parquet({q(os.path.join(out_dir, 'edges.parquet'))})""")
    for i in range(1, 101):
        before = con.execute('SELECT count(*) FROM core').fetchone()[0]
        con.execute(f"""CREATE OR REPLACE TABLE core AS SELECT * FROM core
            WHERE user IN (SELECT user FROM core GROUP BY 1 HAVING count(*) >= {k})
              AND repo IN (SELECT repo FROM core GROUP BY 1 HAVING count(*) >= {k})""")
        after = con.execute('SELECT count(*) FROM core').fetchone()[0]
        if after == before:
            break
    u, r = con.execute('SELECT count(DISTINCT user), count(DISTINCT repo) FROM core').fetchone()
    print(f'{k}-core after {i} passes: users {u:,}  repos {r:,}  edges {after:,}')
    con.execute(f"""COPY core TO {q(os.path.join(out_dir, 'core_edges.parquet'))}
                    (FORMAT parquet, COMPRESSION zstd)""")
    return u, r, after


def export_nodes(con, out_dir):
    """Write per-node metadata for the core, for use as projector labels.

    GH Archive's 2026 payloads are trimmed, so there is no language or repo
    creation date to be had here; everything below is derived from the events
    in the window itself.
    """
    events = q(os.path.join(out_dir, 'events.parquet'))
    counts = ', '.join(
        f"count(*) FILTER (type = '{t}') AS {name}"
        for t, name in (('WatchEvent', 'stars'), ('ForkEvent', 'forks'),
                        ('PullRequestEvent', 'prs'), ('IssuesEvent', 'issues'),
                        ('PushEvent', 'pushes')))
    for side, key, label in (('repo', 'repo_name', 'url'), ('user', 'actor_login', 'login')):
        other = 'actor_login' if side == 'repo' else 'repo_name'
        out = os.path.join(out_dir, f'nodes_{side}s.parquet')
        con.execute(f"""
            COPY (
                SELECT ev.{key} AS {label},
                       count(DISTINCT ev.{other}) AS degree,
                       count(*) AS events, {counts},
                       min(ev.ts)::DATE AS first_seen,
                       max(ev.ts)::DATE AS last_seen
                FROM read_parquet({events}) ev
                JOIN (SELECT DISTINCT {side} FROM core) c ON c.{side} = ev.{key}
                GROUP BY 1
            ) TO {q(out)} (FORMAT parquet, COMPRESSION zstd)
        """)
        print(f'wrote {os.path.basename(out)}')


def report(con, out_dir):
    edges = os.path.join(out_dir, 'edges.parquet')
    con.execute(f'CREATE OR REPLACE VIEW e AS SELECT * FROM read_parquet({q(edges)})')

    n_edges, n_users, n_repos = con.execute(
        'SELECT count(*), count(DISTINCT user), count(DISTINCT repo) FROM e').fetchone()
    print(f'edges {n_edges:,}   users {n_users:,}   repos {n_repos:,}\n')

    for side, other in (('user', 'repo'), ('repo', 'user')):
        print(f'--- degree of {side} (distinct {other}s) ---')
        rows = con.execute(f"""
            WITH d AS (SELECT {side} AS k, count(DISTINCT {other}) AS deg FROM e GROUP BY 1)
            SELECT deg_min, count(*) AS n
            FROM (SELECT CASE WHEN deg >= 100 THEN 100 WHEN deg >= 50 THEN 50
                              WHEN deg >= 20 THEN 20 WHEN deg >= 10 THEN 10
                              WHEN deg >= 5 THEN 5 WHEN deg >= 3 THEN 3
                              WHEN deg >= 2 THEN 2 ELSE 1 END AS deg_min FROM d)
            GROUP BY 1 ORDER BY 1
        """).fetchall()
        total = sum(n for _, n in rows)
        cum = total
        for deg_min, n in rows:
            print(f'  >={deg_min:4d}: {cum:8,} ({100 * cum / total:5.1f}%)')
            cum -= n
        print()


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--raw', required=True, help='directory of *.json.gz')
    p.add_argument('--out', required=True, help='directory for the parquet output')
    p.add_argument('--memory', default='24GB')
    p.add_argument('--k-core', type=int, default=2,
                   help='minimum degree on both sides after iterative pruning')
    p.add_argument('--skip-stage', action='store_true',
                   help='reuse an existing events.parquet')
    args = p.parse_args()

    raw = os.path.expanduser(args.raw)
    out = os.path.expanduser(args.out)
    os.makedirs(out, exist_ok=True)

    con = duckdb.connect()
    con.execute(f"SET memory_limit = '{args.memory}'")
    con.execute(f"SET temp_directory = '{os.path.join(out, 'tmp')}'")

    if not args.skip_stage:
        print('staging events ...', flush=True)
        stage_events(con, os.path.join(raw, '*.json.gz'), out)
    print('building edges ...', flush=True)
    build_edges(con, out)
    print()
    report(con, out)
    print(f'pruning to the {args.k_core}-core ...', flush=True)
    prune(con, out, args.k_core)
    export_nodes(con, out)


if __name__ == '__main__':
    main()
