# This file is Copyright (c) 2017-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Tim 'mithro' Ansell <me@mith.ro>
# License: BSD

import subprocess
import unittest
import os

from migen import *

from litex.soc.integration.builder import *


RUNNING_ON_TRAVIS = (os.getenv('TRAVIS', 'false').lower() == 'true')


def build_test(socs):
    errors = 0
    for soc in socs:
        os.system("rm -rf build")
        builder = Builder(soc, compile_software=False, compile_gateware=False)
        builder.build()
        errors += not os.path.isfile("build/{build_name}/gateware/{build_name}.v".format(build_name=soc.build_name))
    os.system("rm -rf build")
    return errors

test_kwargs = {
    "integrated_rom_size": 0x8000,
    "max_sdram_size": 0x4000000
}

class TestTargets(unittest.TestCase):
    # Altera boards
    def test_de0nano(self):
        from litex.boards.targets.de0nano import BaseSoC
        errors = build_test([BaseSoC(**test_kwargs)])
        self.assertEqual(errors, 0)

    # Xilinx boards
    # Spartan-6
    def test_minispartan6(self):
        from litex.boards.targets.minispartan6 import BaseSoC
        errors = build_test([BaseSoC(**test_kwargs)])
        self.assertEqual(errors, 0)

    # Artix-7
    def test_arty(self):
        from litex.boards.targets.arty import BaseSoC
        errors = build_test([
            BaseSoC(**test_kwargs),
            BaseSoC(with_ethernet=True, **test_kwargs)
        ])
        self.assertEqual(errors, 0)

    def test_netv2(self):
        from litex.boards.targets.netv2 import BaseSoC
        errors = build_test([
            BaseSoC(**test_kwargs),
            BaseSoC(with_ethernet=True, **test_kwargs)
        ])
        self.assertEqual(errors, 0)

    def test_nexys4ddr(self):
        from litex.boards.targets.nexys4ddr import BaseSoC
        errors = build_test([BaseSoC(**test_kwargs)])
        self.assertEqual(errors, 0)

    def test_nexys_video(self):
        from litex.boards.targets.nexys_video import BaseSoC
        errors = build_test([
            BaseSoC(**test_kwargs),
            BaseSoC(with_ethernet=True, **test_kwargs)
        ])
        self.assertEqual(errors, 0)

    def test_arty_symbiflow(self):
        from litex.boards.targets.arty import BaseSoC
        errors = build_test([
            BaseSoC(toolchain="symbiflow", **test_kwargs)
        ])
        self.assertEqual(errors, 0)

    # Kintex-7
    def test_genesys2(self):
        from litex.boards.targets.genesys2 import BaseSoC
        errors = build_test([
            BaseSoC(**test_kwargs),
            BaseSoC(with_ethernet=True, **test_kwargs)
        ])
        self.assertEqual(errors, 0)

    def test_kc705(self):
        from litex.boards.targets.kc705 import BaseSoC
        errors = build_test([
            BaseSoC(**test_kwargs),
            BaseSoC(with_ethernet=True, **test_kwargs)
        ])
        self.assertEqual(errors, 0)

    # Kintex-Ultrascale
    def test_kcu105(self):
        from litex.boards.targets.kcu105 import BaseSoC
        errors = build_test([BaseSoC(**test_kwargs)])
        self.assertEqual(errors, 0)

    # Lattice boards
    # ECP5
    def test_versa_ecp5(self):
        from litex.boards.targets.versa_ecp5 import BaseSoC
        errors = build_test([BaseSoC(**test_kwargs)])
        self.assertEqual(errors, 0)

    def test_ulx3s(self):
        from litex.boards.targets.ulx3s import BaseSoC
        errors = build_test([BaseSoC(**test_kwargs)])
        self.assertEqual(errors, 0)

    # Build simple design for all platforms
    def test_simple(self):
        platforms = []
        # Xilinx
        platforms += ["minispartan6"]                              # Spartan6
        platforms += ["arty", "netv2", "nexys4ddr", "nexys_video"] # Artix7
        platforms += ["kc705", "genesys2"]                         # Kintex7
        platforms += ["kcu105"]                                    # Kintex Ultrascale

        # Altera/Intel
        platforms += ["de0nano"]                                   # Cyclone4

        # Lattice
        platforms += ["tinyfpga_bx"]                               # iCE40
        platforms += ["machxo3"]                                   # MachXO3
        platforms += ["versa_ecp5", "ulx3s"]                       # ECP5

        # Microsemi
        platforms += ["avalanche"]                                 # PolarFire

        for p in platforms:
            with self.subTest(platform=p):
                cmd = """\
litex/boards/targets/simple.py litex.boards.platforms.{p} \
    --cpu-type=vexriscv     \
    --no-compile-software   \
    --uart-name=stub        \
""".format(p=p)
                subprocess.check_call(cmd, shell=True)

    def test_z_cpu_none(self): # FIXME: workaround to execute it last.
        from litex.boards.targets.arty import BaseSoC
        errors = build_test([BaseSoC(cpu_type=None)])
        self.assertEqual(errors, 0)

    def run_variants(self, cpu, variants):
        for v in variants:
            with self.subTest(cpu=cpu, variant=v):
                self.run_variant(cpu, v)

    def run_variant(self, cpu, variant):
        cmd = """\
litex/boards/targets/simple.py litex.boards.platforms.arty \
    --cpu-type={c}          \
    --cpu-variant={v}       \
    --no-compile-software   \
    --uart-name=stub        \
""".format(c=cpu, v=variant)
        subprocess.check_output(cmd, shell=True)

    # Build some variants for the arty platform to make sure they work.
    def test_variants_picorv32(self):
        self.run_variants("picorv32", ('standard', 'minimal'))

    def test_variants_vexriscv(self):
        self.run_variants("vexriscv", ('standard', 'minimal', 'lite', 'lite+debug', 'full+debug'))

    @unittest.skipIf(RUNNING_ON_TRAVIS, "No nMigen/Yosys on Travis-CI")
    def test_variants_minerva(self):
        self.run_variants("minerva", ('standard',))

    def test_variants_vexriscv(self):
        cpu_variants = {
            'vexriscv': ('standard', 'minimal', 'lite', 'lite+debug', 'full+debug'),
        }
        for cpu, variants in cpu_variants.items():
            self.run_variants(cpu, variants)

    @unittest.skipIf(RUNNING_ON_TRAVIS, "No lm32 toolchain on Travis-CI")
    def test_variants_lm32(self):
        self.run_variants('lm32', ('standard', 'minimal', 'lite'))

    @unittest.skipIf(RUNNING_ON_TRAVIS, "No or1k toolchain on Travis-CI")
    def test_variants_mor1kx(self):
        self.run_variants('mor1kx', ('standard', 'linux'))
