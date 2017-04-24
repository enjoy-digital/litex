import unittest

from litex.gen import *

from litex.soc.integration.builder import *


def build_test(socs):
    for soc in socs:
        builder = Builder(soc, output_dir="build", compile_software=False, compile_gateware=False)
        builder.build()


class TestTargets(unittest.TestCase):
    def test_arty(self):
        from litex.boards.targets.arty import BaseSoC, MiniSoC
        build_test([BaseSoC(), MiniSoC()])

    def test_de0nano(self):
        from litex.boards.targets.de0nano import BaseSoC
        build_test([BaseSoC()])

    def test_kc705(self):
        from litex.boards.targets.kc705 import BaseSoC, MiniSoC
        build_test([BaseSoC(), MiniSoC()])

    def test_minispartan6(self):
        from litex.boards.targets.minispartan6 import BaseSoC
        build_test([BaseSoC()])

    def test_nexys_video(self):
        from litex.boards.targets.nexys_video import BaseSoC, MiniSoC
        build_test([BaseSoC(), MiniSoC()])
