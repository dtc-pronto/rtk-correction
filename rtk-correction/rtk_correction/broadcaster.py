#!/usr/bin/env python3
# base station broadcaster
#
# Reads RTCM correction bytes off the GPS serial connection (via pyrtcm)
# and publishes them over ZMQ. Rajant is the primary path and is always
# bound at its known, static address -- no health check is needed to
# decide whether to use it, only to decide when corrections also need to
# go out over WiFi.
#
# WiFi is a warm standby: its address isn't known ahead of time (it's
# handed out by whatever network is present), so it's discovered at
# runtime from the OS, bound as a second PUB socket, and continuously
# beaconed so the receiver already has a ready connection *before* Rajant
# ever fails. Real correction data is only sent over it once the Rajant
# health check says Rajant is down -- this avoids doubling the correction
# traffic for the entire run just to cover an occasional fallback.

import rclpy
from rclpy.node import Node
import serial
import zmq
from pyrtcm import RTCMReader

from rtk_correction.beacon import BeaconSender
from rtk_correction.network_health import HealthMonitor, get_interface_ipv4


class Basestation(Node):
    def __init__(self):
        super().__init__("rtk_broadcaster")

        # -- Rajant (primary, static address) --
        self.declare_parameter("ip", "10.10.10.10")
        self.declare_parameter("port", 7507)
        self.declare_parameter("rajant_interface", "rajant")

        # -- WiFi (warm standby, discovered at runtime) --
        self.declare_parameter("wifi_interface", "wlan0")
        self.declare_parameter("beacon_port", 7508)
        self.declare_parameter("beacon_interval", 1.5)

        # -- Health check (pings a known peer over the Rajant interface) --
        self.declare_parameter("ping_target", "")
        self.declare_parameter("ping_interval", 1.5)
        self.declare_parameter("ping_timeout", 1.0)
        self.declare_parameter("fail_threshold", 3)
        self.declare_parameter("recover_threshold", 3)

        self.rajant_ip = self.get_parameter("ip").value
        self.port = self.get_parameter("port").value
        self.rajant_interface = self.get_parameter("rajant_interface").value
        self.wifi_interface = self.get_parameter("wifi_interface").value
        self.beacon_port = self.get_parameter("beacon_port").value
        self.beacon_interval = self.get_parameter("beacon_interval").value
        self.ping_target = self.get_parameter("ping_target").value

        self.context_ = zmq.Context()

        # Rajant socket: always bound, this is the main path.
        self.rajant_socket = self.context_.socket(zmq.PUB)
        try:
            self.rajant_socket.bind(f"tcp://{self.rajant_ip}:{self.port}")
            self.get_logger().info(f"[RTK] Rajant PUB bound at {self.rajant_ip}:{self.port}")
        except zmq.ZMQError as e:
            self.get_logger().error(f"[RTK] Could not bind Rajant socket: {e}")
            self.rajant_socket = None

        # WiFi socket: bound if the interface currently has an address.
        # If it doesn't (radio not associated yet, etc.), skip it -- the
        # health check / beacon simply won't have anything to offer until
        # a WiFi address shows up on a later restart.
        self.wifi_socket = None
        self.beacon_sender = None
        wifi_ip = get_interface_ipv4(self.wifi_interface)
        if wifi_ip:
            self.wifi_socket = self.context_.socket(zmq.PUB)
            try:
                self.wifi_socket.bind(f"tcp://{wifi_ip}:{self.port}")
                self.get_logger().info(f"[RTK] WiFi PUB bound at {wifi_ip}:{self.port}")
                self.beacon_sender = BeaconSender(
                    advertise_ip=wifi_ip,
                    advertise_port=self.port,
                    beacon_port=self.beacon_port,
                    source_ip=wifi_ip,
                    interval=self.beacon_interval,
                    logger=self.get_logger(),
                )
                self.beacon_sender.start()
            except zmq.ZMQError as e:
                self.get_logger().error(f"[RTK] Could not bind WiFi socket: {e}")
                self.wifi_socket = None
        else:
            self.get_logger().warn(
                f"[RTK] No IPv4 address on '{self.wifi_interface}' -- "
                "WiFi standby not available this run"
            )

        # Health check: only meaningful if a ping target was configured.
        # Without one, Rajant is assumed healthy and WiFi is never used
        # for real data (still beaconed, just never selected) -- better to
        # be explicit about this than silently guess a target.
        self.health_monitor = None
        if self.ping_target:
            self.health_monitor = HealthMonitor(
                target=self.ping_target,
                interface=self.rajant_interface,
                interval=self.get_parameter("ping_interval").value,
                timeout=self.get_parameter("ping_timeout").value,
                fail_threshold=self.get_parameter("fail_threshold").value,
                recover_threshold=self.get_parameter("recover_threshold").value,
                logger=self.get_logger(),
            )
            self.health_monitor.start()
        else:
            self.get_logger().warn(
                "[RTK] No ping_target configured -- Rajant health is not being "
                "checked, so WiFi will never be used for corrections this run"
            )

    def broadcast(self):
        with serial.Serial('/dev/ublox', 38400, timeout=3) as stream:
            rtr = RTCMReader(stream)
            self.get_logger().info("[RTK] Connected to GPS")
            while rclpy.ok():
                raw_data, parsed_data = rtr.read()
                if parsed_data is None:
                    continue

                self.get_logger().info("[RTK] Broadcasting corrections", once=True)

                if self.rajant_socket is not None:
                    try:
                        self.rajant_socket.send(raw_data)
                    except zmq.ZMQError as e:
                        self.get_logger().error(f"[RTK] Rajant send failed: {e}")

                rajant_down = (
                    self.health_monitor is not None and not self.health_monitor.healthy
                )
                if rajant_down and self.wifi_socket is not None:
                    self.get_logger().warn(
                        "[RTK] Rajant unhealthy -- also sending corrections over WiFi",
                        once=True,
                    )
                    try:
                        self.wifi_socket.send(raw_data)
                    except zmq.ZMQError as e:
                        self.get_logger().error(f"[RTK] WiFi send failed: {e}")

    def destroy_node(self):
        if self.health_monitor is not None:
            self.health_monitor.stop()
        if self.beacon_sender is not None:
            self.beacon_sender.stop()
        if self.rajant_socket is not None:
            self.rajant_socket.close()
        if self.wifi_socket is not None:
            self.wifi_socket.close()
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
