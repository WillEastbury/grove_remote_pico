"""
Pico 2 W main entry point.
Connects to WiFi with a static IP then polls for IR commands.
Runs forever — any failure (WiFi drop, server unreachable) triggers a full
reconnect + restart cycle so the device self-heals without a manual reboot.
"""

import network
import time
import machine
import wifi_config
from client import IRClient

_RETRY_DELAY_S = 5


def connect_wifi() -> bool:
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Apply static IP before connecting
    wlan.ifconfig((
        wifi_config.STATIC_IP,
        wifi_config.STATIC_MASK,
        wifi_config.STATIC_GW,
        wifi_config.STATIC_DNS,
    ))

    if wlan.isconnected():
        print(f"[WiFi] already connected: {wlan.ifconfig()[0]}")
        return True

    print(f"[WiFi] connecting to '{wifi_config.SSID}' …")
    wlan.connect(wifi_config.SSID, wifi_config.PASSWORD)

    for _ in range(30):
        if wlan.isconnected():
            print(f"[WiFi] connected  ip={wlan.ifconfig()[0]}")
            return True
        time.sleep(1)

    wlan.active(False)
    print("[WiFi] connection failed")
    return False


def run_poll_loop(client: IRClient):
    """Poll until an unrecoverable error occurs, then raise so the outer loop reconnects."""
    print(f"[IR] polling {wifi_config.SERVER_URL} …")
    consecutive_errors = 0
    while True:
        try:
            client.poll()
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            print(f"[IR] poll error #{consecutive_errors}: {e}")
            if consecutive_errors >= 5:
                raise RuntimeError("too many consecutive poll errors") from e
        time.sleep_ms(client.interval_ms())


def main():
    while True:                          # outer loop — reconnect on any failure
        try:
            if not connect_wifi():
                print(f"[WiFi] retrying in {_RETRY_DELAY_S}s …")
                time.sleep(_RETRY_DELAY_S)
                continue

            client = IRClient()
            run_poll_loop(client)

        except Exception as e:
            print(f"[MAIN] fatal error: {e} — reconnecting in {_RETRY_DELAY_S}s")
            # Bring WiFi down cleanly before retrying
            try:
                wlan = network.WLAN(network.STA_IF)
                wlan.disconnect()
                wlan.active(False)
            except Exception:
                pass
            time.sleep(_RETRY_DELAY_S)


main()
