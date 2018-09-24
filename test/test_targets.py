import unittest
import os

from migen import *

from litex.soc.integration.builder import *


def build_test(socs):
    errors = 0
    for soc in socs:
        os.system("rm -rf build")
        builder = Builder(soc, output_dir="./build", compile_software=False, compile_gateware=False)
        builder.build()
        errors += not os.path.isfile("./build/gateware/top.v")
    os.system("rm -rf build")
    return errors


class TestTargets(unittest.TestCase):
    # altera boards
    def test_de0nano(self):
        from litex.boards.targets.de0nano import BaseSoC
        errors = build_test([BaseSoC()])
        self.assertEqual(errors, 0)

    # xilinx boards
    def test_minispartan6(self):
        from litex.boards.targets.minispartan6 import BaseSoC
        errors = build_test([BaseSoC()])
        self.assertEqual(errors, 0)

    def test_arty(self):
        from litex.boards.targets.arty import BaseSoC, EthernetSoC
        errors = build_test([BaseSoC(), EthernetSoC()])
        self.assertEqual(errors, 0)

    def test_nexys4ddr(self):
        from litex.boards.targets.nexys4ddr import BaseSoC
        errors = build_test([BaseSoC()])
        self.assertEqual(errors, 0)

    def test_nexys_video(self):
        from litex.boards.targets.nexys_video import BaseSoC, EthernetSoC
        errors = build_test([BaseSoC(), EthernetSoC()])
        self.assertEqual(errors, 0)

    def test_genesys2(self):
        from litex.boards.targets.genesys2 import BaseSoC, EthernetSoC
        errors = build_test([BaseSoC(), EthernetSoC()])
        self.assertEqual(errors, 0)

    def test_kc705(self):
        from litex.boards.targets.kc705 import BaseSoC, EthernetSoC
        errors = build_test([BaseSoC(), EthernetSoC()])
        self.assertEqual(errors, 0)

    # lattice boards

    # build simple design for all platforms
    def test_simple(self):
        platforms = [
            "arty",
            "arty_s7",
            "de0nano",
            "genesys2",
            "icestick",
            "kc705",
            "kcu105",
            "machxo3",
            "mercury",
            "mimasv2",
            "minispartan6",
            "nexys4ddr",
            "nexys_video",
            "papilio_pro",
            "tinyfpga_b",
            "tinyfpga_bx",
            "versa",
            "versaecp55g"
        ]
        for p in platforms:
            os.system("litex_simple litex.boards.platforms." + p +
                " --no-compile-software " +
                " --no-compile-gateware " +
                " --uart-stub=True")
