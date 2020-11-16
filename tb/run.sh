#!/bin/bash
APP_PATH="$( cd "$( dirname "$0" )" && pwd )"
cd $APP_PATH || exit

TB_PORT=$1
if [ ${#TB_PORT} -eq 1 ]
then
    TB_PORT=0$TB_PORT
fi

mkdir -p logs

EMB_DIR=${2:-embeddings}

TB_PORT=80$TB_PORT
CONTAINER_NAME=tb-$TB_PORT
PORTS=$TB_PORT:6006

docker rm -f $CONTAINER_NAME
docker run \
    -d \
    --restart always \
    --privileged \
    -e GRANT_SUDO=yes \
    -e TZ=Europe/Kiev \
    -p $PORTS \
    -m 4G \
    --name $CONTAINER_NAME \
    -v $APP_PATH:/app \
    sergibro/tb \
    bash daemon.sh $EMB_DIR
