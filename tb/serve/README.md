# Serving the embeddings

The [Embedding Projector](https://projector.tensorflow.org/) is a client-side
application: it downloads tensors and runs PCA/t-SNE/UMAP in the browser. Nothing
needs to run on the server, so the whole demo is a handful of static files behind
any web server. This replaces the original docker + TensorBoard 1.x setup, which
required a live Python process just to hand out the same bytes.

## 1. Export the assets

`convert.py` turns embedding pickles into what the projector expects:

```bash
python convert.py \
    --src ./pickles \
    --out /srv/tb/embeddings \
    --base-url https://tb-gh-recs.example.com \
    --order repos_25k_gte1k,users_73k_gte500,repos_19k_gte1k_old,users_48k_gte100_old
```

Each pickle must be a pandas DataFrame with an `embeddings` column (one vector per
row); every other column becomes metadata you can colour and search by. For one
pickle named `repos_25k_gte1k.pkl` you get:

| file | what |
| --- | --- |
| `repos_25k_gte1k.bytes` | raw little-endian float32, row-major, no header |
| `repos_25k_gte1k_labels.tsv` | header row + one row per point, same order |
| `config.json` | manifest listing every tensor, its shape and its URLs |

Requires only `pandas` and `numpy`.

**`--base-url` is not optional in practice.** The projector resolves `tensorPath`
and `metadataPath` against the page it is running on, *not* against the config URL.
When the app and the data are served from different hosts -- which they are here,
and always are when using the hosted projector -- relative paths resolve to the app
host and 404, and the UI reports `Error fetching tensors`.

## 2. Serve them

See `Caddyfile.example`. Three hosts: the data, a public copy of the projector
bundle, and a private password-protected copy. The important rule is that the
`Access-Control-Allow-Origin` header belongs on the *data* host only, since that is
what the browser fetches cross-origin; the hosts serving the application itself
need no CORS at all.

The bundle for the app hosts is the `index.html` from the archived
[embedding-projector-standalone](https://github.com/tensorflow/embedding-projector-standalone)
repository -- a single self-contained file. Patch the demo config path baked into
it to point at your own `config.json` so the bare URL works without a query string.

## 3. Open it

Using the hosted projector, no app host of your own needed:

```
https://projector.tensorflow.org/?config=https://tb-gh-recs.example.com/config.json
```

Verify a deployment from the command line before trusting it: every asset must
return `200` together with the CORS header, when asked for as the browser asks.

```bash
curl -s -o /dev/null -w "%{http_code} %header{access-control-allow-origin}\n" \
    -H "Origin: https://projector.tensorflow.org" \
    https://tb-gh-recs.example.com/config.json
```

Then open the page and check that the tensor list is populated and points render;
large tensors take a while, since the whole file is fetched before anything is
drawn and the projection is computed client-side.

## Raising the sampling limits

"For faster results, the data will be sampled down to 10,000 points" is not a
limit on what is *displayed* -- every point is loaded and rendered. It caps what
the expensive projections are computed over: t-SNE and UMAP give coordinates only
to the first N points of a shuffled order, so the rest drop out of those two
views. PCA is different -- it samples only to compute the components, then
projects everything.

The three sizes are compiled into the bundle as constants:

```js
a.TSNE_SAMPLE_SIZE=1E4;a.UMAP_SAMPLE_SIZE=5E3;a.PCA_SAMPLE_SIZE=5E4;a.PCA_SAMPLE_DIM=200
```

Rather than hard-coding different numbers, they can be made overridable from the
query string, keeping the current values as defaults:

```js
var _sp=new URLSearchParams(location.search);
a.TSNE_SAMPLE_SIZE=+_sp.get("tsne")||1E4;a.UMAP_SAMPLE_SIZE=+_sp.get("umap")||5E3;
a.PCA_SAMPLE_SIZE=+_sp.get("pca")||5E4;a.PCA_SAMPLE_DIM=+_sp.get("pcadim")||200
```

An absent or unparseable value falls back to the default, and the labels in the
UI update on their own, since they read the same constants. Then:

```
https://tb.example.com/?tsne=30000&umap=15000
```

Worth doing on a private front end, and worth thinking twice about on a public
one: t-SNE and UMAP run in the browser, so a large value on a weak device reads
as a hung tab rather than as a slow projection.
