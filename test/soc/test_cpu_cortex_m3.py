#
# This file is part of LiteX.
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from migen import *

from litex.soc.cores.cpu.cortex_m3.core import CortexM3
from litex.soc.cores.cpu.cortex_m3.generic import CortexM3Generic
from litex.soc.interconnect import wishbone


def transfer(bus, address, data=None, size=2, sequential=False):
    yield bus.addr.eq(address)
    yield bus.size.eq(size)
    yield bus.trans.eq(3 if sequential else 2)
    if data is not None:
        yield bus.write.eq(1)
        yield bus.wdata.eq(data)
    else:
        yield bus.write.eq(0)
    yield
    yield bus.trans.eq(0)
    for _ in range(100):
        if not (yield bus.readyout):
            break
        yield
    else:
        raise AssertionError("AHB transfer did not start")
    for _ in range(100):
        if (yield bus.readyout):
            return (yield bus.rdata), (yield bus.resp)
        yield
    raise AssertionError("AHB transfer did not complete")


class TestCortexM3(unittest.TestCase):
    def test_sources_and_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ["CORTEXM3INTEGRATIONDS.v", "cortexm3ds_logic.v"]:
                (root / name).touch()
            # Source registration only: these files are not a processor model.
            platform = Mock()
            cpu = CortexM3(platform, variant="generic", rtl_dir=root)
            self.assertEqual(len(cpu.periph_buses), 3)
            self.assertTrue(all(isinstance(bus, wishbone.Interface) for bus in cpu.periph_buses))
            self.assertEqual(platform.add_source.call_count, 2)
            platform.add_source_dir.assert_not_called()
            cpu.finalize()
            self.assertIn("CORTEXM3INTEGRATIONDS", [s.of for s in cpu._fragment.specials if isinstance(s, Instance)])

        platform = Mock()
        cpu = CortexM3(platform)
        self.assertEqual(len(cpu.periph_buses), 2)
        platform.add_source_dir.assert_called_once_with(
            "AT426-BU-98000-r0p1-00rel0/vivado/Arm_ipi_repository/CM3DbgAXI/rtl")
        cpu.finalize()
        self.assertIn("CortexM3DbgAXI", [s.of for s in cpu._fragment.specials if isinstance(s, Instance)])

    def test_missing_sources(self):
        with patch.object(CortexM3, "rtl_dir", None):
            with self.assertRaisesRegex(ValueError, "--cpu-rtl-dir"):
                CortexM3(Mock(), variant="generic")
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "CORTEXM3INTEGRATIONDS.v").touch()
            platform = Mock()
            with self.assertRaisesRegex(FileNotFoundError, "cortexm3ds_logic.v"):
                CortexM3(platform, variant="generic", rtl_dir=directory)
            platform.add_source.assert_not_called()

    def test_cli_and_jtag(self):
        parser = argparse.ArgumentParser()
        CortexM3.args_fill(parser)
        with tempfile.TemporaryDirectory() as directory, patch.object(CortexM3, "rtl_dir", None):
            for name in ["CORTEXM3INTEGRATIONDS.v", "cortexm3ds_logic.v"]:
                (Path(directory) / name).touch()
            CortexM3.args_read(parser.parse_args(["--cpu-rtl-dir", directory]))
            cpu = CortexM3(Mock(), variant="generic")
            pads = Record([(name, 1) for name in ["tms", "tdi", "tdo", "ntrst", "tck"]])
            cpu.add_jtag(pads)
            self.assertEqual(cpu.cpu_params["i_DBGEN"], 1)
            self.assertIs(cpu.cpu_params["i_SWCLKTCK"], pads.tck)
            self.assertIs(cpu.cpu_params["o_TDO"], pads.tdo)
            self.assertNotIn("p_JTAG_PRESENT", cpu.cpu_params)
            self.assertNotIn("o_JTAGTOP", cpu.cpu_params)

    def test_three_buses_share_memory(self):
        dut = Module()
        dut.submodules.generic = generic = CortexM3Generic(Signal(), Signal(2))
        dut.submodules.ram = ram = wishbone.SRAM(256)
        dut.submodules.interconnect = wishbone.InterconnectShared(
            generic.periph_buses, [(lambda address: 1, ram.bus)])
        instruction, data, system = generic.ahb_buses

        def bench():
            self.assertEqual((yield from transfer(data, 0x20, 0x12345678))[1], 0)
            self.assertEqual((yield from transfer(instruction, 0x20)), (0x12345678, 0))
            yield from transfer(system, 0x21, 0x0000ab00, size=0)
            self.assertEqual((yield from transfer(data, 0x20)), (0x1234ab78, 0))
            yield from transfer(data, 0x22, 0xcdef0000, size=1)
            self.assertEqual((yield from transfer(system, 0x20)), (0xcdefab78, 0))
            yield from transfer(system, 0x24, 0xdeadbeef, sequential=True)
            self.assertEqual((yield from transfer(instruction, 0x24)), (0xdeadbeef, 0))

        run_simulation(dut, bench())

    def test_errors_and_wait_states(self):
        dut = CortexM3Generic(Signal(), Signal(2))

        def bench():
            for index, (bus, wb) in enumerate(zip(dut.ahb_buses, dut.periph_buses)):
                yield bus.addr.eq(0xa0000000 + 4*index)
                yield bus.size.eq(2)
                yield bus.trans.eq(2)
                yield
                yield bus.trans.eq(0)
                for _ in range(3):
                    yield
                self.assertEqual((yield wb.cyc), 1)
                self.assertEqual((yield wb.adr), 0x28000000 + index)
                self.assertEqual((yield bus.readyout), 0)
                yield wb.err.eq(1)
                yield
                yield
                self.assertEqual((yield bus.resp), 1)
                self.assertEqual((yield bus.readyout), 0)
                yield wb.err.eq(0)
                yield
                self.assertEqual((yield bus.resp), 1)
                self.assertEqual((yield bus.readyout), 1)
                yield
                self.assertEqual((yield bus.resp), 0)

        run_simulation(dut, bench())

    def test_concurrent_reads(self):
        dut = Module()
        dut.submodules.generic = generic = CortexM3Generic(Signal(), Signal(2))
        contents = [0x12340000 + index for index in range(64)]
        dut.submodules.ram = ram = wishbone.SRAM(256, init=contents)
        dut.submodules.interconnect = wishbone.InterconnectShared(
            generic.periph_buses, [(lambda address: 1, ram.bus)])

        def reader(bus, offset):
            for index in range(offset, offset + 4):
                self.assertEqual((yield from transfer(bus, 4*index)), (contents[index], 0))

        run_simulation(dut, [reader(bus, 4*index) for index, bus in enumerate(generic.ahb_buses)])

    def test_system_reset_releases_stalled_bridges(self):
        dut = CortexM3Generic(Signal(), Signal(2))

        def bench():
            for bus in dut.ahb_buses:
                yield bus.trans.eq(2)
                yield bus.size.eq(2)
            yield
            for bus in dut.ahb_buses:
                yield bus.trans.eq(0)
            yield
            yield
            for wb in dut.periph_buses:
                self.assertEqual((yield wb.cyc), 1)
            yield dut.sys_reset_request.eq(1)
            yield
            yield dut.sys_reset_request.eq(0)
            yield
            self.assertEqual((yield dut.sys_reset), 1)
            yield
            for wb in dut.periph_buses:
                self.assertEqual((yield wb.cyc), 0)
            for _ in range(5):
                yield
            self.assertEqual((yield dut.sys_reset), 0)
            for bus in dut.ahb_buses:
                self.assertEqual((yield bus.readyout), 1)

        run_simulation(dut, bench())
