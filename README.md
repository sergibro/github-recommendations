# GitHub repositories and users recommendations by embeddings

Data: http://ghtorrent.org/downloads.html

Using Word2Vec Skip-gram architecture we train `repo2vec` (based on users stars), `following2vec` and `followers2vec` models.

## Visualisation
Visualizations with different kind of tensors (embeddings) are available at TensorBoard:
http://hel.sergibro.me:8002/#projector [hope not to forget to update if it moves]
Hints:
- open from desktop browser (it fetch hundreds of MB for larger tensors and computations done on the client side!);
- for better visual experience run T-SNE instead of PCA for `500-1K` iterations on large tensors with `5-15` perplexity and learning rate set to `1` (from our experience); for smaller tensors you can play more due to fewer computations (but losing in data points);
- you may choose feature to be colored by (language for repos, type for users, etc.)

## To run our pipeline
1. Download SQL dump you like (here we use `2019-03-01`) at `data/` folder and unpack relationships tables (CSV): `followers.csv`, `watchers.csv`; and metadata: `users.csv`, `projects.csv` to `data/%Y-%m-%d` folder (or change directories code dependencies at notebooks);
2. Change `resources/config.template.json` to `resources/config.json` with your info.
3. Run notebooks in ASC order;
4. View `tb/README` for more info about TensorBoard launch with your embeddings and metadata (docker based, but it is easy to run without it if needed);
5. Modify code the way you like to find some new insights and share with us!

---
**Contacts**: https://t.me/sergibro
