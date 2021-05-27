import unittest

from migen import *

from litex.soc.cores.timer import Timer

class TestTimer(unittest.TestCase):
    def test_one_shot_software_polling(self):
        def generator(timer):
            clock_cycles = 25
            yield from timer._en.write(0)
            yield from timer._load.write(clock_cycles)
            yield from timer._reload.write(0)
            yield from timer._en.write(1)
            yield from timer._update_value.write(1)
            yield
            self.assertTrue((yield timer._value.status) > 0)
            while (yield timer._value.status) > 0:
                yield from timer._update_value.write(1)
            yield
            self.assertEqual((yield timer._value.status), 0)

        timer = Timer()
        run_simulation(timer, generator(timer))

    def test_periodic_timer_software_polling(self):
        def generator(timer):
            clock_cycles = 25
            yield from timer._en.write(0)
            yield from timer._load.write(0)
            yield from timer._reload.write(clock_cycles)
            yield from timer._en.write(1)
            yield from timer._update_value.write(1)
            yield
            self.assertTrue((yield timer._value.status) > 0)
            while (yield timer._value.status) > 0:
                yield from timer._update_value.write(1)
            yield
            # Ensure that the timer reloads
            self.assertEqual((yield timer._value.status), clock_cycles)

        timer = Timer()
        run_simulation(timer, generator(timer))

    def test_one_shot_timer_interrupts(self):
        def generator(timer):
            clock_cycles = 25
            yield from timer._en.write(0)
            yield from timer._load.write(clock_cycles)
            yield from timer._reload.write(0)
            yield from timer.ev.enable.write(1)

            self.assertEqual(0, (yield timer.ev.zero.trigger))

            yield from timer._en.write(1)

            while (yield timer.ev.zero.trigger != 1) and clock_cycles >= -5:
                yield
                clock_cycles -= 1
            self.assertEqual(1, (yield timer.ev.zero.trigger))

        timer = Timer()
        run_simulation(timer, generator(timer))
