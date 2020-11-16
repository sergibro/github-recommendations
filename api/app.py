import logging
import logging.config
import json
from json.decoder import JSONDecodeError
from functools import wraps
from requests import Session

from flask import Flask, request, jsonify

from core import Core

app = Flask(__name__)
app.core = None  # type: Core

GENERAL_ENDPOINT = '/api/v1.0/'
TRUES_STRINGS = ['1', 'true', 'yes', 'y', 't', '+']  # lowercase


def init_app():
    with open('./resources/logging.json') as f:
        log_config = json.load(f)
    logging.config.dictConfig(log_config)
    app.config['JSON_AS_ASCII'] = False
    app.core = Core()
    model_name = 'repos_19k_gte1k'  # ToDo: avoid hardcode
    app.core.load_index(model_name)
    logging.debug('[Inited app]')


init_app()


def unexpected_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            logging.debug(f'[request] {request}')
            return func(*args, **kwargs)
        except Exception as e:
            logging.exception(f'[Exception] {e}')
            return jsonify({'error': f'{e}'}), 404

    return wrapper


@app.route(GENERAL_ENDPOINT + 'list_models', methods=['GET'])
@unexpected_error
def list_models():
    model_names = app.core.list_models()
    res_dict = {
        'model_names': model_names
    }
    return jsonify(res_dict)


@app.route(GENERAL_ENDPOINT + 'list_index', methods=['GET'])
@unexpected_error
def list_index():
    index_names = app.core.list_index()
    res_dict = {
        'index_names': index_names
    }
    return jsonify(res_dict)


@app.route(GENERAL_ENDPOINT + 'load_index', methods=['GET'])
@unexpected_error
def load_index():
    data = request.args
    try:
        model_name = data.get('model_name')
        if not model_name:
            raise Exception('No model_name provided')
        inner = data.get('inner', 'f').lower() in TRUES_STRINGS
    except (KeyError, ValueError, JSONDecodeError):
        m = 'Bad query argument'
        logging.debug(f'[request] {m}')
        bad_query_response = {'error': m}
        return jsonify(bad_query_response), 404
    status = app.core.load_index(model_name, inner)
    res_dict = {
        'status': status,
        'model_name': model_name
    }
    return jsonify(res_dict)


@app.route(GENERAL_ENDPOINT + 'get_closest_repos', methods=['GET'])
@unexpected_error
def get_closest_repos():
    data = request.args
    try:
        query = data.get('gh_repo')
        if not query:
            raise Exception('No gh_repo provided')
        inner = data.get('inner', 'f').lower() in TRUES_STRINGS
        top_n = int(data.get('top_n', 10))
    except (KeyError, ValueError, JSONDecodeError):
        m = 'Bad query argument'
        logging.debug(f'[request] {m}')
        bad_query_response = {'error': m}
        return jsonify(bad_query_response), 404
    repo_query = app.core.get_repo_query(query)
    exists = app.core.exists(repo_query)
    res_dict = {
        'data': [],
        'query': query,
        'repo_query': repo_query,
        'exists': exists,
        'top_n': top_n
    }
    if exists:
        res = app.core.get_closest_repos(repo_query, inner=inner, top_n=top_n)
        res_dict['data'] = res
    return jsonify(res_dict)


@app.route(GENERAL_ENDPOINT + 'get_ip_info', methods=['GET', 'POST'])
@unexpected_error
def get_ip_info():
    data = json.loads(request.data) if request.method == 'POST' else request.args
    ip = data.get('ip')
    if not ip:
        ip = request.environ.get('HTTP_X_REAL_IP')
    if ip:
        s = Session()
        r = s.get(f'http://ip-api.com/json/{ip}?fields=262143&lang=en').json()
        return jsonify(r)
    ip_dict = {
        'ip': request.environ.get('REMOTE_ADDR', 'ERROR')
        # list(request.environ.keys())
    }
    return jsonify(ip_dict)


if __name__ == "__main__":
    logging.info('[App] Start')
    app.run(host='0.0.0.0', port=5000)
