"""
IR Transmitter base driver for Raspberry Pi Pico 2 W.
Uses machine.PWM on GP26 (Grove Shield port A0) to generate the carrier.

mark()/space() are the only interface the protocol encoders call, so this
class can be swapped for a PIO-based implementation without changing any
protocol code — just replace IRTransmitter with a PIO subclass.
"""

from machine import Pin, PWM
from time import sleep_us

IR_PIN = 26  # Grove Shield for Pi Pico: port A0 signal pin = GP26


class IRTransmitter:
    # 33% duty cycle — higher peak current, avoids overdriving the Grove IR LED.
    # Grove IR transmitter module has its own driver transistor so this is safe.
    _DUTY_33 = int(65535 * 0.33)

    def __init__(self, pin: int = IR_PIN):
        self._pwm = PWM(Pin(pin))
        self._current_khz = 0
        self._pwm.duty_u16(0)

    def set_freq(self, khz: int):
        """Set carrier frequency (e.g. 38 for NEC, 36 for RC5, 40 for Sony)."""
        if khz != self._current_khz:
            self._current_khz = khz
            self._pwm.freq(khz * 1000)

    def mark(self, us: int):
        """Modulated carrier burst for `us` microseconds."""
        self._pwm.duty_u16(self._DUTY_33)
        sleep_us(us)

    def space(self, us: int):
        """Carrier off for `us` microseconds."""
        self._pwm.duty_u16(0)
        sleep_us(us)

    def idle(self):
        """Ensure carrier is off between commands."""
        self._pwm.duty_u16(0)
