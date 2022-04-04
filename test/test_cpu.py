#
# This file is part of LiteX.
#
# Copyright (c) 2021 Navaneeth Bhardwaj <navan93@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import pexpect
import sys

class TestCPU(unittest.TestCase):
    def boot_test(self, cpu_type, cpu_variant="standard"):
        cmd = f'litex_sim --cpu-type={cpu_type} --cpu-variant={cpu_variant}'
        litex_prompt = [b'\033\[[0-9;]+mlitex\033\[[0-9;]+m>']
        is_success = True
        with open("/tmp/test_boot_log", "wb") as result_file:
            p = pexpect.spawn(cmd, timeout=None, logfile=result_file)
            try:
                match_id = p.expect(litex_prompt, timeout=1200)
            except pexpect.EOF:
                print('\n*** Premature termination')
                is_success = False
            except pexpect.TIMEOUT:
                print('\n*** Timeout ')
                is_success = False

        if not is_success:
            print(f'*** {cpu_type} Boot Failure')
            with open("/tmp/test_boot_log", "r") as result_file:
                print(result_file.read())
        else:
            p.terminate(force=True)
            print(f'*** {cpu_type} Boot Success')

        return is_success

    # RISC-V CPUs.
    def test_vexriscv(self):
        self.assertTrue(self.boot_test("vexriscv"))

    def test_vexriscv_smp(self):
        self.assertTrue(self.boot_test("vexriscv_smp"))

    def test_cv32e40p(self):
        self.assertTrue(self.boot_test("cv32e40p"))

    def test_ibex(self):
        self.assertTrue(self.boot_test("ibex"))

    def test_serv(self):
        self.assertTrue(self.boot_test("serv"))

    def test_femtorv(self):
        self.assertTrue(self.boot_test("femtorv"))

    def test_picorv32(self):
        self.assertTrue(self.boot_test("picorv32"))

    # OpenRISC CPUs.
    #def test_mor1kx(self):
    #    self.assertTrue(self.boot_test("mor1kx"))

    # PowerPC CPUs.
    #def test_microwatt(self):
    #    self.assertTrue(self.boot_test("microwatt", cpu_variant="standard+ghdl"))

    # LM32 CPUs.
    #def test_lm32(self):
    #    self.assertTrue(self.boot_test("lm32"))
