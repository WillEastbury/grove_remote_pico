# grove_remote_pico

Control a Hisense TV via IR using a **Raspberry Pi Pico 2 W** + Grove Shield + Grove IR transmitter, driven by a Python web server with Google SSO.

```
Browser → Google SSO → FastAPI server → (HTTP poll) → Pico 2 W → Grove IR TX → Hisense TV
```

---

## Hardware

| Part | Notes |
|---|---|
| Raspberry Pi Pico 2 W | RP2350, onboard WiFi |
| Grove Shield for Pi Pico | https://wiki.seeedstudio.com/Grove_Shield_for_Pi_Pico_V1.0/ |
| Grove IR Transmitter (v1.2) | Plug into **port A0** on the shield |

The Grove Shield A0 connector maps to **GP26** on the Pico.  The IR transmitter module has its own driver transistor, so GP26 drives it safely via PWM.

---

## Project layout

```
grove_remote_pico/
├── sources_upstream/       Seeed Arduino IR library (reference, not deployed)
├── pico/                   MicroPython firmware for the Pico 2 W
│   ├── ir/
│   │   ├── ir_tx.py        PWM carrier driver (GP26, 33% duty)
│   │   ├── nec.py          NEC protocol  (38 kHz) — most Hisense TVs
│   │   ├── rc5.py          RC5 protocol  (36 kHz) — Philips / some older TVs
│   │   └── sony.py         Sony SIRC     (40 kHz)
│   ├── wifi_config.py      ← copy and fill in before flashing
│   ├── client.py           HTTP polling client
│   └── main.py             Entry point
└── server/
    ├── server.py           FastAPI control server
    ├── hisense_codes.py    NEC code table (model-specific, see note below)
    ├── requirements.txt
    ├── .env.example        ← copy to .env and fill in
    └── static/
        └── index.html      Web remote GUI (Google SSO, no build step)
```

---

## IR protocol port

Timing constants are ported directly from the upstream [Seeed_Arduino_IR](https://github.com/Seeed-Studio/Seeed_Arduino_IR) (IRLib2) C++ library:

| Protocol | Source file | Carrier | Key timings |
|---|---|---|---|
| NEC | `IRLib_P01_NEC.h` | 38 kHz | header 9024/4512 µs, bit 564 µs |
| RC5 | `IRLib_P03_RC5.h` | 36 kHz | T1 = 889 µs, Manchester encoding |
| Sony SIRC | `IRLib_P02_Sony.h` | 40 kHz | header 2400/600 µs, sent ×3 |

---

## Hisense IR codes ⚠️

**These codes are defaults for common Hisense Smart TV remotes (EN2A27H / EN-83801 series) and may not match your model.**

If a button does not respond:
1. Point your original Hisense remote at a **smartphone front camera** and press the button — you will see a white flash if the camera doesn't filter IR.
2. Use an IR learning app (e.g. "IR Remote" on Android / iOS) to capture the raw NEC code.
3. The 32-bit NEC code breaks down as: `address(8) | ~address(8) | command(8) | ~command(8)`.  The command byte for your button is byte 3 (bits 16–23).
4. Update `HISENSE_COMMANDS` in `server/hisense_codes.py` and restart the server.

---

## Setup

### 1 — Google OAuth2 credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → Create OAuth 2.0 Client ID.
2. Application type: **Web application**.
3. Authorised redirect URI: `http://localhost:8000/auth/callback` (add your LAN IP too if needed, e.g. `http://192.168.1.100:8000/auth/callback`).
4. Copy Client ID and Secret.

### 2 — Server

```bash
cd server
cp .env.example .env
# Edit .env: fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY, PICO_DEVICE_TOKEN
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in a browser.

### 3 — Pico 2 W firmware

Install [MicroPython for Pico 2 W](https://micropython.org/download/RPI_PICO2_W/) (≥ 1.24).

```bash
# Using mpremote or Thonny — copy the whole pico/ directory to the Pico
cp pico/wifi_config.py /tmp/wifi_config.py
# Edit /tmp/wifi_config.py: SSID, PASSWORD, SERVER_URL, DEVICE_TOKEN
```

Files to flash onto the Pico (maintaining the directory structure):

```
/                       ← Pico root
├── main.py
├── client.py
├── wifi_config.py      ← your edited copy
└── ir/
    ├── __init__.py
    ├── ir_tx.py
    ├── nec.py
    ├── rc5.py
    └── sony.py
```

With [mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html):

```bash
mpremote connect auto cp pico/main.py   :main.py
mpremote connect auto cp pico/client.py :client.py
mpremote connect auto cp /tmp/wifi_config.py :wifi_config.py
mpremote connect auto mkdir :ir
mpremote connect auto cp pico/ir/__init__.py :ir/__init__.py
mpremote connect auto cp pico/ir/ir_tx.py    :ir/ir_tx.py
mpremote connect auto cp pico/ir/nec.py      :ir/nec.py
mpremote connect auto cp pico/ir/rc5.py      :ir/rc5.py
mpremote connect auto cp pico/ir/sony.py     :ir/sony.py
```

### 4 — Use it

1. Open `http://<server-ip>:8000` in a browser.
2. Sign in with Google.
3. Press any button on the remote GUI — the command queues on the server and the Pico transmits it within ≤ 200 ms.

---

## Updating upstream IR codes

```bash
cd grove_remote_pico
git subtree pull --prefix=sources_upstream upstream/master --squash
```

---

## Architecture notes

- **Pico polls** the server every 200 ms (slows to 1 s when idle) — avoids WebSocket complexity on MicroPython.
- **Two separate auth layers**: Google JWT (30-day, cached in `localStorage`) for the browser; static bearer token for the Pico device.
- **ACK = "transmitted"** — the server records that the Pico sent the IR burst; it does not confirm the TV received it.
- The `mark()`/`space()` abstraction in `ir_tx.py` allows swapping PWM for a PIO state machine (for more precise timing) without changing any protocol code.
