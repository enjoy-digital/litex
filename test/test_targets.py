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
    # Altera boards
    def test_de0nano(self):
        from litex.boards.targets.de0nano import BaseSoC
        errors = build_test([BaseSoC()])
        self.assertEqual(errors, 0)

    # Xilinx boards
    # Spartan-6
    def test_minispartan6(self):
        from litex.boards.targets.minispartan6 import BaseSoC
        errors = build_test([BaseSoC()])
        self.assertEqual(errors, 0)

    # Artix-7
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

    # Kintex-7
    def test_genesys2(self):
        from litex.boards.targets.genesys2 import BaseSoC, EthernetSoC
        errors = build_test([BaseSoC(), EthernetSoC()])
        self.assertEqual(errors, 0)

    def test_kc705(self):
        from litex.boards.targets.kc705 import BaseSoC, EthernetSoC
        errors = build_test([BaseSoC(), EthernetSoC()])
        self.assertEqual(errors, 0)

    # Kintex-Ultrascale
    def test_kcu105(self):
        from litex.boards.targets.kcu105 import BaseSoC
        errors = build_test([BaseSoC()])
        self.assertEqual(errors, 0)

    # Lattice boards
    # ECP5
    def test_versa_ecp5(self):
        from litex.boards.targets.versa_ecp5 import BaseSoC
        errors = build_test([BaseSoC()])
        self.assertEqual(errors, 0)

    def test_versa_ulx3s(self):
        from litex.boards.targets.ulx3s import BaseSoC
        errors = build_test([BaseSoC()])
        self.assertEqual(errors, 0)

    # Build simple design for all platforms
    def test_simple(self):
        platforms = []
        # Xilinx
        platforms += ["minispartan6", "sp605"]                     # Spartan6
        platforms += ["arty", "nexys4ddr", "nexys_video", "ac701"] # Artix7
        platforms += ["kc705", "genesys2"]                         # Kintex7
        platforms += ["kcu105"]                                    # Kintex Ultrascale

        # Altera
        platforms += ["de0nano"]                                   # Cyclone4

        # Lattice
        platforms += ["tinyfpga_bx"]                               # iCE40
        platforms += ["machxo3"]                                   # MachXO3
        platforms += ["versa_ecp3"]                                # ECP3
        platforms += ["versa_ecp5", "ulx3s"]                       # ECP5

        # Microsemi
        platforms += ["avalanche"]                                 # PolarFire

        for p in platforms:
            os.system("litex/boards/targets/simple.py litex.boards.platforms." + p +
                " --cpu-type=vexriscv " +
                " --no-compile-software " +
                " --no-compile-gateware " +
                " --uart-stub=True")
