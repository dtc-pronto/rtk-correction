#!/usr/bin/env python3
# Base station broadcaster.
#
# It sends the same RTK data stream on both Rajant and WiFi over the same
# `rtk_port` parameter. It also sends the WiFi IP over Rajant on a separate
# `wifi_info_port` so the receiver can learn the WiFi path without broadcast
# or a subnet scan by default.

import re
import subprocess
from typing import Optional

import rclpy
from rclpy.node import Node
import serial
import zmq
from pyrtcm import RTCMReader

from rtk_correction.beacon import WIFI_INFO_PREFIX

INET_RE = re.compile(r"inet\s+(\d+\.\d+\.\d+\.\d+)")

def get_interface_ipv4(interface: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["ip", "-4", "addr", "show", "dev", interface],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    match = INET_RE.search(result.stdout)
    return match.group(1) if match else None

class Basestation(Node):
    def __init__(self):
        super().__init__("rtk_broadcaster")

        self.declare_parameter("basestation_rajant_ip", "10.10.10.10")
        self.declare_parameter("rtk_port", 7501)
        self.declare_parameter("wifi_info_port", 7502)
        self.declare_parameter("wifi_interface", "wlan0")

        self.basestation_rajant_ip = self.get_parameter("basestation_rajant_ip").value
        self.rtk_port = self.get_parameter("rtk_port").value
        self.wifi_info_port = self.get_parameter("wifi_info_port").value
        self.wifi_interface = self.get_parameter("wifi_interface").value

        self.context_ = zmq.Context()

        self.rajant_socket = self.context_.socket(zmq.PUB)
        try:
            self.rajant_socket.bind(f"tcp://{self.basestation_rajant_ip}:{self.rtk_port}")
            self.get_logger().info(f"[RTK] Rajant PUB bound at {self.basestation_rajant_ip}:{self.rtk_port}")
        except zmq.ZMQError as e:
            self.get_logger().error(f"[RTK] Could not bind Rajant socket: {e}")
            self.rajant_socket = None

        self.wifi_socket = None
        self.wifi_info_socket = None
        self.wifi_ip = get_interface_ipv4(self.wifi_interface)

        if self.wifi_ip:
            self.wifi_socket = self.context_.socket(zmq.PUB)
            try:
                self.wifi_socket.bind(f"tcp://{self.wifi_ip}:{self.rtk_port}")
                self.get_logger().info(f"[RTK] WiFi PUB bound at {self.wifi_ip}:{self.rtk_port}")
            except zmq.ZMQError as e:
                self.get_logger().error(f"[RTK] Could not bind WiFi socket: {e}")
                self.wifi_socket = None
        else:
            self.get_logger().warn(
                f"[RTK] No IPv4 address on '{self.wifi_interface}' -- "
                "WiFi RTK will not be available this run"
            )

        if self.basestation_rajant_ip:
            self.wifi_info_socket = self.context_.socket(zmq.PUB)
            try:
                self.wifi_info_socket.bind(f"tcp://{self.basestation_rajant_ip}:{self.wifi_info_port}")
                self.get_logger().info(
                    f"[RTK] WiFi-info PUB bound at {self.basestation_rajant_ip}:{self.wifi_info_port}"
                )
            except zmq.ZMQError as e:
                self.get_logger().error(f"[RTK] Could not bind WiFi-info socket: {e}")
                self.wifi_info_socket = None

    def broadcast(self):
        with serial.Serial('/dev/ublox', 38400, timeout=3) as stream:
            rtr = RTCMReader(stream)
            self.get_logger().info("[RTK] Connected to GPS")
            while rclpy.ok():
                # Read data from RTK Facet
                raw_data, parsed_data = rtr.read()
                if parsed_data is None:
                    continue
                self.get_logger().debug("[RTK] Still recieving data from rtk facet",
                                        throttle_duration_sec=5.0)
                
                if self.rajant_socket is not None:
                    # Send the RTK corrections over Rajant
                    try:
                        self.rajant_socket.send(raw_data)
                        self.get_logger().info("[RTK] Beginning to broadcast RTK corrections over rajant",once=True)
                        self.get_logger().debug("[RTK] Still broadcasting RTK corrections over rajant",
                                                 throttle_duration_sec=5.0)
                    except zmq.ZMQError as e:
                        self.get_logger().error(f"[RTK] Rajant send failed: {e}")

                    # Send the WiFi IP over Rajant so receivers can learn it
                    if self.wifi_ip and self.wifi_info_socket is not None:
                        info = f"{WIFI_INFO_PREFIX}:{self.wifi_ip}:{self.rtk_port}".encode()
                        try:
                            self.wifi_info_socket.send(info)
                            self.get_logger().debug("[RTK] Still broadcasting my WiFi info over Rajant",
                                                    throttle_duration_sec=5.0)
                        except zmq.ZMQError as e:
                            self.get_logger().error(f"[RTK] WiFi-info send failed: {e}")
                if self.wifi_socket is not None:
                    # Send the RTK corrections over WiFi
                    try:
                        self.wifi_socket.send(raw_data)
                        self.get_logger().debug("[RTK] Still broadcasting RTK corrections over WiFi",
                                                throttle_duration_sec=5.0)
                    except zmq.ZMQError as e:
                        self.get_logger().error(f"[RTK] WiFi send failed: {e}")

                

    def destroy_node(self):
        if self.rajant_socket is not None:
            self.rajant_socket.close()
        if self.wifi_socket is not None:
            self.wifi_socket.close()
        if self.wifi_info_socket is not None:
            self.wifi_info_socket.close()
        self.context_.term()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = Basestation()
    try:
        node.broadcast()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()