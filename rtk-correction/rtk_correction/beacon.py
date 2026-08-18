#!/usr/bin/env python3
"""
Discovery for the WiFi fallback path.

Rajant's address is static and known ahead of time, so it never needs any
of this. WiFi's address is handed out by whatever network is present
("the provided wifi" on field day), so the receiver has to learn it at
runtime. Two mechanisms are provided:

  - BeaconSender / BeaconListener: the broadcaster periodically announces
    its current WiFi address over a UDP broadcast; the receiver listens
    passively and reacts the moment one arrives. Fast, but depends on
    broadcast traffic actually being allowed on the network.

  - scan_subnet: a fallback for networks that block broadcast (e.g. client
    isolation on a guest/event network) -- tries a plain TCP connect to
    every address in a known subnet, in parallel, and returns whichever
    one is actually listening. Slower, but only needs ordinary unicast
    connectivity, which is far more likely to be allowed.
"""

import ipaddress
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional, Tuple

BEACON_PREFIX = "RTK_BEACON"


class BeaconSender(threading.Thread):
    """
    Broadcaster side. Periodically sends a small UDP packet announcing
    where the RTK broadcaster can currently be reached over WiFi, so the
    receiver can find (and keep) a ready connection before it's ever
    actually needed ("warm standby") rather than discovering cold at the
    moment Rajant fails.
    """

    def __init__(
        self,
        advertise_ip: str,
        advertise_port: int,
        beacon_port: int,
        source_ip: Optional[str] = None,
        interval: float = 1.5,
        logger=None,
    ):
        super().__init__(daemon=True)
        self.advertise_ip = advertise_ip
        self.advertise_port = advertise_port
        self.beacon_port = beacon_port
        self.source_ip = source_ip
        self.interval = interval
        self.logger = logger
        self._stop_event = threading.Event()

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        if self.source_ip:
            # Binding the local end to the WiFi interface's own address
            # (instead of SO_BINDTODEVICE, which needs root) makes sure the
            # beacon actually leaves via WiFi and not some other interface,
            # since the basestation has Rajant up at the same time.
            self._sock.bind((self.source_ip, 0))

    def stop(self):
        self._stop_event.set()
        self._sock.close()

    def run(self):
        message = f"{BEACON_PREFIX}:{self.advertise_ip}:{self.advertise_port}".encode()
        if self.logger:
            self.logger.info(
                f"[RTK] Beaconing WiFi address {self.advertise_ip}:{self.advertise_port}"
            )
        while not self._stop_event.is_set():
            try:
                self._sock.sendto(message, ("255.255.255.255", self.beacon_port))
            except OSError as e:
                if self.logger:
                    self.logger.warn(f"[RTK] Beacon send failed: {e}")
            self._stop_event.wait(self.interval)


class BeaconListener(threading.Thread):
    """
    Receiver side. Listens for BeaconSender announcements and calls
    `on_discover(ip, port)` whenever a new or changed WiFi address is
    heard. Runs continuously in the background so the receiver always has
    an up-to-date WiFi address on file, not just one caught at startup.
    """

    def __init__(
        self,
        beacon_port: int,
        on_discover: Callable[[str, int], None],
        logger=None,
    ):
        super().__init__(daemon=True)
        self.beacon_port = beacon_port
        self.on_discover = on_discover
        self.logger = logger
        self._stop_event = threading.Event()
        self._last_seen: Optional[Tuple[str, int]] = None

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("", self.beacon_port))
        self._sock.settimeout(1.0)

    def stop(self):
        self._stop_event.set()
        self._sock.close()

    def run(self):
        while not self._stop_event.is_set():
            try:
                data, _ = self._sock.recvfrom(256)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                prefix, ip, port_str = data.decode().split(":")
                port = int(port_str)
            except (ValueError, UnicodeDecodeError):
                continue
            if prefix != BEACON_PREFIX:
                continue

            if (ip, port) != self._last_seen:
                self._last_seen = (ip, port)
                if self.logger:
                    self.logger.info(f"[RTK] Beacon discovered WiFi broadcaster at {ip}:{port}")
                self.on_discover(ip, port)


def scan_subnet(cidr: str, port: int, timeout: float = 0.3, max_workers: int = 64) -> Optional[str]:
    """
    Fallback discovery for networks that block broadcast: try a plain TCP
    connect to every host in `cidr` on `port`, many at once, and return the
    first one that accepts a connection (or None if nobody answered).
    """

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
                for f in futures:
                    f.cancel()
                return result
    return None
