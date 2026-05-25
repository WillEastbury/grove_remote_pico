"""
Hisense TV NECx IR code table.

Protocol:  NEC-extended (38 kHz), 16-bit address 0xBF00.
NECx frame: addr_low(8) | addr_high(8) | command(8) | ~command(8), LSB-first.

Captured live from the original Hisense remote pointed at a Grove IR receiver
on a Raspberry Pi Pico (see pico/scripts/ircapture.py).  Verified for the
Hisense 85A6NTUK (UK A6N series).  Older Hisense models (EN2A27H etc) used
NEC1 with 8-bit address 0x40 — they are NOT compatible with this table.

If a button does not respond, recapture it:
    mpremote run pico/scripts/ircapture_labelled.py
and update the command byte below.
"""

# NECx 16-bit address used by most Hisense buttons.
# Stored as (addr_high << 8) | addr_low so it's a single int > 0xFF, which
# triggers the NEC-extended code path in the encoder.
# Captured frame bytes were: 00 BF cc ~cc  →  addr_low=0x00, addr_high=0xBF
HISENSE_ADDRESS = 0xBF00

# Some app-launch buttons use a second NECx address.  Each special button
# overrides protocol + address from the global table.
SPECIAL: dict[str, dict] = {
    "vidaa":  {"protocol": "nec", "address": 0xBA00, "command": 0x49},
    "nowtv":  {"protocol": "nec", "address": 0xBA00, "command": 0x0F},
    "freely": {"protocol": "nec", "address": 0xBA00, "command": 0x4F},
    "kid":    {"protocol": "nec", "address": 0xBA00, "command": 0x25},
}

# Map of button name → NEC command byte (all on address 0xBF00 unless in SPECIAL).
# All entries were captured live with labelled presses from the original remote.
HISENSE_COMMANDS: dict[str, int] = {
    # ── Power / system ─────────────────────────────────────────────────
    "power":        0x0D,   # CONFIRMED
    "source":       0x12,   # CONFIRMED
    "mute":         0x0E,   # CONFIRMED

    # ── Volume ─────────────────────────────────────────────────────────
    "vol_up":       0x44,   # CONFIRMED
    "vol_down":     0x43,   # CONFIRMED

    # ── Channel ────────────────────────────────────────────────────────
    "ch_up":        0x4A,   # CONFIRMED
    "ch_down":      0x4B,   # CONFIRMED

    # ── Navigation pad ─────────────────────────────────────────────────
    "up":           0x16,   # CONFIRMED
    "down":         0x17,   # CONFIRMED
    "left":         0x19,   # CONFIRMED
    "right":        0x18,   # CONFIRMED
    "ok":           0x15,   # CONFIRMED
    "select":       0x15,   # CONFIRMED alias
    "back":         0x48,   # CONFIRMED
    "exit":         0x5C,   # CONFIRMED
    "home":         0x20,   # CONFIRMED
    "menu":         0x14,   # CONFIRMED
    "hamburger":    0x14,   # CONFIRMED alias
    "info":         0x0C,   # CONFIRMED
    "guide":        0x3A,   # CONFIRMED
    "chlist":       0x21,   # CONFIRMED

    # ── Playback ───────────────────────────────────────────────────────
    "play":         0xCA,   # CONFIRMED
    "pause":        0xCA,   # CONFIRMED: same physical play/pause toggle

    # ── Numeric pad ────────────────────────────────────────────────────
    "0":            0x00,   # CONFIRMED
    "1":            0x01,   # CONFIRMED
    "2":            0x02,   # CONFIRMED
    "3":            0x03,   # CONFIRMED
    "4":            0x04,   # CONFIRMED
    "5":            0x05,   # CONFIRMED
    "6":            0x06,   # CONFIRMED
    "7":            0x07,   # CONFIRMED
    "8":            0x08,   # CONFIRMED
    "9":            0x09,   # CONFIRMED

    # ── Streaming shortcuts ─────────────────────────────────────────────
    "netflix":      0x2D,   # CONFIRMED
    "prime":        0xBB,   # CONFIRMED
    "amazon":       0xBB,   # CONFIRMED alias
    "disney":       0x6A,   # CONFIRMED
    "youtube":      0xAA,   # CONFIRMED
    "apps":         0x5F,   # CONFIRMED
    "heart":        0x80,   # CONFIRMED favourites
    "favourites":   0x80,   # CONFIRMED alias
    "favorites":    0x80,   # CONFIRMED alias
    "rakuten":      0xD9,   # CONFIRMED
    "voice":        0xD5,   # CONFIRMED
    "subtitle":     0x1F,   # CONFIRMED

    # Buttons below are overridden by SPECIAL with address 0xBA00.
    "vidaa":        0x49,   # CONFIRMED
    "nowtv":        0x0F,   # CONFIRMED
    "freely":       0x4F,   # CONFIRMED
    "kid":          0x25,   # CONFIRMED

    # ── Colour buttons ─────────────────────────────────────────────────
    "red":          0x52,   # CONFIRMED
    "green":        0x53,   # CONFIRMED
    "yellow":       0x54,   # CONFIRMED
    "blue":         0x55,   # CONFIRMED
}

# Buttons that support NEC repeat frames when held
REPEATABLE: set[str] = {
    "vol_up", "vol_down", "ch_up", "ch_down",
    "up", "down", "left", "right",
}


def get_command(name: str) -> dict | None:
    """Return a ready-to-queue command dict for a named button, or None."""
    if name in SPECIAL:
        cmd_def = dict(SPECIAL[name])
        cmd_def["repeatable"] = name in REPEATABLE
        return cmd_def
    cmd = HISENSE_COMMANDS.get(name)
    if cmd is None:
        return None
    return {
        "protocol":   "nec",
        "address":    HISENSE_ADDRESS,
        "command":    cmd,
        "repeatable": name in REPEATABLE,
    }


def all_buttons() -> list[dict]:
    """Return metadata for all buttons (used by the web GUI)."""
    out = []
    for name, cmd in HISENSE_COMMANDS.items():
        if name in SPECIAL:
            sp = SPECIAL[name]
            out.append({
                "name":       name,
                "command":    sp["command"],
                "address":    sp["address"],
                "protocol":   sp["protocol"],
                "repeatable": name in REPEATABLE,
            })
        else:
            out.append({
                "name":       name,
                "command":    cmd,
                "address":    HISENSE_ADDRESS,
                "protocol":   "nec",
                "repeatable": name in REPEATABLE,
            })
    return out
