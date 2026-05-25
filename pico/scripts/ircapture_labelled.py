# Labelled NEC/NECx capture for Grove IR receiver on A1 / GP27.
# Run with: mpremote run pico/scripts/ircapture_labelled.py
import time
from machine import Pin

PIN_RX = 27
TIMEOUT_US = 12000

BUTTONS = [
    "power", "source", "home", "menu", "back", "exit", "info", "guide",
    "chlist", "up", "down", "left", "right", "ok", "vol_up", "vol_down",
    "mute", "ch_up", "ch_down", "play", "pause",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "vidaa", "apps", "heart", "netflix", "prime", "disney", "youtube",
    "nowtv", "freely", "kid", "rakuten", "voice", "subtitle",
    "red", "green", "yellow", "blue",
]

rx = Pin(PIN_RX, Pin.IN, Pin.PULL_UP)


def quiet(ms):
    start = time.ticks_ms()
    last_low = start
    while time.ticks_diff(time.ticks_ms(), last_low) < ms:
        if rx.value() == 0:
            last_low = time.ticks_ms()
        if time.ticks_diff(time.ticks_ms(), start) > 15000:
            return
        time.sleep_us(100)


def capture(timeout_ms=30000):
    times = []
    start = time.ticks_ms()
    while rx.value() == 1:
        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
            return None
        time.sleep_us(50)

    last = time.ticks_us()
    last_v = 0
    times.append(0)
    while True:
        v = rx.value()
        now = time.ticks_us()
        if v != last_v:
            times.append(time.ticks_diff(now, last))
            last = now
            last_v = v
            if len(times) > 220:
                break
        elif v == 1 and time.ticks_diff(now, last) > TIMEOUT_US:
            break
    return times


def decode(times):
    if times is None:
        return None, "timeout"
    if len(times) < 20:
        return None, "short frame"

    header_mark = times[1]
    header_space = times[2]
    if not (7000 < header_mark < 11000):
        return None, "bad header mark {}".format(header_mark)
    if 1800 < header_space < 2800:
        return "REPEAT", "repeat frame"
    if not (4000 < header_space < 5500):
        return None, "bad header space {}".format(header_space)

    bits = []
    i = 3
    while i + 1 < len(times) and len(bits) < 32:
        mark = times[i]
        space = times[i + 1]
        if not (300 < mark < 900):
            return None, "bad bit mark {}".format(mark)
        bits.append(1 if space > 1000 else 0)
        i += 2

    if len(bits) != 32:
        return None, "only {} bits".format(len(bits))

    def byte_at(offset):
        value = 0
        for n in range(8):
            value |= bits[offset + n] << n
        return value

    b0 = byte_at(0)
    b1 = byte_at(8)
    b2 = byte_at(16)
    b3 = byte_at(24)

    if (b2 ^ b3) != 0xFF:
        return None, "bad command checksum {:02X} {:02X}".format(b2, b3)
    if (b0 ^ b1) == 0xFF:
        return ("NEC1", b0, b2), "ok"
    return ("NECX", (b1 << 8) | b0, b2), "ok"


print("LABELLED CAPTURE READY")
print("Wait for PRESS line, then press that remote button once.")
quiet(3000)

for name in BUTTONS:
    print("PRESS {}".format(name))
    while True:
        res, msg = decode(capture())
        if res == "REPEAT":
            continue
        if res is None:
            print("RETRY {} ({})".format(name, msg))
            quiet(2000)
            print("PRESS {}".format(name))
            continue

        proto, addr, cmd = res
        if proto == "NECX":
            print("GOT {} {} addr=0x{:04X} cmd=0x{:02X}".format(name, proto, addr, cmd))
        else:
            print("GOT {} {} addr=0x{:02X} cmd=0x{:02X}".format(name, proto, addr, cmd))
        quiet(3000)
        break

print("LABELLED CAPTURE DONE")
