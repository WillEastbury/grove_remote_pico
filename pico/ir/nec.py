"""
NEC IR protocol encoder — ported from IRLib_P01_NEC.h.

NEC frame: 9024µs mark | 4512µs space | 32 data bits (LSB first) | 564µs stop mark
Data bits: address(8) | ~address(8) | command(8) | ~command(8)
Bit encoding: 564µs mark + [564µs space = 0 | 1692µs space = 1]
Carrier: 38 kHz
Frame extent: ~108 ms

Source timings: IRLib_P01_NEC.h sendGeneric(data,32, 564*16,564*8, 564,564, 564*3,564, 38,true,108000)
"""

from .ir_tx import IRTransmitter

_KHZ       = 38
_UNIT      = 564      # µs base unit

_HEAD_MARK  = _UNIT * 16   # 9024 µs
_HEAD_SPACE = _UNIT * 8    # 4512 µs
_BIT_MARK   = _UNIT        #  564 µs
_SPACE_1    = _UNIT * 3    # 1692 µs  (logical 1)
_SPACE_0    = _UNIT        #  564 µs  (logical 0)
_STOP_MARK  = _UNIT        #  564 µs
_REPEAT_SPACE = _UNIT * 4  # 2256 µs  (repeat frame)


class NECSender:
    """Sends NEC IR frames via an IRTransmitter.

    Builds the 32-bit NEC word as: address | ~address | command | ~command
    then clocks it out LSB-first exactly as the Arduino library does.

    Args:
        tx: IRTransmitter instance (or compatible PIO replacement)
    """

    def __init__(self, tx: IRTransmitter):
        self._tx = tx

    def send(self, address: int, command: int, repeats: int = 1):
        """Send one (or more) NEC frames separated by the standard 108 ms gap.

        Args:
            address:  8-bit device address (e.g. 0x40 for Hisense)
            command:  8-bit command byte
            repeats:  how many full frames to send (for held buttons use send_repeat)
        """
        self._tx.set_freq(_KHZ)
        for i in range(repeats):
            self._send_frame(address, command)
            if i < repeats - 1:
                # 108 ms total frame extent; already ~67 ms used, wait the rest
                self._tx.space(41000)

    def _send_frame(self, address: int, command: int):
        # Build 32-bit NEC word LSB-first: [addr][~addr][cmd][~cmd]
        data = (
            (address  & 0xFF)        |
            ((~address & 0xFF) << 8) |
            ((command  & 0xFF) << 16)|
            ((~command & 0xFF) << 24)
        )
        self._tx.mark(_HEAD_MARK)
        self._tx.space(_HEAD_SPACE)
        for bit in range(32):
            self._tx.mark(_BIT_MARK)
            if data & (1 << bit):
                self._tx.space(_SPACE_1)
            else:
                self._tx.space(_SPACE_0)
        self._tx.mark(_STOP_MARK)
        self._tx.idle()

    def send_repeat(self):
        """Send NEC repeat frame (for sustained button presses).

        NEC1 repeat: 9024µs mark | 2256µs space | 564µs mark | ~97.5 ms gap
        """
        self._tx.set_freq(_KHZ)
        self._tx.mark(_HEAD_MARK)
        self._tx.space(_REPEAT_SPACE)
        self._tx.mark(_STOP_MARK)
        self._tx.space(97572)
        self._tx.idle()
