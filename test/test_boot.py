#
# This file is part of LiteX.
#
# Copyright (c) 2021 Navaneeth Bhardwaj <navan93@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import pexpect
import sys

class TestCPU(unittest.TestCase):
    def boot_test(self, cpu_type):
        cmd = 'lxsim --cpu-type={}'.format(cpu_type)
        litex_prompt = [b'\033\[92;1mlitex\033\[0m>']
        p = pexpect.spawn(cmd, timeout=None, logfile=sys.stdout.buffer)
        try:
            match_id = p.expect(litex_prompt, timeout=1200)
        except pexpect.EOF:
            print('\n*** Premature termination')
            return False
        except pexpect.TIMEOUT:
            print('\n*** Timeout ')
            return False

        is_success = True

        # Let it print rest of line
        match_id = p.expect_exact([b'\n', pexpect.TIMEOUT, pexpect.EOF], timeout=1)
        p.terminate(force=True)

        line_break = '\n' if match_id != 0 else ''
        print(f'{line_break}*** {"Success" if is_success else "Failure"}')

        return is_success

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

    def test_minerva(self):
        self.assertTrue(self.boot_test("minerva"))

