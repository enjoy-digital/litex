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

    def test_periodic_timer_interrupts(self):
        # Counterpart to test_one_shot_timer_interrupts: with reload != 0 the timer must keep
        # firing the zero event on every reload cycle, not just once. Counts at least two
        # distinct zero events within a window long enough for several periods.
        def generator(timer):
            period = 10
            yield from timer._en.write(0)
            yield from timer._load.write(0)
            yield from timer._reload.write(period)
            yield from timer.ev.enable.write(1)
            yield from timer._en.write(1)

            firings = 0
            prev    = 0
            for _ in range(8*period):
                cur = (yield timer.ev.zero.trigger)
                if prev == 0 and cur == 1:
                    firings += 1
                prev = cur
                yield
            self.assertGreaterEqual(firings, 2,
                f"periodic zero event fired only {firings} times in 8 periods")

        timer = Timer()
        run_simulation(timer, generator(timer))
