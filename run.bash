#!/bin/bash

docker run --rm -it \
    --network=host \
    --privileged \
    --entrypoint="" \
    -e RTK=true \
    -e RAJANT_IP=10.10.10.10 \
    -e WIFI_IP=192.168.60.229 \
    -e RTK_PORT=7501 \
    -e WIFI_INFO_PORT=7502 \
    -e WIFI_INTERFACE=wlp1s0f0 \
    --name "dtc-platform-$(hostname)-rtk" \
    "dtc-platform-$(hostname):rtk" \
    bash