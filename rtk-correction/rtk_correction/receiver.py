#!/usr/bin/env python3
# Rover receiver.
#
# Rajant is the primary path and is always connected to the known static IP.
# The broadcaster also sends the WiFi IP over a separate Rajant control port
# and pushes the same RTK data over WiFi on the same `rtk_port`.
#
# The receiver prefers Rajant and falls back to WiFi only after the Rajant
# stream has been silent long enough. If no WiFi IP is known yet, it scans the
# robot subnet for a host that is answering on the RTK port.

import threading
import time

import rclpy
from rclpy.node import Node
from rtcm_msgs.msg import Message
import zmq

from rtk_correction.beacon import parse_wifi_info_message


class RTKReceiver(Node):
    def __init__(self):
        super().__init__('rtk_receiver')

        # Declare parameters
        self.declare_parameter("rajant_ip", "10.10.10.10")
        self.declare_parameter("wifi_ip", "192.168.129.100")
        
        self.declare_parameter("rtk_port", 7501)
        self.declare_parameter("wifi_info_port", 7502)
        
        self.declare_parameter("rajant_stale_timeout", 5.0)
        self.declare_parameter("wifi_stale_timeout", 5.0)
        
        self.declare_parameter("rajant_probe_interval", 4.0)
        self.declare_parameter("wifi_probe_interval", 4.0)

        # Get parameters
        self.rajant_ip = self.get_parameter("rajant_ip").value
        self.wifi_ip = self.get_parameter("wifi_ip").value

        self.rtk_port = self.get_parameter("rtk_port").value
        self.wifi_info_port = self.get_parameter("wifi_info_port").value
        
        self.rajant_stale_timeout = self.get_parameter("rajant_stale_timeout").value
        self.wifi_stale_timeout = self.get_parameter("wifi_stale_timeout").value
        
        self.rajant_probe_interval = self.get_parameter("rajant_probe_interval").value
        self.wifi_probe_interval = self.get_parameter("wifi_probe_interval").value
        
        self.context_ = zmq.Context()

        # Set up socket for Rajant RTK corrections
        self.rajant_socket = self.context_.socket(zmq.SUB)
        self.rajant_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.rajant_endpoint = f"tcp://{self.rajant_ip}:{self.rtk_port}"
        self.rajant_socket.connect(self.rajant_endpoint)
        self.get_logger().info(f"[RTK] Rajant connection ready at {self.rajant_endpoint}")

        # Set up socket for WiFi info
        self.wifi_info_socket = self.context_.socket(zmq.SUB)
        self.wifi_info_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.wifi_info_socket.connect(f"tcp://{self.rajant_ip}:{self.wifi_info_port}")
        self.get_logger().info(
            f"[RTK] Listening for WiFi discovery on {self.rajant_ip}:{self.wifi_info_port}"
        )
        
        # Set up socket for WiFi RTK corrections if a WiFi IP is already known
        self.wifi_socket = None
        if(self.wifi_ip is not None and self.wifi_ip != ""):
            self._set_wifi_endpoint(self.wifi_ip, self.rtk_port)        
        
        self._rajant_connected = True
        self._wifi_connected = False
        
        self._last_rajant_msg = 0.0
        self._last_wifi_msg = 0.0
        
        self._last_rajant_probe = 0.0
        self._last_wifi_probe = 0.0

        self.pub = self.create_publisher(Message, '/rtcm', 1)

    def _set_wifi_endpoint(self, ip: str, port: int):
        try:
            endpoint = f"tcp://{ip}:{port}"
            
            if self.wifi_socket is not None:
                        try:
                            self.wifi_socket.close()
                        except Exception:
                            pass

            self.wifi_ip = ip
            self.wifi_socket = self.context_.socket(zmq.SUB)
            self.wifi_socket.setsockopt_string(zmq.SUBSCRIBE, "")
            self.wifi_socket.connect(endpoint)
            self.get_logger().info(f"[RTK] WiFi fallback connection ready at {endpoint}")
        except Exception as e:
            self.get_logger().error(f"[RTK] Failed to set WiFi endpoint {ip}:{port}: {e}")

    def _try_loading_wifi_info(self):
        try:
            msg = self.wifi_info_socket.recv(flags=zmq.NOBLOCK)
        except zmq.Again:
            return

        parsed = parse_wifi_info_message(msg)
        if parsed is None:
            return
        ip, port = parsed
        if ip and port:
            self._set_wifi_endpoint(ip, port)
            

    def _publish_rtcm(self, rtcm_raw: bytes):
        self.get_logger().info("[RTK] Received corrections", once=True)

        msg = Message()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.message = rtcm_raw
        self.pub.publish(msg)
        
    def _probe_wifi(self):
        now = time.monotonic()
        if self.wifi_socket is None:
            return
        if now - self._last_wifi_probe >= self.wifi_probe_interval:
            self._last_wifi_probe = now
            try:
                rtcm_raw = self.wifi_socket.recv(flags=zmq.NOBLOCK)
                self._publish_rtcm(rtcm_raw)
                self._last_wifi_msg = now
                self.get_logger().info("[RTK] WiFi connection recovered")
                self._wifi_connected = True
            except zmq.Again:
                self.get_logger().warn(f"Probed wifi but no response; "
                                       f"WiFi has been silent for {self.wifi_probe_interval}s;")

    def _probe_rajant(self):
            now = time.monotonic()
            if self.rajant_socket is None:
                return
            if now - self._last_rajant_probe >= self.rajant_probe_interval:
                self._last_rajant_probe = now
                try:
                    rtcm_raw = self.rajant_socket.recv(flags=zmq.NOBLOCK)
                    self._publish_rtcm(rtcm_raw)
                    self._last_rajant_msg = now
                    self.get_logger().info("[RTK] Rajant connection recovered")
                    self._rajant_connected = True
                except zmq.Again:
                    self.get_logger().warn(f"Probed rajent but no response; "
                                           f"Rajant has been silent for {self.rajant_probe_interval}s;")

    @staticmethod
    def _read_socket(socket):
        try:
            return socket.recv(flags=zmq.NOBLOCK)
        except zmq.Again:
            return None

    def _read_rajant(self, now):
        rtcm_raw = self._read_socket(self.rajant_socket)
        if rtcm_raw is None:
            return False

        self._last_rajant_msg = now
        self._rajant_monitor_started = now
        if self._rajant_state != "up":
            message = "recovered" if self._rajant_state == "down" else "established"
            self.get_logger().info(f"[RTK] Rajant connection {message}")
        self._rajant_state = "up"
        self._publish_rtcm(rtcm_raw)
        return True

    def _probe_rajant(self, now):
        if now - self._last_rajant_probe < self.rajant_probe_interval:
            return False

        self._last_rajant_probe = now
        rtcm_raw = self._read_socket(self.rajant_socket)
        if rtcm_raw is None:
            return False

        self._last_rajant_msg = now
        self._rajant_monitor_started = now
        self.get_logger().info("[RTK] Rajant connection recovered; switching from WiFi")
        self._rajant_state = "up"
        self._using_wifi = False
        self._publish_rtcm(rtcm_raw)
        return True

    def _read_wifi(self, now):
        if not self._using_wifi or self.wifi_socket is None:
            return False

        rtcm_raw = self._read_socket(self.wifi_socket)
        if rtcm_raw is None:
            return False

        self._last_wifi_msg = now
        if self._wifi_state != "up":
            self.get_logger().info("[RTK] WiFi connection established")
        self._wifi_state = "up"
        self._publish_rtcm(rtcm_raw)
        return True

    def _check_rajant_timeout(self, now):
        last_seen = self._last_rajant_msg or self._rajant_monitor_started
        if self._using_wifi or now - last_seen <= self.rajant_stale_timeout:
            return

        if self._rajant_state == "up":
            self.get_logger().warn("[RTK] Rajant connection lost")
        if self._rajant_state != "down":
            self.get_logger().warn(
                f"[RTK] Rajant has been silent for {self.rajant_stale_timeout}s; "
                "trying WiFi fallback"
            )
        self._rajant_state = "down"

        self._using_wifi = self.wifi_socket is not None
        if self.wifi_socket is None:
            self._maybe_scan_subnet()

    def _check_wifi_timeout(self, now):
        if not self._using_wifi or self._last_wifi_msg is None:
            return
        if now - self._last_wifi_msg <= self.wifi_stale_timeout:
            return

        if self._wifi_state == "up":
            self.get_logger().warn("[RTK] WiFi connection lost")
        self._wifi_state = "down"
        self.get_logger().warn(
            f"[RTK] WiFi has been silent for {self.wifi_stale_timeout}s"
        )
        self._last_wifi_msg = None

    def _on_rajant_health_change(self, healthy: bool):
        if healthy:
            self.get_logger().info("[RTK] Rajant recovered; receiver will switch back when ready")
        else:
            self.get_logger().warn("[RTK] Rajant is unhealthy; receiver will use WiFi if available")

    def _select_socket(self):
        rajant_healthy = self.health_monitor is None or self.health_monitor.healthy
        desired_path = "rajant"
        if not rajant_healthy and self.wifi_socket is not None:
            desired_path = "wifi"

        if desired_path != self._active_path:
            self._active_path = desired_path
            self.get_logger().info(f"[RTK] Active correction path: {desired_path}")

        return self.rajant_socket if self._active_path == "rajant" else self.wifi_socket

    def receive(self):
        while rclpy.ok():
            self._try_loading_wifi_info()
            now = time.monotonic()
            
            if(self._rajant_connected and self.rajant_socket is not None):
                try:
                    rtcm_raw = self.rajant_socket.recv(flags=zmq.NOBLOCK)
                    self._last_rajant_msg = now
                    self._publish_rtcm(rtcm_raw)
                except zmq.Again:
                    if now - self._last_rajant_msg > self.rajant_stale_timeout:
                        self._rajant_connected = False
                        self.get_logger().warn("[RTK] Rajant connection lost")
            elif(self._wifi_connected and self.wifi_socket is not None):
                self._probe_rajant()
                if not self._rajant_connected:
                    try:
                        rtcm_raw = self.wifi_socket.recv(flags=zmq.NOBLOCK)
                        self._last_wifi_msg = now
                        self._publish_rtcm(rtcm_raw)
                    except zmq.Again:
                        if now - self._last_wifi_msg > self.wifi_stale_timeout:
                            self._wifi_connected = False
                            self.get_logger().warn("[RTK] WiFi connection lost")
            else:
                self._probe_rajant()
                self._probe_wifi()
                
            time.sleep(0.1)

        self.rajant_socket.close()
        if self.wifi_socket is not None:
            self.wifi_socket.close()
        self.wifi_info_socket.close()
        self.context_.term()

    def destroy_node(self):
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RTKReceiver()
    try:
        node.receive()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
