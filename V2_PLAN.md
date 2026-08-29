# v2 — modernization plan

Working document for the v2 line. Lives on `dev`. Written 2026-07-25, last updated 2026-08-28.

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

- No sudo. `uv` (0.11.32, in `~/.local/bin`) builds its own venvs and does not need the
  missing `pip` / `venv` modules of the system python 3.14. `v2/pyproject.toml` pins
  `>=3.12,<3.14`, because gensim has no 3.14 wheels yet; uv downloads a managed 3.13.
- Data lives outside the repo, in `~/data/gh-recs-v2/` (`raw/` hourly archives,
  `graph/` parquet). 62 GB RAM, 12 cores; 460 GB free as of 2026-07-25, after the
  47 GiB of archives had landed.
- GH Archive answers **403 to the default `Python-urllib` User-Agent**; `fetch.py`
  sets its own.
- Docker is available. The running `jup` container image
  (`quay.io/jupyter/pyspark-notebook`) has pandas 2.2.3 and is the fallback for
  anything pandas-shaped.
- Old v1 pickles, for comparison:
  `/home/sbro/hetzner-opt-home/ucu/github-recommendations/tb/embeddings/`
- Live assets: `/srv/tb/embeddings` (data), `/srv/tb/{public,local}` (projector bundle).
- Work happens on `dev`. Nothing lands on `main` without asking.

## What the 2026 firehose actually looks like

Measured on the fetched data, not assumed. Three findings that reshaped M1:

**Payloads are trimmed.** A `PullRequestEvent`'s `payload.pull_request.base.repo`
carries only `id`, `name` and `url` — no `language`, no `created_at`, no
`stargazers_count`. Nothing else carries them either. So the v1 metadata columns
(`language`, repo timestamps, user `location` / `country_code`, which came from
GHTorrent's user and project tables) **cannot be reproduced from GH Archive at all.**
v2 metadata is therefore derived from the events in the window: degree, event counts
by type, first/last seen. Adding `language` back would need the GitHub REST API and a
token — deferred, and it is a per-repo request, so it only makes sense for the core.

**The event mix has collapsed towards pushes.** Sampling one hour per day across a
week, 1.14M events:

| share | event |
| --- | --- |
| 88.5% | PushEvent |
| 6.5% | CreateEvent |
| 3.3% | DeleteEvent |
| 0.7% | PullRequestEvent |
| **0.2%** | **WatchEvent** (a star) |
| 0.03% | ForkEvent |

In the 2019 data v1 was built on, stars were a large fraction of the stream. At ~250
stars/hour they can no longer carry the graph, so v2 weights code contribution
heavily — not because it is the better signal, but because it is what still exists.

**Correction, established 2026-08-28.** The paragraph above describes what GH Archive
*delivers*, and it was wrong to present that as what GitHub *emits*. Three separate
causes, only one of which is GitHub policy:

1. **Payload trimming — official and deliberate.** Announced 2025-08-08, brownout
   2025-09-08, rolled out 2025-10-07: GitHub removed fields from pull request and push
   events that "are slow to generate and require costly database calls." This is the
   real, permanent explanation for the missing `language` / `created_at` above.
2. **A caching bug on GitHub's side.** Daily events fell from 2,769,429 on 2025-10-08 to
   18,906 on 2025-10-09. GitHub Support confirmed it: "recent changes did introduce a
   cache for event data, which unexpectedly led to some users seeing 'stale' events."
   Volume partly recovered from 2025-10-14 but never to the old baseline.
3. **A bug in GH Archive's own crawler.** It fetches a single page of `/events` per
   cycle where the API offers up to 300 events over 100-per-page pages, so it captures
   roughly a third to a fifth of what is available. The fix has sat in an unmerged pull
   request since **2026-02-19** on a project its own contributors now describe as
   unmaintained.

Separately, the collapse specific to `WatchEvent` (90–100% capture until 2025-06, 10–20%
from 2026-02) has **no published explanation** from GitHub or anyone else.

So the graph in M1 rests on systematically undercounted data. That is a property of the
source, not of our pipeline, and it means the event mix above should be read as a lower
bound. See `docs/data-sources.md`.

**Most push volume is noise.** In one hour, `github-actions[bot]` alone accounted for
20k of 150k pushes, and 25,537 of 36,006 pushing accounts pushed exactly once. Two
filters do most of the cleaning: drop bot logins, and drop pushes to the actor's *own*
repository — those imply no shared interest and produce nearly every degree-1 node.

**Consequence for the window.** One week (168 hours, 3.3 GiB) yields 355k edges but a
2-core of only 4.2k users / 4.3k repos, against v1's 25k repos / 73k users; the 3-core
collapses to 114 users. The window was therefore widened to ~12 weeks
(2026-05-01 … 2026-07-23). The core grows faster than linearly with the window, since
co-occurrence needs two interactions to fall inside the same window.

## Milestones

### M1 — environment and graph

Install `uv`, create `pyproject.toml`, pull a bounded slice of GH Archive, build the
user↔repo edge list in DuckDB.

Scripts: `v2/fetch.py` (download), `v2/build_graph.py` (stage → edges → k-core → nodes).

- Keep only interaction events that imply interest, weighted by how much they imply it;
  drop bots and own-repo pushes (see the section above).
- v1's `gte1k` / `gte500` thresholds were star counts accumulated over years and have no
  meaning in a 12-week window. The equivalent here is an **iterative k-core**: prune
  until every user has ≥k repos and every repo ≥k users. That is the threshold that
  matters for node2vec, since below it there is no co-occurrence to learn from.
- **Done when:** node and edge counts are reported, with the degree distribution and the
  chosen k.

**Done.** 2026-05-01 … 2026-07-23, 2016 hourly files, 47 GiB, no gaps. After filtering:
5,728,298 edges over 2.81M users and 3.41M repos. Cores:

| k | users | repos | edges |
| --- | --- | --- | --- |
| 2 | 400,230 | 298,221 | 1,464,681 |
| 3 | 120,901 | 69,564 | 643,200 |
| **4** | **50,582** | **25,905** | **346,460** |
| 5 | 24,705 | 12,154 | 204,556 |
| 6 | 13,241 | 6,577 | 126,495 |

**k = 4 is the published core**, because it lands almost exactly on v1's dimensions
(25,905 repos against v1's 24,963) — the two eras are then the same size in the
projector and can be compared without arguing about scale. 99.7% of its edges point at
a repository the user does not own.

### M2 — baseline embeddings

Train node2vec on that graph; produce repo and user tensors as pandas pickles in the
same shape `convert.py` expects (an `embeddings` column plus metadata columns).

- Metadata is whatever the window yields: degree, per-type event counts, first/last seen.
  Language and repo timestamps are not available (see above).
- **Done when:** pickles exist and spot-checked nearest neighbours are sane — the v1
  README's own example is the reference: querying `apache/spark` should surface other
  Apache infrastructure projects.

**Done.** `walk.py` + `embed.py`: 764,870 walks of length 80 in 19s, skip-gram over them
in 478s on 12 cores, 100 dimensions to match v1. `apache/spark` returns
`apache/parquet-java`, `apache/spark-docker`, `apache/iceberg-cpp`, `apache/hadoop`,
`apache/gluten` — the reference example reproduces.

One caveat worth keeping in view. Because the graph is now contribution-driven rather
than star-driven, part of what it learns is *who works together* rather than *what is
worth looking at next*: for 23.5% of repositories all five nearest neighbours share the
same owner. It is not the whole picture — 57.7% have no same-owner repo in their top
five, and cross-organisation neighbourhoods are clearly thematic (`duckdb/duckdb` →
`apache/iceberg-rust`, `Eventual-Inc/Daft`, `trinodb/trino`, `ray-project/ray`) — but
large monorepo organisations do collapse into tight same-owner balls. Weighting stars
and forks higher cannot fix this while stars are 0.2% of the stream; a co-occurrence
prior that discounts same-owner edges would be the thing to try.

### M3 — publish

Export with `tb/serve/convert.py`, add the new tensors to the live `config.json`
alongside the four v1 tensors, verify end to end.

- **Done when:** the public projector URL shows both eras, every asset returns 200 with
  CORS, and the old tensors still work.

**On the private host, deliberately not public yet.** Running `convert.py` over all six
pickles at once regenerates the four v1 tensors **byte-identically** to what is live —
the proof that the export path is reproducible and that publishing cannot corrupt v1.

The v2 assets went to `/srv/tb/local/`, not `/srv/tb/embeddings/`. That distinction is
the whole point: `/srv/tb/embeddings` is the *public* data host, so anything placed
there is world-readable regardless of which front end links it. `/srv/tb/local` is
behind `basic_auth`, and since the projector bundle is served from the same host, the
page and its tensors share an origin and need no CORS.

    https://tb-local.hel.sergibro.me/

The bundle in `/srv/tb/local` has its baked-in default config path repointed at
`config_all.json`, so the bare URL is enough; `?config=` still overrides it. That bundle
also takes `?tsne=`, `?umap=`, `?pca=` and `?pcadim=` (see `tb/serve/README.md`). The
public bundle in `/srv/tb/public` is untouched: public manifest, stock sample sizes.

`config_all.json` lists all six tensors, `repos_25k_v2` first: the two v2 ones point at
`tb-local`, the four v1 ones stay on the public data host, which its `*` CORS header
allows the private page to fetch. Verified: v2 returns 401 unauthenticated and 404 on
the public host, every v1 asset still returns 200 with CORS, and the public
`config.json` still lists exactly the original four.

To publish later: copy the four `*_v2.*` files into `/srv/tb/embeddings/`, regenerate
`config.json` there with `--base-url https://tb-gh-recs.hel.sergibro.me`, and update the
README link.

### M4 — metadata recovered

**Done 2026-08-29.** GitHub's payload trim removed `language` and `created_at` from the
event stream, so they were fetched separately — `v2/enrich.py`, against ecosyste.ms, no
credentials. Coverage of the core: **24,368 of 25,905 (94.1%)**, with `created_at` for
99.6%, star counts for 99.9%, `language` for 94.2% and `topics` for 56.4%. `embed.py`
left-joins the result, so the repository tensor now carries 23 metadata columns instead of
nine and `language` is a colouring dimension again, as it was in v1.

Two things learned the hard way, both recorded in `docs/data-sources.md`: sustained
throughput bears no relation to single-request latency (0.15 s per lookup implied 15
minutes; the run took 4 hours), and a second pass over the misses recovered 1,348 of
3,031 — much of "not indexed" was transient refusal.

### Next — decided, not started

Four candidates, in no fixed order:

- **A three-dimensional tensor.** Compute UMAP offline into 3 dimensions and publish it as
  an ordinary extra tensor. The projector's PCA view of 3-dimensional data is just a
  rotation of coordinates that are already correct, so it renders instantly, shows every
  point with no sampling, and keeps full 3D orbit. This is the cheapest real improvement
  available: no new viewer, no new infrastructure, no change to `convert.py`. See
  `docs/viewers.md` for why replacing the viewer is the wrong move.
- **An honest comparison of eras.** 35 monthly GHTorrent MySQL dumps survive on
  archive.org (2013-10 to 2018-03, verified downloadable; see `docs/data-sources.md`).
  Building a 2018 graph with this same pipeline would compare v1's era against v2's on
  data of equal quality, instead of comparing a healthy snapshot against a degraded one.
  ~71 GB for one month.
- **A penalty on same-owner edges.** For 23.5% of repositories all five nearest neighbours
  share an owner, because a contribution-driven graph partly learns who works together
  rather than what is worth looking at. Discounting co-occurrence inside one organisation
  is the obvious thing to try; weighting stars higher cannot work while they are 0.2% of
  the stream.
- **A wider window.** `open-index/open-github` mirrors the whole event stream as Parquet,
  queryable in place, so a year or two would cost no more effort than the current twelve
  weeks — and the core grows faster than linearly with the window.

### Later — not scoped yet

GraphSAGE with text features (inductive: new repos without a full retrain), possibly
LightGCN if the framing becomes recommendation rather than exploration; reviving the
nearest neighbour API on a modern stack (FastAPI + hnswlib/FAISS) from the legacy branch.

On the viewer, `docs/viewers.md` surveys the alternatives (verified 2026-07-26) and
concludes we should keep the current one: what stalls at 25k points is the *projection*,
computed in the browser, not the rendering. Computing UMAP offline into three dimensions
and publishing it as an ordinary extra tensor gives instant, unsampled, fully 3D views
with no new infrastructure. Embedding Atlas would be a real gain for cross-filtering over
metadata columns, but it is 2D only.

## Budget

The user's subscription usage is **not visible to me** — `/usage` is a client-side
command with no tool behind it. Pacing therefore works by checkpoint: stop at each
milestone, report, let the user check `/usage` and decide the next scope. As of
2026-07-25 the weekly allowance was at 50%, resetting 2026-07-28.
