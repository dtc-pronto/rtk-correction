#!/bin/bash

HOSTNAME=$(hostname)

UGVS=("phobos" "deimos" "titania" "oberon" "aphrodite" "ares")
UAVS=("dione")
BASESTATIONS=("neptune" "turing")

source /opt/ros/jazzy/setup.bash
source ws/install/setup.bash
if [ "${RTK}" == "true" ]; then
    if [[ " ${UGVS[*]} " == *" $HOSTNAME "* ]]; then
        ros2 launch rtk_correction receiver.launch.py \
            rajant_ip:=${RAJANT_IP} \
            wifi_ip:=${WIFI_IP} \
            rtk_port:=${RTK_PORT} \
            wifi_info_port:=${WIFI_INFO_PORT} &
    
    elif [[ " ${UAVS[*]} " == *" $HOSTNAME "* ]]; then
        ros2 launch rtk_correction receiver.launch.py \
            rajant_ip:=${RAJANT_IP} \
            wifi_ip:=${WIFI_IP} \
            rtk_port:=${RTK_PORT} \
            wifi_info_port:=${WIFI_INFO_PORT} &
    
    elif [[ " ${BASESTATIONS[*]} " == *" $HOSTNAME "* ]]; then
        ros2 launch rtk_correction broadcaster.launch.py \
            rajant_ip:=${RAJANT_IP} \
            wifi_interface:=${WIFI_INTERFACE} \
            rtk_port:=${RTK_PORT} \
            wifi_info_port:=${WIFI_INFO_PORT} & 
    else
        echo "Error: Hostname '$HOSTNAME' not recognized."
        exit 1
    fi
fi
