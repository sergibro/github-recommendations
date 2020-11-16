import os
import logging
from core import Core


def main():
    for model_name in core.list_models():
        if 'repo' not in model_name:
            continue
        logging.debug(f'Checking index for {model_name}')
        if os.path.exists(f'index/{model_name}.ann') and os.path.exists(f'index/{model_name}.pkl'):
            logging.info(f'{model_name} index already exists. Using previous formed index.')
        else:
            core.build_index(model_name)


if __name__ == '__main__':
    core = Core()
    main()
