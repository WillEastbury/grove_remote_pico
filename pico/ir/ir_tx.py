"""
IR Transmitter base driver for Raspberry Pi Pico 2 W.
Uses machine.PWM on GP26 (Grove Shield port A0) to generate the carrier.

mark()/space() are the only interface the protocol encoders call, so this
class can be swapped for a PIO-based implementation without changing any
protocol code — just replace IRTransmitter with a PIO subclass.
"""

from machine import Pin, PWM
from time import sleep_us, sleep_ms

IR_PIN = 26  # Grove Shield for Pi Pico: port A0 signal pin = GP26


class IRTransmitter:
    # 50% duty cycle — maximises optical output per cycle. The Grove module
    # has its own driver transistor + current limiter so this is safe.
    # Cheap IR LEDs need this; 33% often produces signal too weak for TVs.
    _DUTY_ON = int(65535 * 0.50)

    def __init__(self, pin: int = IR_PIN):
        self._pin = pin
        self._pwm = PWM(Pin(pin))
        self._current_khz = 0
        self._pwm.duty_u16(0)

    def set_freq(self, khz: int):
        """Set carrier frequency (e.g. 38 for NEC, 36 for RC5, 40 for Sony).

        Re-initialises the PWM so the new frequency takes effect cleanly,
        with the output starting in the OFF state.
        """
        if khz != self._current_khz:
            self._current_khz = khz
            self._pwm.freq(khz * 1000)
            self._pwm.duty_u16(0)

    def mark(self, us: int):
        """Modulated carrier burst for `us` microseconds."""
        self._pwm.duty_u16(self._DUTY_ON)
        sleep_us(us)
        # Important: turn carrier OFF at end of mark so the following space
        # is truly silent even if sleep_us inside space() jitters.
        self._pwm.duty_u16(0)

    def space(self, us: int):
        """Carrier off for `us` microseconds."""
        self._pwm.duty_u16(0)
        sleep_us(us)

    def idle(self):
        """Ensure carrier is off between commands."""
        self._pwm.duty_u16(0)

    def self_test(self, seconds: float = 2.0, khz: int = 38):
        """Hold a continuous 38 kHz carrier for N seconds.

        Use this to verify the LED + wiring + driver: an IR receiver module
        will go LOW for the whole burst.  Useful when no camera is available
        to see the LED directly.
        """
        self.set_freq(khz)
        self._pwm.duty_u16(self._DUTY_ON)
        sleep_ms(int(seconds * 1000))
        self._pwm.duty_u16(0)
