#
# This file is part of LiteX.
#
# Copyright (c) 2021 Navaneeth Bhardwaj <navan93@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import subprocess
import unittest

class TestCPU(unittest.TestCase):
    def boot_test(self, cpu_type):
        cmd = 'lxsim --bios-test-mode --sim-debug --non-interactive --cpu-type={}'.format(cpu_type)
        cmd = cmd.split(' ')
        p = subprocess.run(cmd, stdout=subprocess.PIPE)
        result = str(p.stdout)
        if 'Bios successfully booted.' not in result or p.returncode != 0:
            print(result)
            self.fail()

    def test_vexriscv(self):
        self.boot_test("vexriscv")

    def test_vexriscv_smp(self):
        self.boot_test("vexriscv_smp")

    def test_cv32e40p(self):
        self.boot_test("cv32e40p")

    def test_ibex(self):
        self.boot_test("ibex")

    def test_serv(self):
        self.boot_test("serv")

    def test_femtorv(self):
        self.boot_test("femtorv")

    def test_picorv32(self):
        self.boot_test("picorv32")

    def test_minerva(self):
        self.boot_test("minerva")

