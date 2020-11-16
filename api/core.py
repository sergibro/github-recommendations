import logging
import os
import pandas as pd
from annoy import AnnoyIndex


class Core:
    def __init__(self):
        pass

    def build_index(self, model_name, n_trees=1_000):
        self.df = pd.read_pickle(f'data/{model_name}.pkl')
        self.dim = len(self.df['embeddings'].iloc[0])
        self.ann = AnnoyIndex(self.dim, 'angular')  # Length of item vector that will be indexed
        self.mapping = {}
        for i, (repo_id, e) in enumerate(self.df['embeddings'].iteritems()):
            self.ann.add_item(i, list(e))
            self.mapping[repo_id] = i
        logging.info(f'Building index for {model_name}')
        self.ann.build(n_trees)
        self.ann.save(f'index/{model_name}.ann')
        pd.to_pickle(self.mapping, f'index/{model_name}_mapping.pkl')
        logging.info(f'Built index for {model_name}')

    @staticmethod
    def list_models():
        model_names = sorted(os.listdir('data'))
        model_names = [model_name.split('.')[0] for model_name in model_names]
        return model_names

    @staticmethod
    def list_index():
        index_names = sorted(os.listdir('index'))
        index_names = [index_name.split('.')[0] for index_name in index_names if index_name.split('.')[-1] == 'ann']
        return index_names

    def load_index(self, model_name, inner=False):
        try:
            self.df = pd.read_pickle(f'data/{model_name}.pkl')
            self.dim = len(self.df['embeddings'].iloc[0])
            self.ann = AnnoyIndex(self.dim, 'angular')
            self.ann.load(f'index/{model_name}.ann')  # super fast, will just mmap the file
            # self.ann.get_n_items(), ann.get_n_trees()
            self.mapping = pd.read_pickle(f'index/{model_name}_mapping.pkl')
            self.mapping_rev = {v: k for k, v in self.mapping.items()}
            status = 'Loaded'
        except Exception:
            status = 'Not loaded'
        return status

    @staticmethod
    def get_repo_query(query):
        repo_query = '/'.join(query.split('/')[-2:])
        return repo_query

    def exists(self, repo_query):
        return bool(self.df['url'].str.lower().str.contains(repo_query.lower()).any())

    def get_closest_repos(self, repo_query, inner=False, top_n=10):
        """Get the nearest neighbors

        :param repo_query: e.g. 'apache/spark'
        :param inner:
        :param top_n:
        :return:
        """
        _id = self.df[self.df['url'].str.lower().str.contains(repo_query)].index[0]
        res, dist = self.ann.get_nns_by_item(self.mapping[_id], top_n, include_distances=True)  # find the top_n nearest neighbors
        res = [self.mapping_rev[r] for r in res]
        res = self.df.loc[res]
        res['distance'] = [round(d, 3) for d in dist]
        res = res[['url', 'distance']].to_dict('records')
        return res
