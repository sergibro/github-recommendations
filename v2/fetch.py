#!/usr/bin/env python3
"""Download a date range of GH Archive hourly files.

GH Archive publishes one gzipped JSON-lines file per hour at
https://data.gharchive.org/YYYY-MM-DD-H.json.gz (hour is *not* zero padded).
No credentials, no API limits -- it is a public bucket.

Files already present and readable are skipped, so an interrupted run resumes.

Usage:
    python fetch.py --start 2026-07-17 --end 2026-07-23 --out ~/data/gh-recs-v2/raw
"""
import argparse
import gzip
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

BASE = 'https://data.gharchive.org'

# The bucket sits behind Cloudflare, which answers 403 to the default
# `Python-urllib/x.y` User-Agent. Any identifying string is accepted.
_opener = urllib.request.build_opener()
_opener.addheaders = [
    ('User-Agent', 'gh-recs-v2/2.0 (+https://github.com/sergibro/github-recommendations)')
]
urllib.request.install_opener(_opener)


def hours(start, end):
    """Every hourly filename from start to end, both days included."""
    d = start
    while d <= end:
        for h in range(24):
            yield f'{d.isoformat()}-{h}.json.gz'
        d += timedelta(days=1)


def intact(path):
    """True if the file exists and gunzips to the end.

    Cheaper than re-downloading, and a truncated file from a killed run would
    otherwise poison every later query with a decompression error.
    """
    if not os.path.exists(path):
        return False
    try:
        with gzip.open(path, 'rb') as f:
            while f.read(1 << 20):
                pass
        return True
    except (OSError, EOFError):
        return False


def fetch(name, out_dir, retries=3):
    path = os.path.join(out_dir, name)
    if intact(path):
        return 'skip', name, os.path.getsize(path)
    tmp = path + '.part'
    for attempt in range(retries):
        try:
            urllib.request.urlretrieve(f'{BASE}/{name}', tmp)
            os.replace(tmp, path)
            return 'get', name, os.path.getsize(path)
        except (urllib.error.URLError, OSError) as e:
            if attempt == retries - 1:
                if os.path.exists(tmp):
                    os.remove(tmp)
                return 'fail', name, str(e)
    return 'fail', name, 'unreachable'


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--start', required=True, type=date.fromisoformat)
    p.add_argument('--end', required=True, type=date.fromisoformat)
    p.add_argument('--out', required=True)
    p.add_argument('--jobs', type=int, default=6)
    args = p.parse_args()

    out_dir = os.path.expanduser(args.out)
    os.makedirs(out_dir, exist_ok=True)
    names = list(hours(args.start, args.end))
    print(f'{len(names)} hourly files -> {out_dir}', flush=True)

    got = skipped = 0
    total = 0
    failures = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for i, (status, name, info) in enumerate(
                pool.map(lambda n: fetch(n, out_dir), names), 1):
            if status == 'fail':
                failures.append((name, info))
            else:
                total += info
                got += status == 'get'
                skipped += status == 'skip'
            if i % 24 == 0 or i == len(names):
                print(f'  {i}/{len(names)}  {total / 2**30:.2f} GiB', flush=True)

    print(f'\ndownloaded {got}, already present {skipped}, failed {len(failures)}')
    for name, why in failures:
        print(f'  FAIL {name}: {why}', file=sys.stderr)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
