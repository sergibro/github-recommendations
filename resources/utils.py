import numpy as np
import pandas as pd

import logging.config
from tqdm import tqdm_notebook as tn

from requests import Session
from pymongo import MongoClient

with open('./resources/config.json') as cf:
    from json import load
    config = load(cf)

mc = MongoClient(config['mongo_url'])

def tgn(msg: str, keys=config['tg_alarmer_keys']):
    s = Session()
    for key in keys:
        parts = msg.split('\n\n')
        for part in parts:
            s.get('https://alarmerbot.ru/', params={'key': key, 'message': part})

def set_logging(filename='debug.log'):
    handlers = {"file": {
        "level": "DEBUG", "class": "logging.handlers.WatchedFileHandler",
        "formatter": "debug", "filename": filename,
        "mode": "w", "encoding": "utf-8"
    }}
    config = {
        "version": 1, "disable_existing_loggers": False,
        "formatters": {"debug": {"class": "logging.Formatter", "format": "[%(asctime)s] %(message)s"}},
        "handlers": handlers,
        "root": {"handlers": ["file"], "level": "DEBUG"}
    }
    logging.config.dictConfig(config)

class SentencesGenerator:
    def __init__(self):
        pass
    
    def generate(self, _input, min_words=5, max_words=None, interested_uids=None):
        np.random.seed(2019)
        total_words = 0
        check = False
        if interested_uids:
            interested_uids = set(interested_uids)
            check = True
        for sentence in tn(_input):
            if check:
                sentence = (set(sentence) & interested_uids)
            if len(sentence) >= min_words:
                sentence = [str(uid) for uid in sentence]
                if max_words:
                    np.random.shuffle(sentence)
                    sentence = sentence[:max_words]
                total_words += len(sentence)
                yield ' '.join(sentence)
        print(f'Total words: {total_words}')
    
    def save(self, _input, path, **kwargs):
        output = self.generate(_input, **kwargs)
        with open(path, 'w') as f:
            for line in tn(output):
                f.write(line + '\n')
