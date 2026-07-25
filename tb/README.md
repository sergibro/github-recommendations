# Visualizing the embeddings

**Use [`serve/`](serve/) — it is the current way.** The Embedding Projector runs
entirely in the browser, so the embeddings only need to be exported once and served
as static files. There is no TensorBoard process to keep alive and nothing to
rebuild when you want to look at the data again.

Either way the input is the same: a directory of pickled pandas DataFrames, each
with an `embeddings` column and at least one metadata column.

## Legacy: TensorBoard 1.x in docker

The scripts in this directory (`build.sh`, `run.sh`, `visualize.py`) start
TensorBoard 1.13 in a container, which loads the pickles through TensorFlow and
serves its own copy of the projector:

```bash
./run.sh {X number for 800X port} {path to model}
```

They are kept for reference and no longer used. TensorFlow 1.x needs Python 3.7 or
older, `tf.contrib` was removed in TensorFlow 2, and `run.sh` publishes a
`--privileged` container directly on a public port — reason enough not to expose
this to the internet. The static setup in `serve/` produces the same visualization
with none of that.
