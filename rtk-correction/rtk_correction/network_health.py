#!/usr/bin/env python3
"""
Helpers for checking whether the Rajant link is actually working, and for
reading a network interface's current IP address at runtime (needed for
WiFi, since it's DHCP-assigned and not known ahead of time like Rajant's
static address is).

This extends the same idea already used in the basestation repo's MOCHA
node (a simple `ping()` check), but tracks round-trip time and uses
consecutive success/failure counts so a single dropped ping doesn't cause
flapping between Rajant and WiFi.
"""

import re
import subprocess
import threading
from typing import Callable, Optional

PING_TIME_RE = re.compile(r"time[=<]\s*([\d.]+)")
INET_RE = re.compile(r"inet\s+(\d+\.\d+\.\d+\.\d+)")


def ping_once(target: str, interface: Optional[str] = None, timeout: float = 1.0) -> Optional[float]:
    """
    Send a single ICMP ping to `target`, forced out `interface` if given
    (so it actually tests the Rajant path specifically, not whatever route
    the OS would otherwise pick). Returns the round-trip time in
    milliseconds, or None if the ping failed or timed out.
    """
    cmd = ["ping", "-c", "1", "-W", str(max(1, int(round(timeout))))]
    if interface:
        cmd += ["-I", interface]
    cmd.append(target)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 1.0
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    match = PING_TIME_RE.search(result.stdout)
    return float(match.group(1)) if match else None


def get_interface_ipv4(interface: str) -> Optional[str]:
    """
    Read whatever IPv4 address is currently assigned to `interface`, or
    None if the interface doesn't exist or has no address. Used for WiFi,
    where the address can't be hardcoded because it's handed out by
    whatever network is present at a given site.
    """
    try:
        result = subprocess.run(
            ["ip", "-4", "addr", "show", "dev", interface],
            capture_output=True, text=True, timeout=2.0,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    match = INET_RE.search(result.stdout)
    return match.group(1) if match else None


class HealthMonitor(threading.Thread):
    """
    Runs in the background, pinging `target` over `interface` on a timer,
    and exposes a `.healthy` flag. Requires `fail_threshold` consecutive
    lost pings before flipping to unhealthy, and `recover_threshold`
    consecutive replies before flipping back — this is the hysteresis that
    keeps a single dropped packet from triggering a switch.
    """

    def __init__(
        self,
        target: str,
        interface: Optional[str] = None,
        interval: float = 1.5,
        timeout: float = 1.0,
        fail_threshold: int = 3,
        recover_threshold: int = 3,
        on_change: Optional[Callable[[bool], None]] = None,
        logger=None,
    ):
        super().__init__(daemon=True)
        self.target = target
        self.interface = interface
        self.interval = interval
        self.timeout = timeout
        self.fail_threshold = fail_threshold
        self.recover_threshold = recover_threshold
        self.on_change = on_change
        self.logger = logger

        # Start optimistic. The first few missed pings will flip this to
        # False if Rajant is genuinely down; starting pessimistic would
        # mean every boot begins by (briefly) treating Rajant as failed.
        self._healthy = True
        self._consecutive_fail = 0
        self._consecutive_success = 0
        self._last_rtt_ms: Optional[float] = None
        self._stop_event = threading.Event()

    @property
    def healthy(self) -> bool:
        return self._healthy

    @property
    def last_rtt_ms(self) -> Optional[float]:
        return self._last_rtt_ms

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            rtt = ping_once(self.target, interface=self.interface, timeout=self.timeout)
            self._last_rtt_ms = rtt

            if rtt is not None:
                self._consecutive_success += 1
                self._consecutive_fail = 0
                if not self._healthy and self._consecutive_success >= self.recover_threshold:
                    self._set_healthy(
                        True,
                        f"{self._consecutive_success} consecutive replies "
                        f"(last {rtt:.1f} ms)",
                    )
            else:
                self._consecutive_fail += 1
                self._consecutive_success = 0
                if self._healthy and self._consecutive_fail >= self.fail_threshold:
                    self._set_healthy(
                        False,
                        f"{self._consecutive_fail} consecutive lost pings to {self.target}",
                    )

            self._stop_event.wait(self.interval)

    def _set_healthy(self, healthy: bool, reason: str):
        self._healthy = healthy
        if self.logger:
            state = "HEALTHY" if healthy else "UNHEALTHY"
            via = self.interface or "default route"
            self.logger.info(f"[RTK] Link to {self.target} via {via} is now {state} ({reason})")
        if self.on_change:
            self.on_change(healthy)
