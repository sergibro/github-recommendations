# Where GitHub activity data can still be got

**Verified 2026-08-28.** Written after GHTorrent's death and after discovering that
GH Archive — the replacement `v2/fetch.py` uses — is both trimmed at the source and
undercounted by its own crawler.

Two separate needs, and no single source covers both:

- **(a) interaction history** — which user touched which repository, over time;
- **(b) repository metadata** — `language`, `stargazerCount`, `createdAt`, topics. These
  came from GHTorrent's relational tables in v1 and are what the current tensors lack.

## What happened to the firehose

Three distinct causes, established from primary sources. Only the first is GitHub policy;
conflating them was the mistake in the first version of `V2_PLAN.md`.

| When | What | Source |
| --- | --- | --- |
| announced 2025-08-08, brownout 2025-09-08, live **2025-10-07** | GitHub trimmed pull request and push payloads — fields "slow to generate and requiring costly database calls." `author_association` dropped from seven event types. One measurement: PullRequestEvent went from ~400 fields to ~60. | [GitHub changelog](https://github.blog/changelog/2025-08-08-upcoming-changes-to-github-events-api-payloads/) |
| **2025-10-09** | Daily events collapsed from 2,769,429 to 18,906. GitHub Support confirmed: "recent changes did introduce a cache for event data, which unexpectedly led to some users seeing 'stale' events." Partial recovery from 2025-10-14, never to the old baseline. Whether the cache is fully gone is unconfirmed. | [gharchive.org#312](https://github.com/igrigorik/gharchive.org/issues/312) |
| ongoing, fix open since **2026-02-19** | GH Archive's crawler fetches one page of `/events` per cycle where the API offers up to 300 events at 100 per page — so it captures roughly a third to a fifth of what is available. | [gharchive.org PR#317](https://github.com/igrigorik/gharchive.org/pull/317) |

Separately, `WatchEvent` capture fell from 90–100% before 2025-06 to 10–20% from 2026-02,
measured against the stargazers REST API. **No published explanation exists**
([#320](https://github.com/igrigorik/gharchive.org/issues/320)).

That last one is independently corroborated by someone with a stake in it being wrong:
**OSS Insight merged a change on 2026-08-19 disabling its star rankings outright**, on the
grounds that `WatchEvent`'s share of GH Archive fell from 2.96% to 0.22% between 2025-06
and 2026-08. Our own sampling of 2026-05-01 … 2026-07-23 measured 0.2%, arrived at
independently — so this is not a local artefact.

GH Archive itself is effectively unmaintained: no crawler code merged since 2025-05-25,
its maintainer unresponsive to a 2026-08-11 ping. Treat its output as a lower bound.

## (a) Interaction history

**`open-index/open-github` on Hugging Face — the closest thing to a GHTorrent-shaped
replacement.** The whole GH Archive event stream, restructured into Parquet tables *by
event type* — `stars`, `forks`, `pull_requests`, `pushes`, `issues`, `issue_comments`,
`pr_reviews`, `releases` and more — partitioned by year/month/day, covering **2011-02-12
to live** with a `live` config that updates in five-minute increments. ODC-BY, no login.

Being Parquet, DuckDB reads it in place over `hf://` with no download step, which removes
the 2,016-files problem entirely. Note it carries repo *identity* (id, name) but not repo
*attributes* — those come from (b) below. And since it is derived from GH Archive, its
post-2025 range inherits the undercounting described above; that is a property of the
upstream, not of this mirror.

**ClickHouse `github_events` — a second, independent way in, also without credentials.**
`play.clickhouse.com` with user `play`, queried directly on 2026-08-28:
**11,111,563,008 rows**, spanning **2011-02-12** to the current hour. One SQL table
instead of thousands of hourly files, which is the ergonomic problem solved outright.

Two caveats. It carries **no repository attributes** — 60 columns of event fields, no
`language`, no `stars`, no repo `created_at`; those can only be derived as event counts.
And because it is fed from GH Archive's raw files, its **recent** data inherits the same
degradation: sampling 2026-08-20 … 2026-08-24 shows PushEvent rising to ~98% share.

The important consequence: its **historical** range, roughly 2011 through mid-2025, was
captured before the collapse and is intact. That is the honest way to compare eras — build
a 2019 tensor and a current one from data of equal quality, rather than comparing a good
snapshot against a degraded one.

A frozen bulk snapshot through 2020-12-06 (3.1B rows, 75 GB compressed) is downloadable at
`clickhouse-public-datasets.s3.amazonaws.com/github_events_v2.native.xz`; the live table is
query-only. Liveness of that URL not tested.

**GH Archive on BigQuery** — needs a Google account (1 TB/month free on public datasets).
An unanswered 2024-11-01 discussion claims the mirror has not updated since ~2022. Since
it mirrors the same Events API, there is no reason to expect it kept fields the API stopped
emitting. Not verified either way; would need a credentialed session to settle.

## (b) Repository metadata

**`ibragim-bad/github-repos-metadata-40M` on Hugging Face.**
41,058,194 repositories, 2.3 GB of Parquet across six files, MIT licence. Schema verified
against the live dataset on 2026-08-28 with DuckDB reading `hf://` directly:

    repo_name, language, created_at, description, description_language,
    description_language_score, license_key, forks_count, watchers_count, size, last_pr_id

That is the v1 metadata set recovered — `language`, `created_at` and a star count — in one
file read rather than 25,905 API calls.

**It does need a Hugging Face token in practice**, which is worth stating precisely
because it is easy to get wrong. Reading the *schema* anonymously works. Pulling the
*files* does not: Hugging Face rate-limits by IP and answers with a plain-text body —
`"We had to rate limit your IP ... create a HF account or login ... and make sure you
pass a HF_TOKEN"` — which `curl` will happily save as a 196-byte "parquet" file unless the
download is size-checked. A free read-only HF token lifts it. This is a much lighter
credential than a GitHub PAT or a Google Cloud login, but it is not nothing.

Two further caveats: the dataset is built from GH Archive Create and PullRequest events, so
**repositories with no pull request activity are absent**, and it is a static snapshot
through **2025-07-23**.

**ecosyste.ms** (repos.ecosyste.ms) returns exactly the right fields — language, stars,
forks, `created_at`, topics, description, licence — confirmed by a live lookup. But it is
**API-only**: there is no bulk dump short of a paid custom export, and its published rate
limits contradict each other (a 2025-12 blog post says 5,000–15,000/hour, the current
pricing page says 300–5,000/hour). Data is CC BY-SA 4.0. Worth measuring the real limit
before planning around it.

**CNCF DevStats** does publish a genuine bulk dump — a 17 GB Postgres `gha.dump`,
last-modified 2026-08-25 — but it covers only the 256 CNCF projects.

**SEART GitHub Search** (seart-ghs.si.usi.ch, MIT) is the natural cross-check: 1,978,810
repositories, but only those with ≥10 stars, and 25 fields including topics, contributors
and branch counts. Its live API is capped at 100 results per page, and its static SQL dump
is stale — the newest is dated 2024-08-01, ~349 MB.

**GitHub GraphQL API — the fallback when freshness matters more than convenience.** Only connection fields
cost points: `primaryLanguage`, `stargazerCount` and `createdAt` are scalars and cost
nothing, so a batch of 100 repositories aliased into one query costs
`round(100 × 10 / 100) = 10` points for its `repositoryTopics(first: 10)`.

| | value |
| --- | --- |
| rate limit | 5,000 points/hour (authenticated) |
| repos to enrich | 25,905 |
| queries at 100 per batch | ~260 |
| total cost | ~2,600 points — **half of one hour's budget** |
| wall clock | **under 15 minutes** |

REST would take ~5 hours for the same work: no bulk endpoint, one request per repository
against a 5,000/hour limit.

On terms: GitHub's Acceptable Use Policies permit public, non-personal information "for
research purposes, only if any publications resulting from that research are open access,"
which is this project. Scraping the website is separately prohibited, as is sharing tokens
to exceed rate limits.

**deps.dev** (Google Open Source Insights) has a free unauthenticated JSON API and a
`Projects` table carrying star count, fork count, open issues and description. Repo
creation date and topics were not confirmed present. Worth checking as a no-credentials
partial substitute.

## Ruled out

- **GitHub Innovation Graph** — aggregated by economy × quarter only. No per-repository
  records exist at all, so it cannot enrich anything. CC0-1.0, from Q1 2020.
- **GitHub Archive Program / Arctic Code Vault** — physical film reels in Svalbard, no
  bulk download. Confirmed negative; its site repo has had no commits since 2024-03-17.
- **`bigquery-public-data.github_repos`** — source code, licences and languages-of-files;
  no stars or creation dates. Community reports say it froze around 2020–2022; Google has
  published no freeze date.
- **OpenSSF Criticality Score** — has language and creation-date proxies per repo, but its
  public infrastructure shuts down after **2026-08-29** and its last successful run was
  2025-07. Only the stale in-repo snapshot (`20250725_all.csv.gz`) survives, and being
  committed to git, it survives the shutdown.
- **OpenSSF Scorecard** — weekly BigQuery dataset over ~1M repos, CDLA Permissive 2.0, but
  security check scores rather than repository metadata; stars/language likely absent.
- **AWS Open Data Registry, Azure Open Datasets** — no GitHub events dataset.
- **Snowflake (Cybersyn), Databricks Marketplace** — GitHub archive products exist but
  require an account on those platforms; no anonymous bulk export.
- **`common-pile/github_archive` on Hugging Face** — 30.3M issue/PR threads, 85.7 GB,
  2011 to 2025-04-01, anonymous download. Text only: no language, stars or creation dates.
- **GHTorrent** — `ghtorrent.org` no longer belongs to the project; it 301-redirects
  through a squatted domain chain. Its coverage was ~2012–2019, ~18 TB of compressed JSON
  plus 6.5B MySQL rows. **No working mirror was found** — not at TU Delft, not on Zenodo
  (only small derived extracts), and the Wayback Machine archived the download pages but
  not the multi-terabyte files behind them. Academic Torrents could not be checked
  (Cloudflare challenge blocks automated access) and remains the one unexplored channel,
  needing a manual browser visit.
- **Software Heritage Graph** — enormous and genuinely open (latest export 2026-06-04:
  58.68B nodes, 1.10T edges, ~33 TiB ORC, anonymous S3), but its schema was checked and it
  has **no stars, no forks, no language and no topics** — it is a content-provenance Merkle
  DAG, so it cannot substitute for the social metadata at all.
- **World of Code** — 7.3B commits, 350.7M repositories, still updated (~V2605, 2026-08).
  But access means registering with an SSH key and querying UTK's servers remotely; the
  terms explicitly forbid bulk extraction, and it holds commit provenance rather than
  stars or topics.
- **Libraries.io open data** — 24.9 GB across seven CSV tables including a repositories
  table, CC-BY 4.0, direct download. **Frozen at v1.6.0, published 2020-01-12**; confirmed
  via the Zenodo API that no newer version exists.
- **`bigcode/the-stack-v2`** — carries `star_events_count`, `gha_language` and
  `gha_created_at` per row, but gated behind a Hugging Face login plus terms acceptance,
  the metadata is embedded per source file rather than offered as a repository table, and
  it is a 2023-09 snapshot.
- **MSR Data Showcase 2023–2026** — reviewed; the track has moved to narrow domain
  datasets (bots, SBOMs, CI logs). Nothing at GHTorrent's scope.

## Where this leaves the project

The chunking problem and the metadata problem have different answers, and both are
reachable: ClickHouse for history in one query with no credentials, GraphQL for metadata in
a quarter of an hour with a read-only token. The genuinely new information is that the
current tensors rest on undercounted data — so rebuilding from a pre-2025 window is not
nostalgia, it is the only way to get a graph whose density reflects reality.
