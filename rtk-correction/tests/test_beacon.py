from rtk_correction.beacon import parse_beacon_message, parse_wifi_info_message


def test_parse_beacon_message_valid():
    payload = b"RTK_BEACON:192.168.42.12:7507"
    assert parse_beacon_message(payload) == ("192.168.42.12", 7507)


def test_parse_beacon_message_invalid():
    assert parse_beacon_message(b"bad-data") is None
    assert parse_beacon_message(b"RTK_BEACON:192.168.42.12") is None


def test_parse_wifi_info_message_valid():
    payload = b"RTK_WIFI_INFO:192.168.42.12:7507"
    assert parse_wifi_info_message(payload) == ("192.168.42.12", 7507)


def test_parse_wifi_info_message_invalid():
    assert parse_wifi_info_message(b"bad-data") is None
    assert parse_wifi_info_message(b"RTK_WIFI_INFO:192.168.42.12") is None
