# RTK Corrections

This ROS 2 package reads RTCM correction data from `/dev/ublox` on the
basestation and publishes it over ZeroMQ. Ground robots connect to the
basestation over the Rajant network and can also use its Wi-Fi address as a
fallback. Corrections are published by the receiver on `/rtcm` as
`rtcm_msgs/msg/Message`.

The container entrypoint uses `RUN=true` to enable the package. Set
`BASESTATION=true` on the basestation or `BASESTATION=false` on a ground
robot. Any other value causes the entrypoint to exit with an error.

## Parameters

### Broadcaster (basestation)

| Parameter                 | Default         | Description                                                    |
| ------------------------- | --------------- | -------------------------------------------------------------- |
| `basestation_rajant_ip` | `10.10.10.10` | Basestation Rajant IP used for the RTK and Wi-Fi-info sockets. |
| `rtk_port`              | `7501`        | ZeroMQ port for RTCM corrections.                              |
| `wifi_info_port`        | `7502`        | ZeroMQ port used to send the basestation Wi-Fi address.        |
| `wifi_interface`        | `wlan0`       | Wi-Fi interface whose IPv4 address is advertised.              |

### Receiver (ground robot)

| Parameter                 | Default             | Description                                            |
| ------------------------- | ------------------- | ------------------------------------------------------ |
| `basestation_rajant_ip` | `10.10.10.10`     | Basestation Rajant IP.                                 |
| `basestation_wifi_ip`   | `192.168.129.100` | Known basestation Wi-Fi IP used for fallback.          |
| `rtk_port`              | `7501`            | Must match the broadcaster.                            |
| `wifi_info_port`        | `7502`            | Must match the broadcaster.                            |
| `rajant_stale_timeout`  | `5.0`             | Seconds without Rajant data before switching to Wi-Fi. |
| `wifi_stale_timeout`    | `5.0`             | Seconds without Wi-Fi data before marking Wi-Fi stale. |
| `rajant_probe_interval` | `4.0`             | Seconds between Rajant recovery probes.                |
| `wifi_probe_interval`   | `4.0`             | Seconds between Wi-Fi recovery probes.                 |

## Docker Compose

Use the RTK directory as the build context. The image entrypoint uses
`BASESTATION` to choose the broadcaster or receiver.

```yaml
# version: "3.8"

x-common: &common
  ipc: host
  network_mode: host
  privileged: true
  tty: true
  logging:
    driver: local
    options:
      max-size: 100m

services:
  rtk:
    <<: *common
    init: true
    hostname: ${HOSTNAME}
    build:
      context: ./common/rtk-correction
      dockerfile: Dockerfile.x86
    image: dtc-platform-${HOSTNAME}:rtk
    environment:
      RUN: "${RTK:-true}"
      BASESTATION: "${BASESTATION:-false}"
      BASESTATION_RAJANT_IP: "${BASESTATION_RAJANT_IP:-10.10.10.10}"
      WIFI_INTERFACE: "${WIFI_INTERFACE:-wlan0}"
      BASESTATION_WIFI_IP: "${BASESTATION_WIFI_IP:-192.168.129.10}"
      RTK_PORT: "${RTK_PORT:-7501}"
      WIFI_INFO_PORT: "${WIFI_INFO_PORT:-7502}"
  
    volumes:
      - /dev:/dev
```

## Example `.env`

### Basestation

```dotenv
HOSTNAME=neptune
RTK=true
BASESTATION=true
BASESTATION_RAJANT_IP=10.10.10.10
WIFI_INTERFACE=wlan0
RTK_PORT=7501
WIFI_INFO_PORT=7502
```

### Ground robot

```dotenv
HOSTNAME=phobos
RTK=true
BASESTATION=false
BASESTATION_RAJANT_IP=10.10.10.10
BASESTATION_WIFI_IP=192.168.129.10
RTK_PORT=7501
WIFI_INFO_PORT=7502
```

The basestation must have `/dev/ublox` available and its Wi-Fi interface must
already have an IPv4 address.
