import os
import argparse

import pandas as pd
import numpy as np

import tensorflow as tf
from tensorflow.contrib.tensorboard.plugins import projector


def _prepare_data(model_path):
    model_df = pd.read_pickle(model_path)
    if 'embeddings' not in model_df:
        raise KeyError('Column \'embeddings\' does not exist')
    embeddings = np.vstack(model_df['embeddings'].values)
    metadata = model_df[[c for c in model_df.columns if c != 'embeddings']]
    print(embeddings.shape)
    print(metadata.shape)
    return metadata, embeddings


def _write_metadata(metadata, metadata_path):
    with open(metadata_path, 'w', encoding='utf-8') as f:
        if metadata.shape[1] == 1:
            f.write('\n'.join(metadata.iloc[:, 0].values))
        else:
            f.write('\t'.join(metadata.columns) + '\n')
            for _, row in metadata.iterrows():
                f.write('\t'.join([str(v) for v in row.values]) + '\n')


def save_tf_model(model_path, log_dir, sess, config):
    model_name = os.path.split(model_path)[-1]
    metadata, embeddings = _prepare_data(model_path)

    #tensor_name = model_name + '_embedding'
    tensor_name = model_name.split('.')[0]
    X = tf.Variable([0.0], name=tensor_name)
    place = tf.placeholder(tf.float32, shape=embeddings.shape)
    set_x = tf.assign(X, place, validate_shape=False)
    sess.run(set_x, feed_dict={place: embeddings})

    md_fname = f'{tensor_name}_metadata.tsv'
    md_path = os.path.join(log_dir, md_fname)
    _write_metadata(metadata, md_path)

    embedding_conf = config.embeddings.add()
    embedding_conf.tensor_name = tensor_name
    embedding_conf.metadata_path = md_fname

    return sess, config


def save_models(model_dir, log_dir):
    tf.reset_default_graph()
    sess = tf.InteractiveSession()
    sess.run(tf.global_variables_initializer())

    summary_writer = tf.summary.FileWriter(log_dir, sess.graph)
    config = projector.ProjectorConfig()

    for model_name in sorted(os.listdir(model_dir)):
        print(model_name)
        model_path = os.path.join(model_dir, model_name)
        sess, config = save_tf_model(model_path, log_dir, sess, config)

    projector.visualize_embeddings(summary_writer, config)
    saver = tf.train.Saver()
    saver.save(sess, os.path.join(log_dir, 'model.ckpt'))


def main():
    print('Start.')
    parser = argparse.ArgumentParser(description="visualize_tb")
    parser.add_argument('-m', dest='model_dir', help='path to directory with data models')
    parser.add_argument('-l', dest='log_dir', help='path to log directory')
    args = parser.parse_args()
    save_models(model_dir=args.model_dir, log_dir=args.log_dir)
    print('Done.')


if __name__ == '__main__':
    main()
