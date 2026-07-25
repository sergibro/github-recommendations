#!/usr/bin/env python3
"""Convert embedding pickles into Embedding Projector assets.

Reads pandas-DataFrame pickles (an `embeddings` column holding one vector per row;
every other column becomes metadata) and writes, for each pickle:

    <name>.bytes         raw little-endian float32, row-major, no header
    <name>_labels.tsv    header row + one row per point, same order as the tensor
    config.json          the projector manifest listing every tensor

No TensorFlow involved -- the projector is a client-side app, so these files can be
served by any static web server. See README.md in this directory.

Usage:
    python convert.py --src ./pickles --out /srv/tb/embeddings \
        --base-url https://tb-gh-recs.example.com
"""
import argparse
import glob
import json
import os

import numpy as np
import pandas as pd

EMB_COL = 'embeddings'


def cell(v):
    """Render one metadata value as a TSV cell (no tabs/newlines, NaN -> empty)."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ''
    return str(v).replace('\t', ' ').replace('\r', ' ').replace('\n', ' ')


def convert_one(path, out_dir, base_url):
    """Write the tensor and metadata for one pickle; return its config entry."""
    name = os.path.splitext(os.path.basename(path))[0]
    df = pd.read_pickle(path)
    if EMB_COL not in df:
        raise KeyError(f'{path}: no {EMB_COL!r} column')

    # Row order must match between the tensor and the metadata, so both are
    # written straight from the DataFrame without reindexing.
    X = np.vstack(df[EMB_COL].values).astype('<f4', copy=False)
    n, dim = X.shape
    with open(os.path.join(out_dir, f'{name}.bytes'), 'wb') as f:
        f.write(X.tobytes(order='C'))

    meta = df.drop(columns=[EMB_COL])
    with open(os.path.join(out_dir, f'{name}_labels.tsv'), 'w', encoding='utf-8') as f:
        f.write('\t'.join(meta.columns) + '\n')
        for row in meta.itertuples(index=False, name=None):
            f.write('\t'.join(cell(v) for v in row) + '\n')

    print(f'{name:24s} rows={n:6d} dim={dim} cols={list(meta.columns)}')
    # The projector resolves these paths against the *app* page, not against the
    # config URL, so they must be absolute whenever app and data differ in origin.
    prefix = f'{base_url}/' if base_url else ''
    return {
        'tensorName': name,
        'tensorShape': [n, dim],
        'tensorPath': f'{prefix}{name}.bytes',
        'metadataPath': f'{prefix}{name}_labels.tsv',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--src', required=True, help='directory containing *.pkl')
    p.add_argument('--out', required=True, help='directory to write the assets to')
    p.add_argument('--base-url', default='',
                   help='public URL the assets are served from; leave empty only if '
                        'the app is served from the same directory')
    p.add_argument('--order', default='',
                   help='comma-separated tensor names, to control the order they appear '
                        'in the projector (default: alphabetical)')
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)
    found = {os.path.splitext(os.path.basename(f))[0]: f
             for f in glob.glob(os.path.join(args.src, '*.pkl'))}
    if not found:
        raise SystemExit(f'no pickles found in {args.src}')

    names = [n.strip() for n in args.order.split(',') if n.strip()] if args.order else sorted(found)
    missing = [n for n in names if n not in found]
    if missing:
        raise SystemExit(f'--order names not found in {args.src}: {missing}')

    entries = [convert_one(found[n], args.out, args.base_url.rstrip('/')) for n in names]
    with open(os.path.join(args.out, 'config.json'), 'w', encoding='utf-8') as f:
        json.dump({'embeddings': entries}, f, indent=2)
    print(f'\nwrote {len(entries)} tensors + config.json to {args.out}')


if __name__ == '__main__':
    main()
