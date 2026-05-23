"""
RC5 IR protocol encoder — ported from IRLib_P03_RC5.h.

RC5 uses Manchester (phase) encoding:
  Logical 1 = space then mark  (low→high transition at bit centre)
  Logical 0 = mark then space  (high→low transition at bit centre)
Each half-bit period T1 = 889 µs.  Carrier = 36 kHz.

Frame: start-mark(T1) | toggle(1b) | address(5b) | command(6b)  [13 bits total]
Toggle bit must be flipped between distinct key presses.

Source timings: IRLib_P03_RC5.h  RC5_T1=889, carrier 36 kHz, frame extent 114 ms
"""

from .ir_tx import IRTransmitter

_KHZ        = 36
_T1         = 889    # µs — RC5 half-bit period
_FRAME_US   = 114000 # µs — total frame length (space fills the rest)

_TOPBIT     = 0x80000000


class RC5Sender:
    """Sends RC5 IR frames via an IRTransmitter.

    Args:
        tx: IRTransmitter instance (or compatible PIO replacement)
    """

    def __init__(self, tx: IRTransmitter):
        self._tx = tx

    def send(self, address: int, command: int, toggle: int = 0, n_bits: int = 13):
        """Send one RC5 frame.

        Args:
            address: 5-bit device address (0–31)
            command: 6-bit command code (0–63); bit 6 used for RC5-F7 14-bit variant
            toggle:  toggle bit (0 or 1) — flip this between separate key presses
            n_bits:  13 (standard RC5) or 14 (RC5-F7)
        """
        self._tx.set_freq(_KHZ)

        # Build data word: [0…] | start(1) | toggle(1) | address(5) | command(6)
        data = (
            (1              << (n_bits - 1)) |  # start bit
            ((toggle & 1)   << (n_bits - 2)) |
            ((address & 0x1F) << 6)           |
            (command & 0x3F)
        )
        data <<= (32 - n_bits)  # align to MSB for the loop

        extent = 0

        def _mark(us):
            nonlocal extent
            self._tx.mark(us)
            extent += us

        def _space(us):
            nonlocal extent
            self._tx.space(us)
            extent += us

        _mark(_T1)  # first start-bit leading mark

        for _ in range(n_bits):
            if data & _TOPBIT:
                _space(_T1)   # 1: space then mark
                _mark(_T1)
            else:
                _mark(_T1)    # 0: mark then space
                _space(_T1)
            data <<= 1

        # Pad to full 114 ms frame with trailing silence
        remaining = _FRAME_US - extent
        if remaining > 0:
            _space(remaining)

        self._tx.idle()
