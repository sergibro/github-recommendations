# GitHub repositories and users recommendations by embeddings

Data: http://ghtorrent.org/downloads.html

Using [PyTorch-BigGraph (PBG)](https://github.com/facebookresearch/PyTorch-BigGraph) we train `repo2vec` (based on users stars) and `user2vec` models.

## Visualisation
Visualizations with different kind of tensors (embeddings) are available at TensorBoard:
http://hel.sergibro.me:8002/#projector [hope not to forget to update if it moves]
Hints:
- open from desktop browser (it fetch hundreds of MB for larger tensors and computations done on the client side!);
- for better visual experience run T-SNE instead of PCA for `500-1K` iterations on large tensors with `5-15` perplexity and learning rate set to `1` (from our experience); for smaller tensors you can play more due to fewer computations (but losing in data points);
- you may choose feature to be colored by (language for repos, type for users, etc.)

## To run our pipeline
1. Change `resources/config.template.json` to `resources/config.json` with your info;
2. Run notebook;
3. Download SQL dump you like (here we use `2019-06-01`) at `data/` folder and extract relationships tables (CSV): `followers.csv`, `watchers.csv`, `project_members.csv`; and metadata: `users.csv`, `projects.csv` to `data/%Y-%m-%d` folder (or change directories code dependencies at notebooks);
4. View `tb/README` for more info about TensorBoard launch with your embeddings and metadata (docker based, but it is easy to run without it if needed);
5. Modify code the way you like to find some new insights and share with us!
s
---
**Contacts**: https://t.me/sergibro
