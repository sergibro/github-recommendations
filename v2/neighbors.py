#!/usr/bin/env python3
"""Look up nearest neighbours in an embedding pickle, by cosine similarity.

The sanity check for a run: ask for a repository you know, and see whether its
neighbours are things a person would actually associate with it.

Usage:
    python neighbors.py --pkl ~/data/gh-recs-v2/pickles/repos_25k_v2.pkl \
        apache/spark pytorch/pytorch
"""
import argparse
import os

import numpy as np
import pandas as pd


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--pkl', required=True)
    p.add_argument('--key', default='', help='label column (default: first column)')
    p.add_argument('-k', type=int, default=10)
    p.add_argument('queries', nargs='+')
    args = p.parse_args()

    df = pd.read_pickle(os.path.expanduser(args.pkl))
    key = args.key or df.columns[0]
    labels = df[key].to_numpy()

    X = np.vstack(df['embeddings'].to_numpy()).astype(np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    index = {v: i for i, v in enumerate(labels)}

    for query in args.queries:
        i = index.get(query)
        if i is None:
            print(f'\n{query}: not in this tensor')
            continue
        sim = X @ X[i]
        top = np.argpartition(-sim, args.k + 1)[:args.k + 1]
        top = top[np.argsort(-sim[top])]
        print(f'\n{query}')
        for j in top:
            if j != i:
                print(f'  {sim[j]:.3f}  {labels[j]}')


if __name__ == '__main__':
    main()
