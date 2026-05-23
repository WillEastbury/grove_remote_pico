"""
Pico 2 W IR client — polls the FastAPI server for IR commands and transmits them.

Flow:
  1. Poll GET /api/next-command every POLL_INTERVAL_MS (adaptive: slows to
     IDLE_INTERVAL_MS after 5 consecutive empty polls).
  2. If a command arrives, transmit the IR signal immediately (no poll during TX).
  3. POST /api/ack/<id> with status="transmitted" once done.

DNS workaround:
  MicroPython v1.28 on RP2350 has a broken socket.getaddrinfo() that returns
  OSError(-2) even when TCP egress works fine.  We do our own UDP DNS lookup
  at startup against the configured DNS server, cache the result, and target
  the server by IP with an explicit Host: header so TLS SNI + virtual hosts
  still work.  If wifi_config.SERVER_IP is set, we skip DNS entirely.

Command JSON from server:
  { "id": "...", "protocol": "nec"|"rc5"|"sony",
    "address": int, "command": int,          # NEC / RC5
    "data": int, "bits": int,                # Sony
    "repeats": int }                         # NEC multi-frame repeats
"""

import urequests
import ujson
import socket
import time

from ir.ir_tx import IRTransmitter
from ir.nec   import NECSender
from ir.rc5   import RC5Sender
from ir.sony  import SonySender
import wifi_config


def _parse_url(url: str):
    """Return (scheme, host, port, path).  Strips trailing slash from host."""
    if "://" not in url:
        raise ValueError("URL must include scheme")
    scheme, rest = url.split("://", 1)
    if "/" in rest:
        host, path = rest.split("/", 1)
        path = "/" + path
    else:
        host, path = rest, "/"
    if ":" in host:
        host, port_s = host.split(":", 1)
        port = int(port_s)
    else:
        port = 443 if scheme == "https" else 80
    return scheme, host, port, path


def _udp_dns_lookup(hostname: str, dns_server: str = "8.8.8.8", timeout: float = 3.0) -> str:
    """Resolve hostname to an IPv4 address via raw UDP DNS query.

    Works around broken socket.getaddrinfo() on MicroPython RP2350 1.28.
    Returns dotted-quad string, or raises OSError on failure.
    """
    # Build minimal DNS query packet (standard A record)
    import urandom
    tid = urandom.getrandbits(16)
    header = bytes([
        (tid >> 8) & 0xFF, tid & 0xFF,   # transaction id
        0x01, 0x00,                       # standard query, recursion desired
        0x00, 0x01,                       # 1 question
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ])
    qname = b""
    for label in hostname.split("."):
        qname += bytes([len(label)]) + label.encode()
    qname += b"\x00"
    qtype_class = bytes([0x00, 0x01, 0x00, 0x01])  # A, IN
    packet = header + qname + qtype_class

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(timeout)
        addr = (dns_server, 53)
        s.sendto(packet, addr)
        data, _ = s.recvfrom(512)
    finally:
        s.close()

    # Skip header (12 bytes) and question section
    pos = 12
    while data[pos] != 0:
        pos += data[pos] + 1
    pos += 5  # null + qtype + qclass

    # Walk answer RRs looking for an A record
    answers = (data[6] << 8) | data[7]
    for _ in range(answers):
        # Name: pointer (2 bytes) or full label sequence
        if data[pos] & 0xC0:
            pos += 2
        else:
            while data[pos] != 0:
                pos += data[pos] + 1
            pos += 1
        rtype = (data[pos] << 8) | data[pos + 1]
        pos += 8  # type, class, ttl
        rdlen = (data[pos] << 8) | data[pos + 1]
        pos += 2
        if rtype == 1 and rdlen == 4:
            return "{}.{}.{}.{}".format(data[pos], data[pos+1], data[pos+2], data[pos+3])
        pos += rdlen
    raise OSError("No A record in DNS response")


class IRClient:
    def __init__(self):
        tx = IRTransmitter()
        self._nec  = NECSender(tx)
        self._rc5  = RC5Sender(tx)
        self._sony = SonySender(tx)
        self._headers = {
            "Authorization": "Bearer {}".format(wifi_config.DEVICE_TOKEN),
            "Content-Type":  "application/json",
        }
        self._idle_ticks = 0

        # Resolve server hostname once at startup (caches IP).
        self._scheme, self._host, self._port, _ = _parse_url(wifi_config.SERVER_URL)
        self._ip = self._resolve_server_ip()
        self._base_url = "{}://{}:{}".format(self._scheme, self._ip, self._port)
        self._headers["Host"] = self._host    # preserves TLS SNI + ingress vhost
        print("[IR] server: {} ({}) → {}".format(self._host, self._ip, self._base_url))

    def _resolve_server_ip(self) -> str:
        """Try static config IP first, then UDP DNS, then getaddrinfo as last resort."""
        static = getattr(wifi_config, "SERVER_IP", None)
        if static:
            print("[IR] using configured SERVER_IP={}".format(static))
            return static
        dns = getattr(wifi_config, "DNS", "8.8.8.8")
        for attempt in range(3):
            try:
                ip = _udp_dns_lookup(self._host, dns_server=dns)
                print("[IR] UDP DNS resolved {} → {}".format(self._host, ip))
                return ip
            except Exception as e:
                print("[IR] UDP DNS attempt {} failed: {!r}".format(attempt + 1, e))
                time.sleep(1)
        # Final fallback — likely to fail on RP2350 1.28 but try anyway
        info = socket.getaddrinfo(self._host, self._port)
        return info[0][-1][0]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def poll(self):
        """Fetch and execute one pending command.  Returns True if a command ran."""
        cmd = self._fetch_command()
        if cmd:
            self._idle_ticks = 0
            print("[IR] executing:", cmd)
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
                self._base_url + "/api/next-command",
                headers=self._headers,
            )
            body = r.text
            r.close()
            if body and body.strip() not in ("null", ""):
                return ujson.loads(body)
        except Exception as e:
            print("[IR] poll error:", repr(e))
        return None

    def _execute(self, cmd):
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
                print("[IR] unknown protocol:", proto)
        except Exception as e:
            print("[IR] transmit error:", repr(e))

    def _ack(self, cmd_id):
        try:
            r = urequests.post(
                self._base_url + "/api/ack/" + cmd_id,
                headers=self._headers,
                data=b'{"status":"transmitted"}',
            )
            r.close()
        except Exception as e:
            print("[IR] ack error:", repr(e))
