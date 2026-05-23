# WiFi and server configuration for the Pico 2 W IR client.
# Copy this file to wifi_config.py and fill in your values before flashing.

SSID     = "Puddles-Mesh"
PASSWORD = "Whatever1"

STATIC_IP      = "192.168.97.101"
STATIC_MASK    = "255.255.0.0"
STATIC_GW      = "192.168.0.1"
STATIC_DNS     = "8.8.8.8"

SERVER_URL = "https://homeremote.wavefunctionlabs.com"
# Optional: pre-resolved IP for SERVER_URL to skip MicroPython's broken
# getaddrinfo() on RP2350 v1.28.  If unset, client.py does its own UDP DNS
# lookup against STATIC_DNS at startup.
SERVER_IP  = "20.26.28.132"

# Alias used by client.py's DNS fallback
DNS        = STATIC_DNS

DEVICE_TOKEN = "f80220a43fa69c6995bc34927631c9d5"

POLL_INTERVAL_MS  = 200
IDLE_INTERVAL_MS  = 1000
