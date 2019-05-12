In order to launch TensorBoard run script `run.sh` as following:
`$ ./run.sh {X number for 800X port} {path to model}`

`path/to/model_data/` directory contains models' data as pickled pandas dataframes. Each DF contains embeddings as well as metadata.
Dataframe MUST contain column `embeddings` and at least one metadata column.
