#!/usr/bin/env python3
"""Weighted random walks over a bipartite user<->repo graph.

The walks are generated with numpy rather than by a node2vec library. pecanpy,
the fast option, pins numba 0.53 and will not build past Python 3.9; the pure
Python implementations are far too slow at this size. With p = q = 1 -- which is
what a baseline wants -- walks are first order, and a first-order weighted walk
vectorises cleanly: every walk takes its next step in the same numpy operation.
"""
import numpy as np


class Graph:
    """An undirected weighted graph in CSR form, built from an edge list."""

    def __init__(self, src, dst, weight, n_nodes):
        # Each edge is stored in both directions, so a walk can cross it either way.
        u = np.concatenate([src, dst])
        v = np.concatenate([dst, src])
        w = np.concatenate([weight, weight]).astype(np.float64)

        order = np.argsort(u, kind='stable')
        self.indices = v[order].astype(np.int32)
        self.n = n_nodes
        self.indptr = np.zeros(n_nodes + 1, dtype=np.int64)
        np.add.at(self.indptr, u + 1, 1)
        np.cumsum(self.indptr, out=self.indptr)

        # One global running sum over the neighbour weights. Because every weight
        # is positive it is sorted ascending, so a single searchsorted picks a
        # neighbour of *any* node: offset into the node's slice, then look up.
        self.cumw = np.cumsum(w[order])
        self.cum0 = np.concatenate([[0.0], self.cumw])

    def degree(self):
        return np.diff(self.indptr)

    def step(self, nodes, rng):
        """One weighted step from each node in `nodes` (vectorised)."""
        lo = self.indptr[nodes]
        hi = self.indptr[nodes + 1]
        base = self.cum0[lo]
        total = self.cum0[hi] - base
        target = base + rng.random(nodes.shape) * total
        idx = np.searchsorted(self.cumw, target, side='right')
        # Guard the slice bounds: floating point can put the target a hair past
        # the end of the run, which would step to an unrelated node's neighbour.
        np.clip(idx, lo, hi - 1, out=idx)
        return self.indices[idx]

    def walks(self, num_walks, walk_length, rng):
        """Yield `num_walks` batches, each one walk from every node.

        Isolated nodes (degree 0) are skipped rather than emitted as a walk of
        length one, which would only teach the model that they exist.
        """
        starts = np.flatnonzero(self.degree() > 0).astype(np.int32)
        for _ in range(num_walks):
            rng.shuffle(starts)
            walk = np.empty((starts.size, walk_length), dtype=np.int32)
            walk[:, 0] = starts
            for t in range(1, walk_length):
                walk[:, t] = self.step(walk[:, t - 1], rng)
            yield walk
