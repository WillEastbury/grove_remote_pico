"""
Hisense TV NEC IR code table.

Protocol:  NEC (38 kHz), address byte 0x40 (~address = 0xBF, verified).
NEC frame: address(8) | ~address(8) | command(8) | ~command(8), LSB-first.

!! MODEL-SPECIFIC DISCLAIMER !!
These codes match common Hisense Smart TV remotes (e.g. EN2A27H, EN-83801 series).
They may not work on all Hisense models.  If a button does not respond:
  1. Point your original Hisense remote at a smartphone front camera (not all cameras
     filter IR) and press the button — you will see the LED flash.
  2. Use an IR learning app (e.g. "IR Remote" on Android) to capture the raw code.
  3. Update the command byte below and re-run the server.
  4. Alternatively, check https://www.remotecentral.com or the LIRC database for your
     exact model number.
"""

HISENSE_ADDRESS = 0x40   # NEC device address for Hisense TVs

# Map of button name → NEC command byte.
# Each command byte is unique within this table.
HISENSE_COMMANDS: dict[str, int] = {
    # ── Power / system ─────────────────────────────────────────────────
    "power":        0x48,
    "mute":         0xF0,
    "source":       0xD0,

    # ── Volume ─────────────────────────────────────────────────────────
    "vol_up":       0x50,
    "vol_down":     0x57,

    # ── Channel ────────────────────────────────────────────────────────
    "ch_up":        0x00,
    "ch_down":      0x01,

    # ── Navigation pad ─────────────────────────────────────────────────
    "up":           0x60,
    "down":         0xA0,
    "left":         0x10,
    "right":        0x90,
    "ok":           0x20,
    "back":         0x70,
    "home":         0x30,
    "menu":         0x40,

    # ── Numeric pad ────────────────────────────────────────────────────
    "0":            0xC0,
    "1":            0x18,
    "2":            0x98,
    "3":            0x58,
    "4":            0xD8,
    "5":            0x38,
    "6":            0xB8,
    "7":            0x78,
    "8":            0xF8,
    "9":            0x08,

    # ── Streaming shortcuts ─────────────────────────────────────────────
    # Verified on Hisense EN2A27H-class remotes:
    "netflix":      0x1E,
    "amazon":       0x4E,
    "youtube":      0x2E,

    # !! UNVERIFIED — placeholder codes !!
    # The original Hisense remote rarely has hard buttons for these apps.
    # If they don't launch the app, capture the real code with a phone
    # camera + IR learner app and update the byte below.
    # Alternative: change the GUI handler to send Home → arrow keys → OK
    # to navigate to the app tile instead of a single IR shot.
    "itvx":         0x5E,
    "iplayer":      0x6E,
    "nowtv":        0x7E,
    "freely":       0x8E,
    "spotify":      0x9E,
}

# Buttons that support NEC repeat frames when held
REPEATABLE: set[str] = {
    "vol_up", "vol_down", "ch_up", "ch_down",
    "up", "down", "left", "right",
}


def get_command(name: str) -> dict | None:
    """Return a ready-to-queue command dict for a named button, or None."""
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
    return [
        {
            "name":       name,
            "command":    cmd,
            "address":    HISENSE_ADDRESS,
            "protocol":   "nec",
            "repeatable": name in REPEATABLE,
        }
        for name, cmd in HISENSE_COMMANDS.items()
    ]
