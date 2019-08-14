# GitHub repositories and users recommendations by embeddings

## Problem Statement
Currently, GitHub has two possibilities to explore users and repositories:
1. Direct search by search term leveraging names and tags.
2. Recommender system under 'Explore' tab which gives suggestions to a user based on his usage of service.
However, there is no possibility to perform a search of connected entities. E.g., find repositories or users highly related to each other.

## Goal of the Project
The goal of this project is to build GitHub repository search/recommender system, which would allow exploring connected repositories and people, by leveraging the underlying graph structure of the repositories database.

## Implemented ML solution
It was decided to build graph nodes embeddings (`repo2vec` and `user2vec`) for the entire GitHub database using [PyTorch-BigGraph (PBG)](https://github.com/facebookresearch/PyTorch-BigGraph). On top of the embeddings representation, we have built query tool with the ranking engine.

Data: http://ghtorrent.org/downloads.html

## To run our pipeline
1. Change `resources/config.template.json` to `resources/config.json` with your info;
2. Download SQL dump you like (here we use `2019-06-01`) at `data/` folder (run `db_download.sh` script (at terminal));
3. Run `project_notebook.ipynb` notebook;
4. View `tb/README.md` for more info about TensorBoard launch with prepared embeddings and metadata (docker based, but it is possible to run without it if needed);
5. Modify code the way you like to find some new insights and share with us!

## Visualisation
Visualizations with different kind of tensors (embeddings) are available at TensorBoard:
http://hel.sergibro.me:8002/#projector [hope not to forget to update if it moves]
Hints:
- open from desktop browser (it fetch hundreds of MB for larger tensors and computations done on the client side!);
- for better visual experience run T-SNE instead of PCA for `500-1K` iterations on large tensors with `5-15` perplexity and learning rate set to `1` (from our experience); for smaller tensors you can play more due to fewer computations (but losing in data points);
- you may choose feature to be colored by (language for repos, type for users, etc.)

---
**Contacts**: https://t.me/sergibro
