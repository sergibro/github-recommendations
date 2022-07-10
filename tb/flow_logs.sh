#!/bin/bash
docker logs -t tb-8002 2>&1 | grep -a tensor? | grep -oP '.*?(?= \- \- )' &> /tmp/tb-8002.log
# https://ipinfo.io/tools/map
