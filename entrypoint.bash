#!/bin/bash

source /opt/ros/jazzy/setup.bash
source ws/install/setup.bash
if [ "${RUN}" == "true" ]; then
    if [[ "${BASESTATION}" == "true" ]]; then
        ros2 launch rtk_correction broadcaster.launch.py \
            basestation_rajant_ip:=${BASESTATION_RAJANT_IP} \
            wifi_interface:=${WIFI_INTERFACE} \
            rtk_port:=${RTK_PORT} \
            wifi_info_port:=${WIFI_INFO_PORT} & 
        
    elif [[ "${BASESTATION}" == "false" ]]; then
        ros2 launch rtk_correction receiver.launch.py \
            basestation_rajant_ip:=${BASESTATION_RAJANT_IP} \
            basestation_wifi_ip:=${BASESTATION_WIFI_IP} \
            rtk_port:=${RTK_PORT} \
            wifi_info_port:=${WIFI_INFO_PORT} & 
    else
        echo "Make sure BASESTATION .env variable is set to true or false"
        exit 1
    fi
fi
