#!/bin/bash

docker run --rm -it \
    --network=host \
    --privileged \
    --entrypoint="" \
    -e RTK=true \
    -e RTK_IP=192.168.60.229 \
    -e RTK_PORT=7501 \
    --name "dtc-platform-$(hostname)-rtk" \
    "dtc-platform-$(hostname):rtk" \
    bash