#!/usr/bin/env python3
# rover receiver
#
# Connects to Rajant's known, static address immediately (no discovery
# needed there). In the background it also listens for WiFi beacons from
# the broadcaster and keeps a second connection ready ("warm standby") --
# if no beacon shows up within a timeout (e.g. broadcast is being blocked
# on the network), it falls back to scanning a known subnet block for the
# broadcaster instead.
#
# A single ZMQ SUB socket can be connect()-ed to more than one endpoint at
# once and will receive from whichever one is actually sending -- so once
# both Rajant and WiFi are connected, no explicit "which one do I trust"
# logic is needed here. The broadcaster is the one deciding when to also
# send over WiFi (once its own Rajant health check says Rajant is down),
# so the receiver just forwards whatever arrives.

import threading
import time

import rclpy
from rclpy.node import Node
from rtcm_msgs.msg import Message
import zmq

from rtk_correction.beacon import BeaconListener, scan_subnet


class RTKReceiver(Node):

    def __init__(self):
        super().__init__('rtk_receiver')

        self.declare_parameter("ip", "10.10.10.10")
        self.declare_parameter("port", 7507)

        self.declare_parameter("beacon_port", 7508)
        self.declare_parameter("beacon_wait_timeout", 8.0)
        self.declare_parameter("wifi_scan_subnet", "")  # e.g. "192.168.1.0/24"; "" disables scan fallback

        self.declare_parameter("stale_timeout", 5.0)

        rajant_ip = self.get_parameter("ip").value
        port = self.get_parameter("port").value
        self.port = port
        self.beacon_wait_timeout = self.get_parameter("beacon_wait_timeout").value
        self.wifi_scan_subnet = self.get_parameter("wifi_scan_subnet").value
        self.stale_timeout = self.get_parameter("stale_timeout").value

        self.context_ = zmq.Context()
        self.socket = self.context_.socket(zmq.SUB)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")

        self.rajant_endpoint = f"tcp://{rajant_ip}:{port}"
        self.socket.connect(self.rajant_endpoint)
        self.get_logger().info(f"[RTK] Connected to Rajant broadcaster at {self.rajant_endpoint}")

        # WiFi is discovered asynchronously (beacon thread / scan thread);
        # the actual socket.connect()/disconnect() calls happen on the main
        # thread inside receive(), since ZMQ sockets aren't meant to be
        # driven from multiple threads at once. `_wifi_pending` is how the
        # background threads hand a newly-discovered address to the main
        # loop.
        self._pending_lock = threading.Lock()
        self._wifi_pending = None
        self.wifi_endpoint = None
        self._scan_started = False
        self._startup_time = time.monotonic()

        self.beacon_listener = BeaconListener(
            beacon_port=self.get_parameter("beacon_port").value,
            on_discover=self._queue_wifi_endpoint,
            logger=self.get_logger(),
        )
        self.beacon_listener.start()

        self.pub = self.create_publisher(Message, '/rtcm', 1)

        self._last_msg_time = None
        self._stale_logged = False

    def _queue_wifi_endpoint(self, ip: str, port: int):
        with self._pending_lock:
            self._wifi_pending = f"tcp://{ip}:{port}"

    def _maybe_start_scan_fallback(self):
        if self._scan_started or not self.wifi_scan_subnet or self.wifi_endpoint:
            return
        if time.monotonic() - self._startup_time < self.beacon_wait_timeout:
            return

        self._scan_started = True
        self.get_logger().warn(
            f"[RTK] No beacon heard after {self.beacon_wait_timeout}s -- "
            f"falling back to scanning {self.wifi_scan_subnet} for the broadcaster"
        )

        def scan_and_queue():
            found = scan_subnet(self.wifi_scan_subnet, self.port)
            if found:
                self.get_logger().info(f"[RTK] Scan found broadcaster at {found}")
                self._queue_wifi_endpoint(found, self.port)
            else:
                self.get_logger().warn(f"[RTK] Scan of {self.wifi_scan_subnet} found nothing")

        threading.Thread(target=scan_and_queue, daemon=True).start()

    def _apply_pending_wifi_endpoint(self):
        with self._pending_lock:
            new_endpoint = self._wifi_pending
            self._wifi_pending = None

        if new_endpoint is None or new_endpoint == self.wifi_endpoint:
            return

        if self.wifi_endpoint is not None:
            try:
                self.socket.disconnect(self.wifi_endpoint)
            except zmq.ZMQError:
                pass

        self.socket.connect(new_endpoint)
        self.wifi_endpoint = new_endpoint
        self.get_logger().info(f"[RTK] WiFi standby connection ready at {new_endpoint}")

    def receive(self):
        while rclpy.ok():
            self._apply_pending_wifi_endpoint()
            self._maybe_start_scan_fallback()

            try:
                rtcm_raw = self.socket.recv(flags=zmq.NOBLOCK)
                self.get_logger().info("[RTK] Recieved corrections", once=True)

                self._last_msg_time = time.monotonic()
                if self._stale_logged:
                    self.get_logger().info("[RTK] Corrections resumed")
                    self._stale_logged = False

                msg = Message()
                msg.header.stamp = self.get_clock().now().to_msg()
                msg.message = rtcm_raw
                self.pub.publish(msg)

            except zmq.Again:
                self._check_stale()

            time.sleep(0.1)

        self.socket.close()
        self.context_.term()

    def _check_stale(self):
        if self._last_msg_time is None or self._stale_logged:
            return
        if time.monotonic() - self._last_msg_time > self.stale_timeout:
            self._stale_logged = True
            self.get_logger().warn(
                f"[RTK] No corrections received for over {self.stale_timeout}s -- "
                "link (Rajant and WiFi) may be down"
            )

    def destroy_node(self):
        self.beacon_listener.stop()
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
