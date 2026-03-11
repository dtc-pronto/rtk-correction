#!/bin/bash

HOSTNAME=$(hostname)

UGVS=("phobos" "deimos" "titania" "oberon" "aphrodite" "ares")
UAVS=("dione")
BASESTATIONS=("neptune" "turing")

source /opt/ros/jazzy/setup.bash
source ws/install/setup.bash
if [ "${RTK}" == "true" ]; then
    if [[ " ${UGVS[*]} " == *" $HOSTNAME "* ]]; then
        ros2 launch rtk_correction receiver.launch.py ip:=$IP port:=$PORT
    
    elif [[ " ${UAVS[*]} " == *" $HOSTNAME "* ]]; then
        ros2 launch rtk_correction receiver.launch.py ip:=$IP port:=$PORT
    
    elif [[ " ${BASESTATIONS[*]} " == *" $HOSTNAME "* ]]; then
        ros2 launch rtk_correction broadcaster.launch.py ip:=$IP port:=$PORT 
    else
        echo "Error: Hostname '$HOSTNAME' not recognized."
        exit 1
    fi
fi
