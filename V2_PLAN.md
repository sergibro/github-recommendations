# v2 — modernization plan

Working document for the v2 line. Lives on `dev`. Written 2026-07-25.

Everything before it is preserved and immutable: `v1.0-ucu` (2019 university project),
`v1.1` (2020–2022 continuation), then untagged 2026 commits that restored the demo and
added `tb/serve/`. The Flask+Annoy nearest-neighbour service sits unmerged and unverified
on `legacy/flask-annoy-api`.

## Why v2 exists

Three things the v1 line depended on are dead or frozen:

| Layer | v1 | Status |
| --- | --- | --- |
| Data | GHTorrent MySQL dumps | Host does not resolve; domain resold. Unrecoverable. |
| Method | PyTorch-BigGraph | Archived by Meta in 2024. Transductive; needed only for billions of edges. |
| Viewer | TensorBoard 1.x projector | Frozen since 2019. Already replaced by static serving. |

## Fixed decisions

- **Source:** `data.gharchive.org` hourly `.json.gz`. Chosen over BigQuery specifically
  because it needs **no credentials** — BigQuery would require an interactive
  `gcloud auth login` that only the user can perform.
- **Processing:** DuckDB, locally. Reads gzipped JSON directly, no server.
- **Baseline method:** node2vec. The graph here is tens of thousands of nodes, so PBG's
  partitioning is unnecessary; the point of the baseline is comparability with v1.
- **Export + serving:** already built — `tb/serve/convert.py` and the three Caddy hosts.
  New tensors join the existing `config.json`, no new infrastructure.
- **Environment:** `uv` + `pyproject.toml`, Python 3.12/3.13.

## Environment constraints

- No sudo. `uv` installs to `~/.local/bin`; system python 3.14 has no `pip` and no
  `venv` module (`python3.14-venv` is not installed).
- Docker is available. The running `jup` container image
  (`quay.io/jupyter/pyspark-notebook`) has pandas 2.2.3 and is the fallback for
  anything pandas-shaped.
- 863 GB free on `/`.
- Old v1 pickles, for comparison:
  `/home/sbro/hetzner-opt-home/ucu/github-recommendations/tb/embeddings/`
- Live assets: `/srv/tb/embeddings` (data), `/srv/tb/{public,local}` (projector bundle).
- Work happens on `dev`. Nothing lands on `main` without asking.

## Milestones

### M1 — environment and graph

Install `uv`, create `pyproject.toml`, pull a bounded slice of GH Archive, build the
user↔repo edge list in DuckDB.

- Start with roughly a week of events, then decide whether to widen.
- Keep only interaction events that imply interest: star (`WatchEvent`), fork, PR, push.
- Filter to entities frequent enough to be meaningful, mirroring v1's `gte1k` / `gte500`
  thresholds, so the result is comparable to the old tensors.
- **Done when:** node and edge counts are reported, with the degree distribution and the
  chosen thresholds.

### M2 — baseline embeddings

Train node2vec on that graph; produce repo and user tensors as pandas pickles in the
same shape `convert.py` expects (an `embeddings` column plus metadata columns).

- Metadata for repos: full name, language, timestamps. For users: login, plus whatever
  the events carry.
- **Done when:** pickles exist and spot-checked nearest neighbours are sane — the v1
  README's own example is the reference: querying `apache/spark` should surface other
  Apache infrastructure projects.

### M3 — publish

Export with `tb/serve/convert.py`, add the new tensors to the live `config.json`
alongside the four v1 tensors, verify end to end.

- **Done when:** the public projector URL shows both eras, every asset returns 200 with
  CORS, and the old tensors still work.

### Later — not scoped yet

GraphSAGE with text features (inductive: new repos without a full retrain), possibly
LightGCN if the framing becomes recommendation rather than exploration; migrating the
viewer to Apple's Embedding Atlas for WebGPU-scale rendering; reviving the nearest
neighbour API on a modern stack (FastAPI + hnswlib/FAISS) from the legacy branch.

## Budget

The user's subscription usage is **not visible to me** — `/usage` is a client-side
command with no tool behind it. Pacing therefore works by checkpoint: stop at each
milestone, report, let the user check `/usage` and decide the next scope. As of
2026-07-25 the weekly allowance was at 50%, resetting Jul 28.
