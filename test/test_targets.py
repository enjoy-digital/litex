import unittest
import os

from litex.gen import *

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
    def test_arty(self):
        from litex.boards.targets.arty import BaseSoC, MiniSoC
        errors = build_test([BaseSoC(), MiniSoC()])
        self.assertEqual(errors, 0)

    def test_de0nano(self):
        from litex.boards.targets.de0nano import BaseSoC
        errors = build_test([BaseSoC()])
        self.assertEqual(errors, 0)

    def test_kc705(self):
        from litex.boards.targets.kc705 import BaseSoC, MiniSoC
        errors = build_test([BaseSoC(), MiniSoC()])
        self.assertEqual(errors, 0)

    def test_minispartan6(self):
        from litex.boards.targets.minispartan6 import BaseSoC
        errors = build_test([BaseSoC()])
        self.assertEqual(errors, 0)

    def test_nexys_video(self):
        from litex.boards.targets.nexys_video import BaseSoC, MiniSoC
        errors = build_test([BaseSoC(), MiniSoC()])
        self.assertEqual(errors, 0)