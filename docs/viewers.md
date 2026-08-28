# Embedding viewers — survey

**Verified 2026-07-26.** Everything below was checked against primary sources on that
date; dates in the tables are the ones those sources carried. This field moves fast, so
treat anything here as needing re-checking after roughly a year — the point of recording
the verification date is to make the staleness visible rather than to pretend otherwise.

Written while deciding whether to replace the TensorFlow Embedding Projector, which
`tb/serve/` currently deploys as static files.

## The finding that reframes the question

Across everything surveyed, **the projection is what breaks first, not the rendering.**
Browser t-SNE and UMAP become unusable in the tens of thousands of points, while renderers
comfortably handle millions — Apple's Embedding Atlas reports 4M points at 60fps on an
M1 Pro, regl-scatterplot claims up to 20M. Our own demo stalls at 25,905 points for
exactly this reason: the projector computes the t-SNE nearest-neighbour graph by brute
force in the browser.

So "find a viewer that scales" is usually the wrong move. The right one is to compute the
projection offline and ship coordinates. A viewer that draws pre-computed 3D coordinates
needs no cleverness at all.

## What breaks at what scale

| Points | Projection | Rendering | Transfer | Interaction |
| --- | --- | --- | --- | --- |
| ~10k | anything works, even in-browser t-SNE | anything | plain JSON | naive JS filtering |
| ~100k | exact kNN and exact t-SNE become painful — needs approximate NN (pynndescent, HNSW) or a move to Python | GPU instancing and binary typed-array attributes become necessary | JSON parse starts costing real time once metadata is attached | naive CPU filter-and-rebuild causes visible jank; needs a spatial index or GPU picking |
| ~1M | in-browser projection infeasible; compute server-side or on GPU (cuML reports 100–500× over CPU) and ship coordinates only | full-buffer instancing still works if it fits GPU memory; overdraw management starts to matter | "download it all as JSON" becomes untenable; Arrow or raw typed arrays needed | GPU-side filtering and picking rather than CPU rebuilds |
| ~10M+ | only GPU or FIt-SNE's O(N) scaling is viable | tiled/LOD streaming becomes mandatory; 10–25fps even on optimised renderers | only viewport-relevant tiles ever resident | spatial index and GPU filtering are mandatory, not optional |

Two numbers worth remembering: deck.gl documents ~1 billion fragment-shader invocations
per frame for 10M points at 5px radius, which is why overdraw — not vertex count — is the
usual rendering wall; and its picking system caps at 16M items per layer.

## The three modalities fail differently

**Text** fails on *label placement*, not on drawing. Two opposed strategies: Embedding
Atlas resolves collisions (implementing Been, Daiches & Yap, *Dynamic Map Labeling*,
IEEE TVCG 2006), while WizMap avoids them by construction — a quadtree over the
embeddings, one TF-IDF label per visible tile, so the number of labels on screen stays
constant regardless of N. The second scales better.

**Images** fail on *GPU texture memory*. The dividing line in practice is whether a tool
builds a sprite atlas: Latent Scope builds a tiled pyramid at several resolutions and
loads only visible tiles, whereas Embedding Atlas renders each image individually as a
data URL — fine for hundreds, not for tens of thousands. The TensorFlow Projector's own
sprite sheet is capped at 8192×8192 px (`MAX_SPRITE_IMAGE_SIZE_PX` in `data-provider.ts`),
which is ~65,000 images at 32×32 px but only ~6,500 at 100×100 px, and it separately
refuses to load past 100,000 vectors.

**Graphs** fail on *layout*, well before rendering. Edges grow as N·k, and CPU force
layouts break down around 50,000–100,000 nodes. The only real workaround is keeping the
layout GPU-resident, as cosmos.gl does. Note that **none of the embedding viewers below
draw edges at all** — they are all point-cloud tools. Our graph is 346,460 edges over
76,487 nodes, so this is a real gap rather than a hypothetical one.

## Candidates

### Point-cloud viewers

| Tool | 3D | Scale | Static? | Licence | Status (as of 2026-07-26) |
| --- | --- | --- | --- | --- | --- |
| TF Embedding Projector (what we use) | **yes** | ~25k, limited by in-browser t-SNE | yes | Apache-2.0 | standalone repo **archived 2026-04** |
| [WizMap](https://github.com/poloclub/wizmap) | no | 1.8M in the paper | **yes** | MIT | last push 2026-01-22 |
| [Embedding Atlas](https://github.com/apple/embedding-atlas) | no | 4M default downsample cap | yes, after export | MIT | v0.22.0, 2026-07-07 |
| [Latent Scope](https://github.com/enjalot/latent-scope) | in progress | ~500k self-reported | no, needs Python | MIT | v1.0.0, 2026-07-12 |
| [Vitessce](https://github.com/vitessce/vitessce) | 2D scatter | "millions" (deck.gl) | yes | MIT | v4.0.1, 2026-07-21 |
| [UCSC Cell Browser](https://github.com/ucscGenomeBrowser/cellBrowser) | mostly 2D | atlas-scale | **yes** | GPL-3.0 | last push 2026-07-24 |
| [cellxgene](https://github.com/chanzuckerberg/cellxgene) | no | **2.07M** benchmarked | no, Flask | MIT | no tag since 1.3.0, 2024-09 |
| [LightlyStudio](https://github.com/lightly-ai/lightly-studio) | **yes** | vendor claim only | no | Apache-2.0 | launched ~2026-03 |
| [FiftyOne](https://github.com/voxel51/fiftyone) | no | undocumented | no | Apache-2.0 | last push 2026-07-26 |
| [Spotlight](https://github.com/Renumics/spotlight) | no | undocumented | no | MIT | last push 2026-07-24 |

### Rendering libraries, if building something custom

| Library | 3D | Scale | Licence | Latest (as of 2026-07-26) |
| --- | --- | --- | --- | --- |
| [deck.gl](https://deck.gl) | **yes**, `OrbitView` + `PointCloudLayer` | 1M at 60fps, 10M at 10–20fps | MIT | v9.3.7, 2026-07-16 |
| [Rerun](https://rerun.io) | **yes**, `Points3D` | large | Apache-2.0 / MIT | active |
| [regl-scatterplot](https://github.com/flekschas/regl-scatterplot) | no | claims 20M | MIT | v1.16.0, 2026-05-08 |
| [cosmos.gl](https://github.com/cosmosgl/graph) | no | ~1M nodes, GPU layout | MIT | v3.3.0, 2026-07-12 |
| [DeepScatter](https://github.com/nomic-ai/deepscatter) | no ("no fake 3d") | billions, Arrow quadtree tiles | **CC-BY-NC-SA** | v2.10.0, 2026-04-11 |

## What Embedding Atlas actually does well

Worth recording, because the interesting parts are not in the marketing copy:

- **Everything is a SQL client over DuckDB.** Charts and the scatter register as Mosaic
  (`@uwdata/vgplot`) clients on a shared coordinator; a selection becomes a SQL `WHERE`
  predicate broadcast to every other view, and a lasso becomes a point-in-polygon
  predicate. Cross-filtering is the architecture, not a feature bolted on.
- **Clustering runs on the density texture, not the points** (arXiv:2504.07285). A KDE map
  is computed on the GPU, then a Rust/WASM pass extracts clusters from that raster in a
  few hundred milliseconds — cost is nearly independent of N, which is why clusters can
  recompute live while panning and filtering.
- **Labels are c-TF-IDF computed in the browser**, not LLM calls.
- **Scale is tuned by DuckDB mode**, not by swapping tools: `wasm` (bounded by tab
  memory), `server` (native DuckDB in the Python process), or a remote endpoint.

The gotcha: its nearest-neighbour feature is a **precomputed column** from UMAP's
pynndescent graph, not a live index, and its search box is **lexical** (FlexSearch), not
semantic. Live semantic search requires implementing the optional `vectorSearch` hook.

Latent Scope makes the opposite trade: a reproducible `ingest → embed → project → cluster
→ label` pipeline with every intermediate artefact on disk, LLM-written cluster labels,
and genuine query-time semantic search over LanceDB. Its value is experimenting with the
pipeline; ours is already written, so it would mostly duplicate `v2/`.

## Claims that were true once and are not any more

Checked 2026-07-26. These are all still repeated in blog posts:

- **Arize Phoenix** removed its UMAP visualiser in **v13.0.0 (2026-02)** — confirmed in
  its own `MIGRATION.md`. It is also Elastic License 2.0, i.e. source-available, not OSI
  open source.
- **Attu** (the Milvus GUI) **went proprietary at v2.6.0**; only ≤2.5.12 remains
  Apache-2.0.
- **Weights & Biases**' embedding projector panel is capped at **1,000 rows and 50
  dimensions**.
- **Aim**'s embedding projector is a roadmap item, not a shipped feature.
- **Parallax** (Uber) is under a custom non-commercial licence and was last pushed
  2024-08-20.
- **Encord Active** is archived; development moved to a closed SaaS.
- Of the vector databases, **only Qdrant ships a visualiser** — and it samples 500 vectors
  by default and freezes past ~10,000. Chroma, Weaviate and Milvus have nothing usable.

## Recommendation for this project

Keep the current viewer. Compute UMAP offline into **three** dimensions and publish the
result as an ordinary extra tensor: the projector's PCA view of a 3-dimensional tensor is
just a rotation of coordinates that are already correct, so it renders instantly, shows
every point with no sampling, and keeps full 3D orbit. That needs no new infrastructure,
no new viewer, and no change to `tb/serve/convert.py`.

If the viewer is ever replaced: **WizMap** is the closest architectural match, being the
only surveyed tool that is genuinely static-file-only like our current deployment.
**Embedding Atlas** is the strongest overall if 2D is acceptable, and its cross-filtering
over metadata columns (`degree`, `stars`, `first_seen`) would be a real gain over what the
projector offers. For true 3D at scale there is no turnkey option — it would mean building
on deck.gl or Rerun and writing the search, colouring and neighbour panels ourselves.

One genuinely open gap, as of 2026-07-26: **nobody has shipped WebGPU-compute-accelerated
projection running client-side.** The substrate exists (WebGPU at ~85% global support,
Safari by default since 2025, Firefox from 2026-01), but no implementation was found.
