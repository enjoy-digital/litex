import unittest

from migen import *
from migen.fhdl.specials import Tristate

from misoc.cores.i2c import *


class _MockPads:
    def __init__(self):
        self.scl = Signal()
        self.sda = Signal()


class _MockTristateImpl(Module):
    def __init__(self, t):
        oe = Signal()
        self.comb += [
            t.target.eq(t.o),
            oe.eq(t.oe),
        ]


class _MockTristate:
    @staticmethod
    def lower(t):
        return _MockTristateImpl(t)


class TestI2C(unittest.TestCase):
    def test_i2c(self):
        pads = _MockPads()
        dut = I2CMaster(pads)

        def check_trans(scl, sda):
            scl_init, sda_init = (yield dut.i2c.scl_o), (yield dut.i2c.sda_o)
            timeout = 0
            while True:
                timeout += 1
                self.assertLess(timeout, 20)
                scl_now, sda_now = (yield dut.i2c.scl_o), (yield dut.i2c.sda_o)
                if scl_now != scl_init or sda_now != sda_init:
                    self.assertEqual(scl_now, scl)
                    self.assertEqual(sda_now, sda)
                    return
                yield

        def wait_idle(do=lambda: ()):
            timeout = 0
            while True:
                timeout += 1
                self.assertLess(timeout, 20)
                idle = ((yield from dut.bus.read(I2C_XFER_ADDR)) & I2C_IDLE) != 0
                if idle:
                    return
                yield

        def write_bit(value):
            yield from check_trans(scl=False, sda=value)
            yield from check_trans(scl=True,  sda=value)

        def write_ack(value):
            yield from check_trans(scl=False, sda=not value)
            yield from check_trans(scl=True,  sda=not value)
            yield from wait_idle()

        def read_bit(value):
            yield from check_trans(scl=False, sda=True)
            yield dut.sda_t.i.eq(value)
            yield from check_trans(scl=True,  sda=True)

        def read_ack(value):
            yield from check_trans(scl=False, sda=True)
            yield dut.sda_t.i.eq(not value)
            yield from check_trans(scl=True,  sda=True)
            yield from wait_idle()
            ack = ((yield from dut.bus.read(I2C_XFER_ADDR)) & I2C_ACK) != 0
            self.assertEqual(ack, value)

        def check():
            yield from dut.bus.write(I2C_CONFIG_ADDR, 4)

            yield from dut.bus.write(I2C_XFER_ADDR, I2C_START)
            yield from check_trans(scl=True, sda=False)
            yield from wait_idle()

            yield from dut.bus.write(I2C_XFER_ADDR, I2C_WRITE | 0x82)
            for i in [True, False, False, False, False, False, True, False]:
                yield from write_bit(i)
            yield from read_ack(True)

            yield from dut.bus.write(I2C_XFER_ADDR, I2C_WRITE | 0x18)
            for i in [False, False, False, True, True, False, False, False]:
                yield from write_bit(i)
            yield from read_ack(False)

            yield from dut.bus.write(I2C_XFER_ADDR, I2C_START | I2C_STOP)
            yield from check_trans(scl=True,  sda=False)
            yield from wait_idle()

            yield from dut.bus.write(I2C_XFER_ADDR, I2C_READ)
            for i in [False, False, False, True, True, False, False, False]:
                yield from read_bit(i)
            data = (yield from dut.bus.read(I2C_XFER_ADDR)) & 0xff
            self.assertEqual(data, 0x18)
            yield from write_ack(False)

            yield from dut.bus.write(I2C_XFER_ADDR, I2C_READ | I2C_ACK)
            for i in [True, False, False, False, True, False, False, False]:
                yield from read_bit(i)
            data = (yield dut.i2c.data)
            self.assertEqual(data, 0x88)
            yield from write_ack(True)

            yield from dut.bus.write(I2C_XFER_ADDR, I2C_STOP)
            yield from check_trans(scl=False,  sda=False)
            yield from wait_idle()

        run_simulation(dut, check(), special_overrides={Tristate: _MockTristate})
