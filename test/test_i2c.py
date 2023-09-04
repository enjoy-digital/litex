#!/usr/bin/env python3
#
# This file is part of MiSoC and has been adapted/modified for Litex.
#
# Copyright 2007-2023 / M-Labs Ltd
# Copyright 2012-2015 / Enjoy-Digital
# Copyright from Misoc LICENCE file added above
#
# Copyright 2023 Andrew Dennison <andrew@motec.com.au>
#
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *
from migen.fhdl.specials import Tristate

from litex.soc.cores.i2c import *


class _MockPads:
    def __init__(self):
        self.scl = Signal()
        self.sda = Signal()


class _MockTristateImpl(Module):
    def __init__(self, t):
        t.i_mock = Signal(reset=True)
        self.comb += [
            If(t.oe,
                t.target.eq(t.o),
                t.i.eq(t.o),
            ).Else(
                t.target.eq(t.i_mock),
                t.i.eq(t.i_mock),
            ),
        ]


class _MockTristate:
    """A mock `Tristate` for simulation

    This simulation ensures the TriState input (_i) tracks the output (_o) when output enable
    (_oe) = 1. A new i_mock `Signal` is added  - this can be written to in the simulation to represent
    input from the external device.

    Example usage:

    class TestMyModule(unittest.TestCase):
        def test_mymodule(self):
            dut = MyModule()
            io = Signal()
            dut.io_t = TSTriple()
            self.io_tristate = self.io_t.get_tristate(io)

            dut.comb += [
                dut.io_t.oe.eq(signal_for_oe),
                dut.io_t.o.eq(signal_for_o),
                signal_for_i.eq(dut.io_t.i),
            ]

    def generator()
        yield dut.io_tristate.i_mock.eq(some_value)
        if (yield dut.io_t.oe):
            self.assertEqual((yield dut.scl_t.i), (yield dut.io_t.o))
        else:
            self.assertEqual((yield dut.scl_t.i), some_value)

    """

    @staticmethod
    def lower(t):
        return _MockTristateImpl(t)


class TestI2C(unittest.TestCase):
    def test_i2c(self):
        pads = _MockPads()
        dut = I2CMaster(pads)

        def check_trans(scl, sda, msg=""):
            scl, sda = int(scl), int(sda)
            scl_init, sda_init = (yield dut.scl_t.i), (yield dut.sda_t.i)
            timeout = 0
            while True:
                scl_now, sda_now = (yield dut.scl_t.i), (yield dut.sda_t.i)
                if scl_now == scl and sda_now == sda:
                    return
                timeout += 1
                self.assertLess(timeout, 20,
                    f"\n*** {msg} timeout. Waiting for: " +
                    f"scl:{scl_now} checking:{scl_init}=>{scl} " +
                    f"sda:{sda_now} checking:{sda_init}=>{sda} ***"
                )
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
            # print(f"write_bit:{value}")
            yield from check_trans(scl=False, sda=value)
            yield from check_trans(scl=True, sda=value)

        def write_ack(value):
            # print(f"write_ack:{value}")
            yield from check_trans(scl=False, sda=not value)
            yield from check_trans(scl=True, sda=not value)
            yield from wait_idle()

        def read_bit(value):
            print(f"read_bit:{value}")
            yield dut.sda_tristate.i_mock.eq(value)
            yield from check_trans(scl=True, sda=value)
            yield from check_trans(scl=False, sda=value)
            yield dut.sda_tristate.i_mock.eq(True)

        def read_ack(value):
            #print(f"read_ack:{value}")
            yield from check_trans(scl=False, sda=True)
            yield dut.sda_tristate.i_mock.eq(not value)
            yield from check_trans(scl=True,  sda=not value)
            yield from wait_idle()
            yield dut.sda_tristate.i_mock.eq(True)
            ack = ((yield from dut.bus.read(I2C_XFER_ADDR)) & I2C_ACK) != 0
            self.assertEqual(ack, value)

        def i2c_restart():
            yield from check_trans(scl=False, sda=True, msg="checking restart precondition")
            yield from dut.bus.write(I2C_XFER_ADDR, I2C_START)
            yield from check_trans(scl=False, sda=True, msg="checking restart0")
            yield from check_trans(scl=True, sda=True, msg="checking restart1")
            yield from check_trans(scl=True, sda=False, msg="checking start0")
            yield from wait_idle()

        def i2c_start():
            yield from check_trans(scl=True, sda=True, msg="checking start precondition")
            yield from dut.bus.write(I2C_XFER_ADDR, I2C_START)
            yield from check_trans(scl=True, sda=False, msg="checking start0")
            yield from wait_idle()

        def i2c_stop():
            yield from check_trans(scl=False, sda=True, msg="checking stop after read or write")
            yield from dut.bus.write(I2C_XFER_ADDR, I2C_STOP)
            yield from check_trans(scl=False, sda=False, msg="checking STOP0")
            yield from check_trans(scl=True, sda=False, msg="checking STOP1")
            yield from check_trans(scl=True, sda=True, msg="checking STOP2")
            yield from wait_idle()

        def i2c_write(value, ack=True):
            value = int(value)
            test_bin = "{0:08b}".format(value)
            # print(f"I2C_WRITE | {hex(value)}:0x{test_bin}")
            yield from dut.bus.write(I2C_XFER_ADDR, I2C_WRITE | value)
            for i in list(test_bin):
                yield from write_bit(int(i))
            yield from read_ack(True)

        def i2c_read(value, ack=True):
            value = int(value)
            test_bin = "{0:08b}".format(value)
            print(f"I2C_READ | {hex(value)}:0x{test_bin}")
            yield from dut.bus.write(I2C_XFER_ADDR, I2C_READ | (I2C_ACK if ack else 0))
            for i in list(test_bin):
                yield from read_bit(int(i))
            yield dut.sda_tristate.i_mock.eq(True)
            data = (yield from dut.bus.read(I2C_XFER_ADDR)) & 0xFF
            self.assertEqual(data, value)
            yield from write_ack(ack)

        def check():
            yield from dut.bus.write(I2C_CONFIG_ADDR, 4)
            data = (yield from dut.bus.read(I2C_CONFIG_ADDR)) & 0xFF
            self.assertEqual(data, 4)

            print("write 1 byte 0x18 to address 0x41")
            yield from i2c_start()
            yield from i2c_write(0x41 << 1 | 0)
            yield from i2c_write(0x18, ack=False)
            yield from i2c_stop()

            print("read 1 byte from address 0x41")
            yield from i2c_start()
            yield from i2c_write(0x41 << 1 | 1)
            yield from i2c_read(0x18, ack=False)

            print("write 2 bytes 0x10 0x00 to address 0x11")
            yield from i2c_restart()
            yield from i2c_write(0x11 << 1 | 0)
            yield from i2c_write(0x10, ack=True)
            yield from i2c_write(0x00, ack=False)
            yield from i2c_stop()

            print("read 1 byte from address 0x11")
            yield from i2c_start()
            yield from i2c_write(0x11 << 1 | 1)
            yield from i2c_read(0x81, ack=False)

            print("read 2 bytes from address 0x55")
            yield from i2c_restart()
            yield from i2c_write(0x55 << 1 | 1)
            yield from i2c_read(0xDE, ack=True)
            yield from i2c_read(0xAD, ack=False)
            yield from i2c_stop()

        clocks = {
            "sys": 10,
            "async": (10, 3),
        }
        generators = {
            "sys": [
                check(),
            ],
        }
        run_simulation(dut, generators, clocks, special_overrides={Tristate: _MockTristate}, vcd_name="i2c.vcd")

if __name__ == "__main__":
    unittest.main()
