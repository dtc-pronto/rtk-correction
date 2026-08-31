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

from rtk_correction.beacon import parse_wifi_info_message, scan_subnet


class RTKReceiver(Node):
    def __init__(self):
        super().__init__('rtk_receiver')

        self.declare_parameter("rajant_ip", "10.10.10.10")
        self.declare_parameter("rtk_port", 7501)
        self.declare_parameter("wifi_info_port", 7502)
        self.declare_parameter("wifi_scan_subnet", "")
        self.declare_parameter("rajant_stale_timeout", 5.0)
        self.declare_parameter("wifi_stale_timeout", 5.0)
        self.declare_parameter("rajant_probe_interval", 2.0)

        self.rajant_ip = self.get_parameter("rajant_ip").value
        self.rtk_port = self.get_parameter("rtk_port").value
        self.wifi_info_port = self.get_parameter("wifi_info_port").value
        self.wifi_scan_subnet = self.get_parameter("wifi_scan_subnet").value
        self.rajant_stale_timeout = self.get_parameter("rajant_stale_timeout").value
        self.wifi_stale_timeout = self.get_parameter("wifi_stale_timeout").value
        self.rajant_probe_interval = self.get_parameter("rajant_probe_interval").value

        self.context_ = zmq.Context()

        self.rajant_socket = self.context_.socket(zmq.SUB)
        self.rajant_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.rajant_endpoint = f"tcp://{self.rajant_ip}:{self.rtk_port}"
        self.rajant_socket.connect(self.rajant_endpoint)
        self.get_logger().info(f"[RTK] Connected to Rajant broadcaster at {self.rajant_endpoint}")

        self.wifi_info_socket = self.context_.socket(zmq.SUB)
        self.wifi_info_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.wifi_info_socket.connect(f"tcp://{self.rajant_ip}:{self.wifi_info_port}")
        self.get_logger().info(
            f"[RTK] Listening for WiFi discovery on {self.rajant_ip}:{self.wifi_info_port}"
        )
        if not self.wifi_scan_subnet:
            self.get_logger().warn(
                "[RTK] wifi_scan_subnet is empty; WiFi cannot be discovered while "
                "both Rajant and the WiFi-info path are unavailable"
            )

        self.wifi_socket = None
        self.wifi_ip = None
        self.wifi_port = None
        self._wifi_scan_started = False
        self._wifi_scan_retry_at = 0.0
        self._last_rajant_msg = None
        self._last_wifi_msg = None
        self._last_pub_time = None
        self._stale_logged = False
        self._using_wifi = False
        self._last_rajant_probe = 0.0
        self._rajant_state = "unknown"
        self._wifi_state = "unknown"
        self._rajant_monitor_started = time.monotonic()

        self.pub = self.create_publisher(Message, '/rtcm', 1)

    def _set_wifi_endpoint(self, ip: str, port: int):
        endpoint = f"tcp://{ip}:{port}"
        if self.wifi_socket is not None and self.wifi_ip == ip and self.wifi_port == port:
            return

        if self.wifi_socket is not None:
            try:
                self.wifi_socket.close()
            except Exception:
                pass

        self.wifi_ip = ip
        self.wifi_port = port
        self._wifi_state = "unknown"
        self.wifi_socket = self.context_.socket(zmq.SUB)
        self.wifi_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.wifi_socket.connect(endpoint)
        self.get_logger().info(f"[RTK] WiFi fallback connection ready at {endpoint}")

    def _maybe_load_wifi_info(self):
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

    def _maybe_scan_subnet(self):
        now = time.monotonic()
        if (
            not self.wifi_scan_subnet
            or self.wifi_ip
            or self._wifi_scan_started
            or now < self._wifi_scan_retry_at
        ):
            return

        subnet = self.wifi_scan_subnet
        self._wifi_scan_started = True
        self.get_logger().warn(
            f"[RTK] No WiFi info known; scanning {subnet} for RTK data on port {self.rtk_port}"
        )

        def worker():
            found = scan_subnet(subnet, self.rtk_port)
            self._wifi_scan_started = False
            if found:
                self.get_logger().info(f"[RTK] Scan found WiFi broadcaster at {found}:{self.rtk_port}")
                self._set_wifi_endpoint(found, self.rtk_port)
            else:
                self.get_logger().warn(f"[RTK] Scan of {subnet} found nothing")
                self._wifi_scan_retry_at = time.monotonic() + self.rajant_stale_timeout

        threading.Thread(target=worker, daemon=True).start()

    def _publish_rtcm(self, rtcm_raw: bytes):
        self.get_logger().info("[RTK] Received corrections", once=True)

        self._last_pub_time = time.monotonic()
        if self._stale_logged:
            self.get_logger().info("[RTK] Corrections resumed")
            self._stale_logged = False

        msg = Message()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.message = rtcm_raw
        self.pub.publish(msg)

    def _check_stale(self):
        if self._last_pub_time is None or self._stale_logged:
            return
        if time.monotonic() - self._last_pub_time > self.wifi_stale_timeout:
            self._stale_logged = True
            self.get_logger().warn(
                f"[RTK] No corrections received for over {self.wifi_stale_timeout}s -- "
                "Rajant and WiFi may be down"
            )

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

    def receive(self):
        while rclpy.ok():
            self._maybe_load_wifi_info()
            now = time.monotonic()

            if self._using_wifi:
                received = self._probe_rajant(now) or self._read_wifi(now)
            else:
                received = self._read_rajant(now)

            if not received:
                self._check_rajant_timeout(now)
                self._check_wifi_timeout(now)

            self._check_stale()
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
