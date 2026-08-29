#!/usr/bin/env python3
"""Train baseline node2vec embeddings on the graph built by build_graph.py.

Users and repositories are embedded in one shared space -- they are nodes of the
same bipartite graph, and a walk alternates between them -- then split into two
pickles, in the shape `tb/serve/convert.py` expects: an `embeddings` column of
vectors plus one column per metadata field.

Usage:
    python embed.py --graph ~/data/gh-recs-v2/graph --out ~/data/gh-recs-v2/pickles
"""
import argparse
import os
import time

import duckdb
import numpy as np
import pandas as pd
from gensim.models import Word2Vec

from walk import Graph


def load_edges(graph_dir):
    """Read the core edge list and map both node kinds onto one integer space."""
    con = duckdb.connect()
    path = os.path.join(graph_dir, 'core_edges.parquet').replace("'", "''")
    df = con.execute(f"SELECT user, repo, weight FROM read_parquet('{path}')").df()

    users = pd.Index(df['user'].unique())
    repos = pd.Index(df['repo'].unique())
    # Users occupy [0, n_users), repositories the rest, so a vector can be traced
    # back to its side by its index alone.
    src = users.get_indexer(df['user']).astype(np.int64)
    dst = repos.get_indexer(df['repo']).astype(np.int64) + len(users)
    return users, repos, src, dst, df['weight'].to_numpy()


def write_corpus(graph, path, num_walks, walk_length, seed):
    """Write walks to a text file for gensim to stream.

    `corpus_file` rather than an in-memory list: gensim's iterable path holds the
    GIL while feeding workers, and materialising tens of millions of Python
    strings costs more memory than the model itself.
    """
    rng = np.random.default_rng(seed)
    n = 0
    with open(path, 'w') as f:
        for batch in graph.walks(num_walks, walk_length, rng):
            f.writelines(' '.join(map(str, row)) + '\n' for row in batch.tolist())
            n += len(batch)
            print(f'  {n:,} walks', flush=True)
    return n


def to_frame(names, offset, wv, meta, key):
    """Assemble one side's DataFrame: metadata columns plus an `embeddings` column.

    Nodes the model never saw (isolated in the core) are dropped rather than
    given a zero vector, which would pile them all onto one point.
    """
    have = [i for i, _ in enumerate(names) if str(i + offset) in wv]
    vecs = [wv[str(i + offset)] for i in have]
    df = pd.DataFrame({key: names[have]})
    df = df.merge(meta, on=key, how='left')
    df['embeddings'] = vecs
    return df


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--graph', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--dim', type=int, default=100,
                   help='v1 used 100, so the eras stay visually comparable')
    p.add_argument('--walks', type=int, default=10)
    p.add_argument('--length', type=int, default=80)
    p.add_argument('--window', type=int, default=10)
    p.add_argument('--epochs', type=int, default=5)
    p.add_argument('--workers', type=int, default=os.cpu_count())
    # The seed fixes the walks exactly. It does not make training reproducible:
    # gensim's workers consume the corpus in whatever order they get it, so
    # similarities move in the third decimal between runs. Neighbour sets are
    # stable; exact scores are not.
    p.add_argument('--seed', type=int, default=42)
    args = p.parse_args()

    graph_dir = os.path.expanduser(args.graph)
    out_dir = os.path.expanduser(args.out)
    os.makedirs(out_dir, exist_ok=True)

    users, repos, src, dst, weight = load_edges(graph_dir)
    print(f'{len(users):,} users + {len(repos):,} repos, {len(src):,} edges')
    g = Graph(src, dst, weight, len(users) + len(repos))

    corpus = os.path.join(out_dir, 'walks.txt')
    t = time.time()
    n_walks = write_corpus(g, corpus, args.walks, args.length, args.seed)
    print(f'{n_walks:,} walks in {time.time() - t:.0f}s -> {corpus}')

    t = time.time()
    model = Word2Vec(corpus_file=corpus, vector_size=args.dim, window=args.window,
                     min_count=0, sg=1, negative=5, sample=1e-4,
                     workers=args.workers, epochs=args.epochs, seed=args.seed)
    print(f'trained {len(model.wv):,} vectors in {time.time() - t:.0f}s')

    con = duckdb.connect()
    for names, offset, key, side in ((users, 0, 'login', 'users'),
                                     (repos, len(users), 'url', 'repos')):
        path = os.path.join(graph_dir, f'nodes_{side}.parquet').replace("'", "''")
        meta = con.execute(f"SELECT * FROM read_parquet('{path}')").df()
        # Repository attributes are not in the event stream any more, so if
        # enrich.py has fetched them, fold them in here. Left join: a repo the
        # API did not know still gets its vector, just with empty columns.
        extra = os.path.join(graph_dir, 'repo_meta.parquet')
        if side == 'repos' and os.path.exists(extra):
            m = pd.read_parquet(extra).rename(columns={'repo': key})
            m = m.drop(columns=[c for c in m.columns if c in meta.columns and c != key])
            meta = meta.merge(m, on=key, how='left')
            print(f'joined {len(m):,} rows of fetched metadata')
        df = to_frame(names, offset, model.wv, meta, key)
        name = f'{side}_{len(df) // 1000}k_v2'
        df.to_pickle(os.path.join(out_dir, f'{name}.pkl'))
        print(f'{name}: {len(df):,} rows, columns {[c for c in df.columns]}')

    os.remove(corpus)


if __name__ == '__main__':
    main()
