"""
Hisense TV NECx IR code table.

Protocol:  NEC-extended (38 kHz), 16-bit address 0x00BF.
NECx frame: addr_low(8) | addr_high(8) | command(8) | ~command(8), LSB-first.

Captured live from the original Hisense remote pointed at a Grove IR receiver
on a Raspberry Pi Pico (see pico/scripts/ircapture.py).  Verified for the
Hisense 85A6NTUK (UK A6N series).  Older Hisense models (EN2A27H etc) used
NEC1 with 8-bit address 0x40 — they are NOT compatible with this table.

If a button does not respond, recapture it:
    mpremote connect auto run pico/scripts/ircapture.py
and update the command byte below.
"""

# NECx 16-bit address used by all Hisense buttons except branded app launchers.
# Stored as (addr_high << 8) | addr_low so it's a single int > 0xFF, which
# triggers the NEC-extended code path in the encoder.
# Captured frame bytes were: 00 BF cc ~cc  →  addr_low=0x00, addr_high=0xBF
HISENSE_ADDRESS = 0xBF00

# Some app-launch buttons on a Hisense remote actually emit a totally different
# protocol/address pair (so they can talk to the smart hub regardless of TV
# vendor).  Each special button overrides protocol + address from the global.
SPECIAL: dict[str, dict] = {
    # Captured live: Netflix on the Hisense clone remote
    "netflix": {"protocol": "nec", "address": 0x04, "command": 0x56},
}

# Map of button name → NEC command byte (all on address 0x00BF unless in SPECIAL).
# CONFIRMED   = captured live with labelled press
# UNVERIFIED  = inherited from a guess table; recapture before relying on it
HISENSE_COMMANDS: dict[str, int] = {
    # ── Power / system ─────────────────────────────────────────────────
    "power":        0x0D,   # CONFIRMED
    "mute":         0xF0,   # UNVERIFIED
    "source":       0xD0,   # UNVERIFIED

    # ── Volume ─────────────────────────────────────────────────────────
    "vol_up":       0x44,   # CONFIRMED
    "vol_down":     0x43,   # CONFIRMED

    # ── Channel ────────────────────────────────────────────────────────
    "ch_up":        0x00,   # UNVERIFIED
    "ch_down":      0x01,   # UNVERIFIED

    # ── Navigation pad ─────────────────────────────────────────────────
    # Captured 0x2D twice (probably home or back), then 0x16/0x17/0x19/0x18 in
    # a cluster — likely the arrow ring.  Treat as best-guess until recapture.
    "up":           0x16,   # GUESS (captured in arrow cluster)
    "down":         0x17,   # GUESS
    "left":         0x18,   # GUESS
    "right":        0x19,   # GUESS
    "ok":           0x15,   # CONFIRMED
    "back":         0x2D,   # GUESS (captured twice in a row)
    "home":         0x30,   # UNVERIFIED
    "menu":         0x40,   # UNVERIFIED

    # ── Numeric pad ────────────────────────────────────────────────────
    "0":            0xC0,   # UNVERIFIED
    "1":            0x18,   # UNVERIFIED
    "2":            0x98,   # UNVERIFIED
    "3":            0x58,   # UNVERIFIED
    "4":            0xD8,   # UNVERIFIED
    "5":            0x38,   # UNVERIFIED
    "6":            0xB8,   # UNVERIFIED
    "7":            0x78,   # UNVERIFIED
    "8":            0xF8,   # UNVERIFIED
    "9":            0x08,   # UNVERIFIED

    # ── Streaming shortcuts ─────────────────────────────────────────────
    # Netflix goes through SPECIAL above (different protocol).
    # Prime/YouTube/etc still UNVERIFIED — recapture before use.
    "netflix":      0x56,   # CONFIRMED (overridden by SPECIAL: NEC1 addr=0x04)
    "amazon":       0x4E,   # UNVERIFIED
    "youtube":      0x2E,   # UNVERIFIED
    "itvx":         0x5E,   # UNVERIFIED
    "iplayer":      0x6E,   # UNVERIFIED
    "nowtv":        0x7E,   # UNVERIFIED
    "freely":       0x8E,   # UNVERIFIED
    "spotify":      0x9E,   # UNVERIFIED
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
