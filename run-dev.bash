#!/bin/bash

docker run --rm -it \
    --network=host \
    --privileged \
    --entrypoint="" \
    -e RTK=true \
    --name dtc-platform-`hostname`-rtk \
    dtc-platform-`hostname`:rtk \
    bash
    
