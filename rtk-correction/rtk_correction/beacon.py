#!/usr/bin/env python3
"""Small helpers for the WiFi fallback path used by the RTK broadcaster/receiver."""

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple

WIFI_INFO_PREFIX = "RTK_WIFI_INFO"
BEACON_PREFIX = "RTK_BEACON"


def parse_beacon_message(data: bytes) -> Optional[Tuple[str, int]]:
    try:
        prefix, ip, port_str = data.decode().split(":")
        port = int(port_str)
    except (TypeError, ValueError, UnicodeDecodeError):
        return None
    if prefix != BEACON_PREFIX:
        return None
    return ip, port


def parse_wifi_info_message(data: bytes) -> Optional[Tuple[str, int]]:
    try:
        prefix, ip, port_str = data.decode().split(":")
        port = int(port_str)
    except (TypeError, ValueError, UnicodeDecodeError):
        return None
    if prefix != WIFI_INFO_PREFIX:
        return None
    return ip, port


def scan_subnet(cidr: str, port: int, timeout: float = 0.3, max_workers: int = 64) -> Optional[str]:
    """Try every host in a subnet and return the first one that answers on `port`."""

    def try_host(ip: str) -> Optional[str]:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return ip
        except OSError:
            return None

    hosts = [str(ip) for ip in ipaddress.ip_network(cidr, strict=False).hosts()]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(try_host, ip): ip for ip in hosts}
        for future in as_completed(futures):
            result = future.result()
            if result:
                for other in futures:
                    other.cancel()
                return result
    return None
