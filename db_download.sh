#!/bin/bash

DUMP_DATE=${1:-2020-07-17}
URL="http://ghtorrent-downloads.ewi.tudelft.nl/mysql/mysql-$DUMP_DATE.tar.gz"
echo $URL

nohup wget -cP data $URL > logs/downloads_$DUMP_DATE.out &
