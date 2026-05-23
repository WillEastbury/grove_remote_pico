"""
Sony SIRC IR protocol encoder — ported from IRLib_P02_Sony.h.

Sony uses variable-length marks with a fixed space:
  Header: 2400µs mark | 600µs space
  Bit 1:  1200µs mark | 600µs space
  Bit 0:   600µs mark | 600µs space
Carrier: 40 kHz.  Frame sent 3 times (Sony protocol requirement).

Variants: 8-bit, 12-bit (default), 15-bit, 20-bit.

Source timings: IRLib_P02_Sony.h sendGeneric(data,nbits, 600*4,600, 600*2,600, 600,600, 40,false,45000)
"""

from .ir_tx import IRTransmitter

_KHZ        = 40
_UNIT       = 600    # µs base unit

_HEAD_MARK  = _UNIT * 4   # 2400 µs
_HEAD_SPACE = _UNIT       #  600 µs
_MARK_1     = _UNIT * 2   # 1200 µs  (logical 1)
_MARK_0     = _UNIT       #  600 µs  (logical 0)
_SPACE      = _UNIT       #  600 µs  (fixed space between bits)
_FRAME_US   = 45000       # µs — total frame length


class SonySender:
    """Sends Sony SIRC IR frames via an IRTransmitter.

    The Sony protocol requires each command to be transmitted 3 times.

    Args:
        tx: IRTransmitter instance (or compatible PIO replacement)
    """

    def __init__(self, tx: IRTransmitter):
        self._tx = tx

    def send(self, data: int, n_bits: int = 12):
        """Send a Sony SIRC command (transmitted 3 times as required).

        Args:
            data:   IR code value (MSB-aligned for n_bits)
            n_bits: 8, 12 (default), 15, or 20
        """
        self._tx.set_freq(_KHZ)
        for _ in range(3):
            self._send_once(data, n_bits)

    def _send_once(self, data: int, n_bits: int):
        extent = 0

        def _mark(us):
            nonlocal extent
            self._tx.mark(us)
            extent += us

        def _space(us):
            nonlocal extent
            self._tx.space(us)
            extent += us

        _mark(_HEAD_MARK)
        _space(_HEAD_SPACE)

        topbit = 1 << (n_bits - 1)
        for _ in range(n_bits):
            if data & topbit:
                _mark(_MARK_1)
            else:
                _mark(_MARK_0)
            _space(_SPACE)
            data <<= 1

        # Pad remaining silence to fill the 45 ms frame
        remaining = _FRAME_US - extent
        if remaining > 0:
            _space(remaining)

        self._tx.idle()
