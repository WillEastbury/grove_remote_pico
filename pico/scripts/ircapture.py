# IR capture v2 ? handles NEC1, NEC-extended (16-bit addr), and repeat frames.
from machine import Pin
from time import ticks_us, ticks_diff, sleep_ms

rx = Pin(27, Pin.IN, Pin.PULL_UP)

def capture_frame(timeout_ms=5000):
    t_end = ticks_us() + timeout_ms * 1000
    while rx.value() == 1:
        if ticks_diff(t_end, ticks_us()) <= 0:
            return None
    t0 = ticks_us()
    last = 0
    transitions = [(0, 0)]
    t_stop = t0 + 100000
    while ticks_diff(t_stop, ticks_us()) > 0:
        v = rx.value()
        if v != last:
            transitions.append((ticks_diff(ticks_us(), t0), v))
            last = v
    return transitions

def decode(tr):
    if len(tr) < 4: return ("short", len(tr))
    head_low = tr[1][0] - tr[0][0]
    if not (7500 < head_low < 10500):
        return ("nonnec_headlow=%dus" % head_low,)
    head_high = tr[2][0] - tr[1][0]
    # Repeat: 9000us LOW, 2250us HIGH, 560us LOW, done
    if 1800 < head_high < 2700 and len(tr) <= 6:
        return ("repeat",)
    if not (3500 < head_high < 5500):
        return ("bad_headhigh=%dus" % head_high,)
    # Decode 32 bits
    bits = []
    i = 2
    while i + 1 < len(tr) and len(bits) < 32:
        if tr[i][1] != 0: i += 1; continue
        if i + 2 >= len(tr): break
        high_dur = tr[i+2][0] - tr[i+1][0]
        bits.append(1 if high_dur > 1000 else 0)
        i += 2
    if len(bits) < 32:
        return ("partial=%d" % len(bits),)
    b0 = sum(bits[i] << i for i in range(8))
    b1 = sum(bits[i+8] << i for i in range(8))
    b2 = sum(bits[i+16] << i for i in range(8))
    b3 = sum(bits[i+24] << i for i in range(8))
    # NEC1 if b1 == ~b0; otherwise NECx (b0|b1 is 16-bit addr)
    if (b0 ^ b1) == 0xFF:
        proto = "NEC1"
        addr_str = "0x%02X" % b0
    else:
        proto = "NECx"
        addr_str = "0x%02X%02X" % (b1, b0)  # high byte first conventionally
    cmd_ok = (b2 ^ b3) == 0xFF
    return (proto, addr_str, "0x%02X" % b2, "cmd_ok=%s" % cmd_ok, "raw=%02X %02X %02X %02X" % (b0,b1,b2,b3))

print("READY  ? press buttons, ~1s apart.  Ctrl+C to stop.")
print("-" * 70)
while True:
    tr = capture_frame(60000)
    if tr is None:
        print("(60s idle)")
        continue
    res = decode(tr)
    if res[0] == "repeat":
        print("    repeat")
    elif res[0].startswith(("short","nonnec","bad","partial")):
        print("   ?? %s  (%d transitions)" % (res[0], len(tr)))
    else:
        print("%-5s addr=%-7s cmd=%-5s  %s   %s" % (res[0], res[1], res[2], res[3], res[4]))
    sleep_ms(50)
