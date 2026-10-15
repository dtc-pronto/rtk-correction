"""Receiver discovery regressions; ROS is stubbed for host-side tests."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def receiver(monkeypatch):
    rclpy = ModuleType("rclpy")
    node = ModuleType("rclpy.node")
    node.Node = object
    messages = ModuleType("rtcm_msgs.msg")
    messages.Message = object
    for name, module in {"rclpy": rclpy, "rclpy.node": node,
                         "rtcm_msgs": ModuleType("rtcm_msgs"),
                         "rtcm_msgs.msg": messages}.items():
        monkeypatch.setitem(sys.modules, name, module)
    path = Path(__file__).parents[1] / "rtk_correction/receiver.py"
    spec = importlib.util.spec_from_file_location("receiver_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receiver = module.RTKReceiver.__new__(module.RTKReceiver)
    receiver.context_ = Mock()
    receiver.wifi_socket = None
    receiver.wifi_endpoint = None
    receiver.get_logger = Mock(return_value=Mock())
    return receiver


def test_repeated_discovery_preserves_subscription(receiver):
    for _ in range(50):
        receiver._set_wifi_endpoint("192.168.129.10", 7501)
    receiver.context_.socket.assert_called_once()
    receiver.wifi_socket.connect.assert_called_once_with("tcp://192.168.129.10:7501")
    receiver.wifi_socket.close.assert_not_called()
    receiver.get_logger().info.assert_called_once()


@pytest.mark.parametrize("ip,port", [("192.168.129.20", 7501), ("192.168.129.10", 7507)])
def test_changed_discovery_replaces_subscription(receiver, ip, port):
    old_socket, new_socket = Mock(), Mock()
    receiver.context_.socket.side_effect = [old_socket, new_socket]
    receiver._set_wifi_endpoint("192.168.129.10", 7501)
    receiver._set_wifi_endpoint(ip, port)
    old_socket.close.assert_called_once()
    new_socket.connect.assert_called_once_with(f"tcp://{ip}:{port}")
    assert receiver.wifi_socket is new_socket


def test_failed_endpoint_change_preserves_working_subscription_and_can_retry(receiver):
    old_socket, failed_socket, retry_socket = Mock(), Mock(), Mock()
    receiver.context_.socket.side_effect = [old_socket, failed_socket, retry_socket]
    receiver._set_wifi_endpoint("192.168.129.10", 7501)
    failed_socket.connect.side_effect = RuntimeError("connection failed")
    receiver._set_wifi_endpoint("192.168.129.20", 7501)
    failed_socket.close.assert_called_once()
    old_socket.close.assert_not_called()
    assert receiver.wifi_socket is old_socket
    assert receiver.wifi_ip == "192.168.129.10"
    receiver.get_logger().error.assert_called_once()
    receiver._set_wifi_endpoint("192.168.129.20", 7501)
    assert receiver.wifi_socket is retry_socket
