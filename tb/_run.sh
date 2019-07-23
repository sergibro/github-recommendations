LOGDIR=logs/$2
rm -rf $LOGDIR
mkdir -p $LOGDIR
python visualize.py -m $1 -l $LOGDIR
tensorboard --logdir=$LOGDIR/ --port=$2
