# RTK Corrections

ROS 2 package for sending RTCM correction data from a base station to rover
robots. The base station reads RTCM data from `/dev/ublox` and publishes it
over ZeroMQ. Each receiver republishes the data as `rtcm_msgs/msg/Message` on
`/rtcm`.

## How it works

- **Rajant** is the primary path. Its IP address is known and configured in
	advance.
- **WiFi** is a fallback path. The broadcaster announces its current WiFi IP
	with a UDP beacon and always sends corrections on both paths.
- If beacons are blocked, a receiver can scan a configured subnet as a
	fallback.
- Each receiver independently monitors its own Rajant connection. It normally
	uses Rajant and switches to WiFi after consecutive local failures, then
	switches back after Rajant recovers.

## Launch
The container entrypoint launches the broadcaster or receiver based on
hostname. To launch manually:

```bash
ros2 launch rtk_correction broadcaster.launch.py
ros2 launch rtk_correction receiver.launch.py
```

For a receiver that should use WiFi failover:

```bash
ros2 launch rtk_correction receiver.launch.py \
	ip:=10.10.10.10 rajant_interface:=rajant \
	enable_wifi_failover:=true wifi_scan_subnet:=192.168.60.0/24
```

## Broadcaster parameters

| Parameter | Default | Purpose |
| --- | --- | --- |
| `ip` | `10.10.10.10` | Local Rajant IP to bind. |
| `port` | `7507` | TCP port used by both correction paths. |
| `wifi_interface` | `wlan0` | Interface whose IPv4 address is used for the WiFi socket and beacon. |
| `beacon_port` | `7508` | UDP broadcast port for WiFi discovery. Must match the receiver. |
| `beacon_interval` | `1.5` | Seconds between WiFi beacon packets. |

The WiFi interface must already have an IPv4 address when the broadcaster
starts. If it does not, the WiFi socket and beacon are not created during that
run.

## Receiver parameters

| Parameter | Default | Purpose |
| --- | --- | --- |
| `ip` | `10.10.10.10` | Rajant IP address of the broadcaster. Also used as the health-check target. |
| `port` | `7507` | Correction TCP port. Must match the broadcaster. |
| `rajant_interface` | `rajant` | This receiver's Linux interface used for Rajant health pings. |
| `enable_wifi_failover` | `true` | Enables this receiver's automatic switch to WiFi. Set to `false` to use Rajant only. |
| `beacon_port` | `7508` | UDP port used to discover the broadcaster over WiFi. |
| `beacon_wait_timeout` | `8.0` | Seconds to wait for a beacon before starting the scan fallback. |
| `wifi_scan_subnet` | `192.168.60.0/24` | CIDR subnet to scan. Empty disables scanning. |
| `stale_timeout` | `5.0` | Seconds without RTCM data before logging a stale-link warning. |
| `ping_interval` | `1.5` | Seconds between this receiver's Rajant health pings. |
| `ping_timeout` | `1.0` | Ping timeout in seconds. |
| `fail_threshold` | `3` | Consecutive failed pings before this receiver switches to WiFi. |
| `recover_threshold` | `3` | Consecutive successful pings before this receiver switches back to Rajant. |

Receivers connect to Rajant immediately. Once WiFi is discovered, the receiver
keeps a separate WiFi connection ready but reads from only one path at a time,
so it does not publish duplicate RTCM messages.

## Configuration checklist

1. Set the broadcaster `ip` to its Rajant address and use the same `ip` and
	 `port` on every receiver.
2. On the broadcaster, set `wifi_interface` to the actual WiFi interface
	name.
3. On each receiver, set `rajant_interface` to the actual Rajant interface
	name. Set `enable_wifi_failover:=false` on receivers that should stay on
	Rajant only.
4. Keep `beacon_port` the same on broadcaster and receivers. If UDP broadcast
	 is unavailable, set `wifi_scan_subnet` on receivers.
5. Confirm that `/dev/ublox` exists on the broadcaster and that the ROS 2
	 workspace contains `rtcm_msgs`.

The receiver publishes the resulting corrections on `/rtcm`.
