#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.soc.cores.ram.efinix_hyperram import EfinixHyperRAM
from litex.soc.cores.ram.lattice_ice40 import Up5kSPRAM
from litex.soc.cores.ram.lattice_nx import NXLRAM, initval_parameters
from litex.soc.cores.ram.xilinx_fifo_sync_macro import FIFOSyncMacro

kB = 1024


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
            FIFOSyncMacro(data_width=73)
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            FIFOSyncMacro(fifo_size="72Kb")
        with self.assertRaisesRegex(ValueError, "up to 72 bits only for 36Kb"):
            FIFOSyncMacro("18Kb", data_width=64, toolchain="f4pga")
        with self.assertRaisesRegex(NotImplementedError, "DO_REG"):
            FIFOSyncMacro(do_reg=1, toolchain="f4pga")


class TestEfinixRAM(unittest.TestCase):
    def test_efinix_hyperram_rejects_missing_sys_clk_freq(self):
        with self.assertRaisesRegex(ValueError, "sys_clk_freq"):
            EfinixHyperRAM(platform=None, sys_clk_freq=None)

    def test_efinix_hyperram_rejects_too_fast_4x_clock(self):
        with self.assertRaisesRegex(ValueError, "4x clock"):
            EfinixHyperRAM(platform=None, sys_clk_freq=62.5e6)


if __name__ == "__main__":
    unittest.main()
