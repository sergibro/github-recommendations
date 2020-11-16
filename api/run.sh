#!/bin/bash
APP_PATH="$( cd "$( dirname "$0" )" && pwd )"
cd $APP_PATH || exit
DATA_PATH="$( cd "../tb/embeddings" && pwd )"

API_PORT=$1
if [ ${#API_PORT} -eq 1 ]
then
    API_PORT=0$API_PORT
fi

mkdir -p logs index

API_PORT=80$API_PORT
PORTS=$API_PORT:5000
IMAGE_NAME=sergibro/gh-api
CONTAINER_NAME=gh-api-$API_PORT
WORKERS=${2:-8}

docker rm -f $CONTAINER_NAME
docker run \
    -d \
    --restart always \
    --privileged \
    -e GRANT_SUDO=yes \
    -e TZ=Europe/Kiev \
    -p $PORTS \
    -m 8G \
    --name $CONTAINER_NAME \
    -v $APP_PATH:/app \
    -v $DATA_PATH:/app/data \
    $IMAGE_NAME \
    bash daemon.sh $WORKERS
