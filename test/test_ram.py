#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
from types import SimpleNamespace

from migen import Array, If, Module, Signal, run_simulation
from migen.fhdl.specials import Instance

from litex.build.altera import AlteraPlatform
from litex.build.efinix import EfinixPlatform
from litex.soc.cores.ram.common import RAM_CAPABILITIES, get_cpu_ram_filename
from litex.soc.cores.ram.efinix_hyperram import (
    EFINIX_HYPERRAM_DYN_PHASE_SEL_WIDTH,
    EFINIX_HYPERRAM_MAX_PHY_CLK_FREQ,
    EfinixHyperRAM,
)
from litex.soc.cores.ram.lattice_ice40 import Up5kSPRAM
from litex.soc.cores.ram.lattice_nx import NXLRAM, initval_parameters
from litex.soc.cores.ram.xilinx_fifo_sync_macro import FIFOSyncMacro

kB = 1024


class _FakeEfinixIfaceWriter:
    def __init__(self):
        self.blocks = []

    def get_block(self, name):
        for block in self.blocks:
            if block["name"] == name:
                return block
        raise ValueError("Unknown block: {}.".format(name))


class _FakeEfinixHyperRAMPlatform:
    family = "Titanium"
    device = "Ti60"

    def __init__(self):
        self.toolchain = SimpleNamespace(
            ifacewriter  = _FakeEfinixIfaceWriter(),
            excluded_ios = [],
        )
        self.clks = {}
        self.extensions = []
        self._requests = {}
        self.pll_used = 0
        self.pll_available = 4

    def add_extension(self, extension):
        self.extensions += extension

    def request(self, name):
        if name not in self._requests:
            if name == "hyperram":
                self._requests[name] = SimpleNamespace(
                    clkp_h   = Signal(name="hyperram_clkp_h"),
                    clkp_l   = Signal(name="hyperram_clkp_l"),
                    clkn_h   = Signal(name="hyperram_clkn_h"),
                    clkn_l   = Signal(name="hyperram_clkn_l"),
                    dq_o_h   = Signal(16, name="hyperram_dq_o_h"),
                    dq_o_l   = Signal(16, name="hyperram_dq_o_l"),
                    dq_i_h   = Signal(16, name="hyperram_dq_i_h"),
                    dq_i_l   = Signal(16, name="hyperram_dq_i_l"),
                    dq_oe    = Signal(16, name="hyperram_dq_oe"),
                    rwds_o_h = Signal(2,  name="hyperram_rwds_o_h"),
                    rwds_o_l = Signal(2,  name="hyperram_rwds_o_l"),
                    rwds_i_h = Signal(2,  name="hyperram_rwds_i_h"),
                    rwds_i_l = Signal(2,  name="hyperram_rwds_i_l"),
                    rwds_oe  = Signal(2,  name="hyperram_rwds_oe"),
                    csn      = Signal(name="hyperram_csn"),
                    rstn     = Signal(name="hyperram_rstn"),
                )
            else:
                self._requests[name] = Signal(name=name)
        return self._requests[name]

    def add_iface_io(self, name):
        return Signal(name=name)

    def get_pin_name(self, clkin):
        return clkin.name_override

    def get_pin_location(self, clkin):
        return []

    def get_free_pll_resource(self):
        resource = "PLL{}".format(self.pll_used)
        self.pll_used += 1
        return resource


class _IgnoreInstance:
    @staticmethod
    def lower(instance):
        return Module()


class _SBSPRAM256KAModel(Module):
    @staticmethod
    def lower(instance):
        return _SBSPRAM256KAModel(instance)

    def __init__(self, instance):
        items = {
            item.name: item.expr
            for item in instance.items
            if hasattr(item, "expr")
        }
        mem = Array(Signal(16, reset=0) for _ in range(16))
        adr = Signal(4)

        self.comb += [
            adr.eq(items["ADDRESS"][:4]),
            items["DATAOUT"].eq(mem[adr]),
        ]
        for i in range(4):
            self.sync += If(items["WREN"] & items["CHIPSELECT"] & items["MASKWREN"][i],
                mem[adr][4*i:4*(i + 1)].eq(items["DATAIN"][4*i:4*(i + 1)]))


class _SP512KModel(Module):
    @staticmethod
    def lower(instance):
        return _SP512KModel(instance)

    def __init__(self, instance):
        items = {
            item.name: item.expr
            for item in instance.items
            if hasattr(item, "expr")
        }
        mem = Array(Signal(32, reset=0) for _ in range(16))
        adr = Signal(4)

        self.comb += [
            adr.eq(items["AD"][:4]),
            items["DO"].eq(mem[adr]),
        ]
        for i in range(4):
            self.sync += If(items["WE"] & items["CS"] & ~items["BYTEEN_N"][i],
                mem[adr][8*i:8*(i + 1)].eq(items["DI"][8*i:8*(i + 1)]))


class _LatticeRAMPrimitiveModel:
    @staticmethod
    def lower(instance):
        if instance.of == "SB_SPRAM256KA":
            return _SBSPRAM256KAModel(instance)
        if instance.of == "SP512K":
            return _SP512KModel(instance)
        return Module()


def instance_names(module):
    return [special.of for special in module.get_fragment().specials]


def parameter_dict(instance):
    return parameter_items_to_dict(instance.items)


def parameter_items_to_dict(items):
    return {
        item.name: item.value
        for item in items
        if hasattr(item, "value")
    }


class TestLatticeRAM(unittest.TestCase):
    def assert_wishbone_ack_pulses(self, dut):
        def generator():
            yield
            self.assertEqual((yield dut.bus.ack), 0)

            yield dut.bus.cyc.eq(1)
            yield dut.bus.stb.eq(1)
            yield
            self.assertEqual((yield dut.bus.ack), 0)
            yield
            self.assertEqual((yield dut.bus.ack), 1)
            yield
            self.assertEqual((yield dut.bus.ack), 0)

            yield dut.bus.cyc.eq(0)
            yield dut.bus.stb.eq(0)
            yield
            self.assertEqual((yield dut.bus.ack), 1)
            yield
            self.assertEqual((yield dut.bus.ack), 0)

        run_simulation(dut, generator(), special_overrides={Instance: _IgnoreInstance})

    def test_up5k_spram_primitive_count_matches_width_and_size(self):
        test_cases = [
            (16,  32*kB, 1),
            (16,  64*kB, 2),
            (32,  64*kB, 2),
            (64, 128*kB, 4),
        ]
        for width, size, count in test_cases:
            with self.subTest(width=width, size=size):
                instances = instance_names(Up5kSPRAM(width=width, size=size))
                self.assertEqual(instances, ["SB_SPRAM256KA"]*count)

    def test_up5k_spram_rejects_invalid_width_and_size(self):
        with self.assertRaisesRegex(ValueError, "width"):
            Up5kSPRAM(width=8)
        with self.assertRaisesRegex(ValueError, "size"):
            Up5kSPRAM(width=32, size=32*kB)

    def test_up5k_spram_wishbone_ack_pulses(self):
        self.assert_wishbone_ack_pulses(Up5kSPRAM(width=32, size=64*kB))

    def test_up5k_spram_writes_selected_byte_lanes(self):
        dut = Up5kSPRAM(width=32, size=64*kB)

        def generator():
            yield from dut.bus.write(0, 0x11223344)
            yield
            self.assertEqual((yield from dut.bus.read(0)), 0x11223344)
            yield from dut.bus.write(0, 0xaaaabbbb, sel=0b0101)
            yield
            self.assertEqual((yield from dut.bus.read(0)), 0x11aa33bb)

        run_simulation(dut, generator(), special_overrides={Instance: _LatticeRAMPrimitiveModel})

    def test_nxlram_primitive_count_matches_width_and_size(self):
        test_cases = [
            (32,  64*kB, 1),
            (32, 320*kB, 5),
            (64, 128*kB, 2),
            (64, 256*kB, 4),
        ]
        for width, size, count in test_cases:
            with self.subTest(width=width, size=size):
                instances = instance_names(NXLRAM(width=width, size=size))
                self.assertEqual(instances, ["SP512K"]*count)

    def test_nxlram_rejects_invalid_width_and_size(self):
        with self.assertRaisesRegex(ValueError, "width"):
            NXLRAM(width=16)
        with self.assertRaisesRegex(ValueError, "size"):
            NXLRAM(width=64, size=64*kB)

    def test_nxlram_wishbone_ack_pulses(self):
        self.assert_wishbone_ack_pulses(NXLRAM(width=32, size=64*kB))

    def test_nxlram_writes_selected_byte_lanes(self):
        dut = NXLRAM(width=64, size=128*kB)

        def generator():
            yield from dut.bus.write(0, 0x1122334455667788)
            yield
            self.assertEqual((yield from dut.bus.read(0)), 0x1122334455667788)
            yield from dut.bus.write(0, 0xaaaabbbbccccdddd, sel=0b01010101)
            yield
            self.assertEqual((yield from dut.bus.read(0)), 0x11aa33bb55cc77dd)

        run_simulation(dut, generator(), special_overrides={Instance: _LatticeRAMPrimitiveModel})

    def test_nxlram_initval_parameters_pack_32bit_words(self):
        contents = [0]*(524288//32)
        contents[0]   = 0x12345678
        contents[127] = 0x89abcdef

        params = parameter_items_to_dict(initval_parameters(contents, 32))
        initval = params["INITVAL_00"]

        self.assertEqual(len(initval), 2 + 1280)
        self.assertTrue(initval.startswith("0x0089ABCDEF"))
        self.assertTrue(initval.endswith("0012345678"))

    def test_nxlram_initval_parameters_pack_64bit_words(self):
        contents = [0]*(524288//64)
        contents[0] = 0x1234567890abcdef

        params = parameter_items_to_dict(initval_parameters(contents, 64))

        self.assertTrue(params["INITVAL_00"].endswith("00123456780090ABCDEF"))

    def test_nxlram_32bit_init_is_split_across_depth_blocks(self):
        words_per_block = 64*kB//4
        contents = [0x11111111] + [0]*(words_per_block - 1) + [0x22222222]

        ram = NXLRAM(width=32, size=128*kB, init=contents)

        block0 = parameter_dict(ram.lram_blocks[0][0])
        block1 = parameter_dict(ram.lram_blocks[1][0])
        self.assertTrue(block0["INITVAL_00"].endswith("0011111111"))
        self.assertTrue(block1["INITVAL_00"].endswith("0022222222"))

    def test_nxlram_64bit_init_is_split_across_width_blocks(self):
        contents = [0x1122334455667788]

        ram = NXLRAM(width=64, size=128*kB, init=contents)

        lower = parameter_dict(ram.lram_blocks[0][0])
        upper = parameter_dict(ram.lram_blocks[0][1])
        self.assertTrue(lower["INITVAL_00"].endswith("0055667788"))
        self.assertTrue(upper["INITVAL_00"].endswith("0011223344"))
        self.assertEqual(contents, [0x1122334455667788])

    def test_nxlram_rejects_init_longer_than_memory(self):
        with self.assertRaisesRegex(ValueError, "init length"):
            NXLRAM(width=32, size=64*kB, init=[0]*(64*kB//4 + 1))

    def test_nxlram_rejects_init_word_outside_width(self):
        with self.assertRaisesRegex(ValueError, "does not fit"):
            NXLRAM(width=32, size=64*kB, init=[1 << 32])
        with self.assertRaisesRegex(ValueError, "does not fit"):
            NXLRAM(width=64, size=128*kB, init=[-1])


class TestRAMCommon(unittest.TestCase):
    def test_ram_capabilities_describe_vendor_wrappers(self):
        self.assertEqual(RAM_CAPABILITIES["up5k_spram"].primitive, "SB_SPRAM256KA")
        self.assertIn(32, RAM_CAPABILITIES["up5k_spram"].data_widths)
        self.assertFalse(RAM_CAPABILITIES["up5k_spram"].init)

        self.assertEqual(RAM_CAPABILITIES["nx_lram"].primitive, "SP512K")
        self.assertIn(64, RAM_CAPABILITIES["nx_lram"].data_widths)
        self.assertTrue(RAM_CAPABILITIES["nx_lram"].byte_enable)

        self.assertEqual(RAM_CAPABILITIES["fifo_sync_macro"].ports, "fifo")
        self.assertIn("36Kb", RAM_CAPABILITIES["fifo_sync_macro"].sizes)


class TestCPURAM(unittest.TestCase):
    def test_cpu_ram_filename_selects_vendor_specific_1w_1rs(self):
        test_cases = [
            (object(),                         "Ram_1w_1rs_Generic.v"),
            (object.__new__(AlteraPlatform),   "Ram_1w_1rs_Intel.v"),
            (object.__new__(EfinixPlatform),   "Ram_1w_1rs_Efinix.v"),
        ]
        for platform, filename in test_cases:
            with self.subTest(filename=filename):
                self.assertEqual(get_cpu_ram_filename(platform, "1w_1rs"), filename)

    def test_cpu_ram_filename_falls_back_to_generic_lutram(self):
        self.assertEqual(
            get_cpu_ram_filename(object.__new__(EfinixPlatform), "1w_1ra"),
            "Ram_1w_1ra_Generic.v")

    def test_cpu_ram_filename_rejects_unknown_kind(self):
        with self.assertRaisesRegex(ValueError, "CPU RAM kind"):
            get_cpu_ram_filename(object(), "2w_2r")


class TestXilinxRAM(unittest.TestCase):
    def test_fifo_sync_macro_vivado_instantiates_unimacro(self):
        fifo = FIFOSyncMacro(
            "36Kb",
            data_width          = 64,
            almost_empty_offset = 10,
            almost_full_offset  = 20,
            do_reg              = 1,
            toolchain           = "vivado",
        )

        instance = list(fifo.get_fragment().specials)[0]
        params = parameter_dict(instance)

        self.assertEqual(instance.of, "FIFO_SYNC_MACRO")
        self.assertEqual(params["DEVICE"], "7SERIES")
        self.assertEqual(params["FIFO_SIZE"], "36Kb")
        self.assertEqual(params["DATA_WIDTH"].value, 64)
        self.assertEqual(params["ALMOST_EMPTY_OFFSET"].value, 10)
        self.assertEqual(params["ALMOST_FULL_OFFSET"].value, 20)
        self.assertEqual(params["DO_REG"].value, 1)

    def test_fifo_sync_macro_rejects_invalid_parameters(self):
        with self.assertRaisesRegex(ValueError, "data-width"):
            FIFOSyncMacro(data_width=0)
        with self.assertRaisesRegex(ValueError, "data-width"):
            FIFOSyncMacro(data_width=73)
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            FIFOSyncMacro(fifo_size="72Kb")
        with self.assertRaisesRegex(ValueError, "DO_REG"):
            FIFOSyncMacro(do_reg=2)
        with self.assertRaisesRegex(ValueError, "almost-empty"):
            FIFOSyncMacro("18Kb", data_width=32, almost_empty_offset=-1)
        with self.assertRaisesRegex(ValueError, "almost-full"):
            FIFOSyncMacro("18Kb", data_width=32, almost_full_offset=513)
        with self.assertRaisesRegex(ValueError, "up to 72 bits only for 36Kb"):
            FIFOSyncMacro("18Kb", data_width=64, toolchain="f4pga")
        with self.assertRaisesRegex(NotImplementedError, "DO_REG"):
            FIFOSyncMacro(do_reg=1, toolchain="f4pga")


class TestEfinixRAM(unittest.TestCase):
    def test_efinix_hyperram_rejects_missing_sys_clk_freq(self):
        with self.assertRaisesRegex(ValueError, "sys_clk_freq"):
            EfinixHyperRAM(platform=None, sys_clk_freq=None)

    def test_efinix_hyperram_rejects_non_positive_sys_clk_freq(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            EfinixHyperRAM(platform=None, sys_clk_freq=0)

    def test_efinix_hyperram_rejects_too_fast_4x_clock(self):
        with self.assertRaisesRegex(ValueError, "4x clock"):
            EfinixHyperRAM(platform=None, sys_clk_freq=EFINIX_HYPERRAM_MAX_PHY_CLK_FREQ/4)

    def test_efinix_hyperram_registers_interface_blocks(self):
        platform = _FakeEfinixHyperRAMPlatform()

        hyperram = EfinixHyperRAM(platform=platform, sys_clk_freq=50e6, with_csr=False)

        pll_block = platform.toolchain.ifacewriter.get_block(hyperram.pll.name)
        self.assertEqual(pll_block["type"], "PLL")
        self.assertIs(pll_block["shift_ena"], platform.request("shift_ena"))
        self.assertIs(pll_block["shift"],     platform.request("shift"))
        self.assertIs(pll_block["shift_sel"], platform.request("shift_sel"))
        self.assertEqual(len(platform.request("shift_sel")), EFINIX_HYPERRAM_DYN_PHASE_SEL_WIDTH)

        hyperram_blocks = [
            block for block in platform.toolchain.ifacewriter.blocks
            if block["type"] == "HYPERRAM"
        ]
        self.assertEqual(len(hyperram_blocks), 1)
        self.assertIs(hyperram_blocks[0]["pads"], hyperram.io_pads)
        self.assertIn(platform.request("shift_ena"), platform.toolchain.excluded_ios)
        self.assertIn(hyperram.io_pads.csn, platform.toolchain.excluded_ios)


if __name__ == "__main__":
    unittest.main()
