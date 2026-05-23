"""
Pico 2 W IR client — polls the FastAPI server for IR commands and transmits them.

Flow:
  1. Poll GET /api/next-command every POLL_INTERVAL_MS (adaptive: slows to
     IDLE_INTERVAL_MS after 5 consecutive empty polls).
  2. If a command arrives, transmit the IR signal immediately (no poll during TX).
  3. POST /api/ack/<id> with status="transmitted" once done.

Command JSON from server:
  { "id": "...", "protocol": "nec"|"rc5"|"sony",
    "address": int, "command": int,          # NEC / RC5
    "data": int, "bits": int,                # Sony
    "repeats": int }                         # NEC multi-frame repeats
"""

import urequests
import ujson
import time

from ir.ir_tx import IRTransmitter
from ir.nec   import NECSender
from ir.rc5   import RC5Sender
from ir.sony  import SonySender
import wifi_config


class IRClient:
    def __init__(self):
        tx = IRTransmitter()
        self._nec  = NECSender(tx)
        self._rc5  = RC5Sender(tx)
        self._sony = SonySender(tx)
        self._headers = {
            "Authorization": f"Bearer {wifi_config.DEVICE_TOKEN}",
            "Content-Type": "application/json",
        }
        self._idle_ticks = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def poll(self):
        """Fetch and execute one pending command.  Returns True if a command ran."""
        cmd = self._fetch_command()
        if cmd:
            self._idle_ticks = 0
            print(f"[IR] executing: {cmd}")
            self._execute(cmd)
            self._ack(cmd["id"])
            return True
        self._idle_ticks += 1
        return False

    def interval_ms(self) -> int:
        """Adaptive poll interval: fast when active, slow when idle."""
        if self._idle_ticks < 5:
            return wifi_config.POLL_INTERVAL_MS
        return wifi_config.IDLE_INTERVAL_MS

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_command(self):
        try:
            r = urequests.get(
                f"{wifi_config.SERVER_URL}/api/next-command",
                headers=self._headers,
            )
            body = r.text
            r.close()
            if body and body.strip() not in ("null", ""):
                return ujson.loads(body)
        except Exception as e:
            print(f"[IR] poll error: {e}")
        return None

    def _execute(self, cmd: dict):
        proto = cmd.get("protocol", "nec").lower()
        try:
            if proto == "nec":
                self._nec.send(
                    cmd["address"],
                    cmd["command"],
                    repeats=cmd.get("repeats", 1),
                )
            elif proto == "rc5":
                self._rc5.send(
                    cmd["address"],
                    cmd["command"],
                    toggle=cmd.get("toggle", 0),
                )
            elif proto == "sony":
                self._sony.send(cmd["data"], n_bits=cmd.get("bits", 12))
            else:
                print(f"[IR] unknown protocol: {proto}")
        except Exception as e:
            print(f"[IR] transmit error: {e}")

    def _ack(self, cmd_id: str):
        try:
            r = urequests.post(
                f"{wifi_config.SERVER_URL}/api/ack/{cmd_id}",
                headers=self._headers,
                data=b'{"status":"transmitted"}',
            )
            r.close()
        except Exception as e:
            print(f"[IR] ack error: {e}")
