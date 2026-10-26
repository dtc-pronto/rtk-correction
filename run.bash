#!/bin/bash

docker run --rm -it \
    --network=host \
    --privileged \
    -e RUN="${RTK:-true}" \
    -e BASESTATION="${BASESTATION:-false}" \
    -e BASESTATION_RAJANT_IP="${BASESTATION_RAJANT_IP:-10.10.10.10}" \
    -e BASESTATION_WIFI_IP="${BASESTATION_WIFI_IP:-192.168.129.10}" \
    -e RTK_PORT="${RTK_PORT:-7501}" \
    -e WIFI_INFO_PORT="${WIFI_INFO_PORT:-7502}" \
    -e WIFI_INTERFACE="${WIFI_INTERFACE:-wlan0}" \
    --name "dtc-platform-$(hostname)-rtk" \
    "dtc-platform-$(hostname):rtk" \
    /home/dtc/entrypoint.bash