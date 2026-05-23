"""
Pico 2 W main entry point.
Connects to WiFi then starts the IR command polling loop.
"""

import network
import time
import wifi_config
from client import IRClient


def connect_wifi() -> bool:
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        print(f"[WiFi] already connected: {wlan.ifconfig()[0]}")
        return True

    print(f"[WiFi] connecting to '{wifi_config.SSID}' …")
    wlan.connect(wifi_config.SSID, wifi_config.PASSWORD)

    for attempt in range(30):
        if wlan.isconnected():
            print(f"[WiFi] connected: {wlan.ifconfig()[0]}")
            return True
        time.sleep(1)

    print("[WiFi] connection failed — check SSID/PASSWORD in wifi_config.py")
    return False


def main():
    if not connect_wifi():
        return

    client = IRClient()
    print(f"[IR] polling {wifi_config.SERVER_URL} for commands …")

    while True:
        client.poll()
        time.sleep_ms(client.interval_ms())


main()
