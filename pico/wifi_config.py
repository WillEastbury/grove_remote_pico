# WiFi and server configuration for the Pico 2 W IR client.
# Copy this file to wifi_config.py and fill in your values before flashing.

SSID     = "YOUR_WIFI_SSID"
PASSWORD = "YOUR_WIFI_PASSWORD"

# IP or hostname of the machine running server/server.py
SERVER_URL = "http://192.168.1.100:8000"

# Must match PICO_DEVICE_TOKEN in server/.env
DEVICE_TOKEN = "CHANGE_ME_PICO_TOKEN"

# Polling intervals in milliseconds
POLL_INTERVAL_MS  = 200    # while active (recent command within last 5 polls)
IDLE_INTERVAL_MS  = 1000   # when queue appears empty
