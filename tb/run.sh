#!/bin/bash

TB_PORT=$1
if [ ${#TB_PORT} -eq 1 ]
then
    TB_PORT=0$TB_PORT
fi

TB_PORT=80$TB_PORT
APP_PATH=$(pwd)
CONTAINER_NAME=tb-$TB_PORT
PORTS=$TB_PORT:$TB_PORT

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
    bash _run.sh $2 $TB_PORT
