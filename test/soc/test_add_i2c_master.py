#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import logging
import sys
import types
import unittest
from unittest import mock

from litex.soc.integration.soc import LiteXSoC, SoCError

# Helpers ------------------------------------------------------------------------------------------

class _FakeLiteI2C:
    def __init__(self, sys_clk_freq, pads=None, **kwargs):
        self.sys_clk_freq = sys_clk_freq
        self.kwargs       = kwargs


def _fake_soc():
    return types.SimpleNamespace(
        logger           = logging.getLogger("test_add_i2c_master"),
        sys_clk_freq     = int(100e6),
        irq              = types.SimpleNamespace(enabled=False, locs={}),
        check_if_exists  = lambda name: None,
        add_module       = lambda name, module: setattr(soc_modules, name, module),
    )

soc_modules = types.SimpleNamespace()


def _add_i2c_master(soc, **kwargs):
    fake = types.ModuleType("litei2c")
    fake.LiteI2C = _FakeLiteI2C
    with mock.patch.dict(sys.modules, {"litei2c": fake}):
        LiteXSoC.add_i2c_master(soc, pads=object(), **kwargs)
    return soc_modules.i2cmaster

# Tests --------------------------------------------------------------------------------------------

class TestAddI2CMaster(unittest.TestCase):
    def test_sys_clock_domain_uses_sys_clk_freq(self):
        i2c = _add_i2c_master(_fake_soc())
        self.assertEqual(i2c.sys_clk_freq, int(100e6))

    def test_clock_domain_uses_clk_freq(self):
        i2c = _add_i2c_master(_fake_soc(), clock_domain="i2c", clk_freq=int(25e6))
        self.assertEqual(i2c.sys_clk_freq, int(25e6))
        self.assertEqual(i2c.kwargs["clock_domain"], "i2c")

    def test_clock_domain_without_clk_freq_is_rejected(self):
        with self.assertRaises(SoCError):
            _add_i2c_master(_fake_soc(), clock_domain="i2c")


if __name__ == "__main__":
    unittest.main()
