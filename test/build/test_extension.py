#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.build.generic_platform import *
from litex.build.extension import Extension, IOExtension
from litex.build.xilinx import Xilinx7SeriesPlatform
from litex.build.lattice import LatticeECP5Platform

# Helpers ------------------------------------------------------------------------------------------

_io = [("clk", 0, Pins("A1"), IOStandard("LVCMOS33"))]

_connectors = [
    ("pmoda", "B1 B2 B3 B4 B5 B6 B7 B8"),
    ("pmodb", "C1 C2 C3 C4 C5 C6 C7 C8"),
    ("J1",    {1: "D1", 2: "D2", 3: "D3", 4: "D4", 5: "D5", 6: "D6", 7: "D7", 8: "D8", 9: "D9"}),
]

def xilinx_platform():
    return Xilinx7SeriesPlatform("xc7a35ticsg324-1L", list(_io), list(_connectors), toolchain="vivado")

def ecp5_platform():
    return LatticeECP5Platform("LFE5U-25F-6BG256C", list(_io), list(_connectors), toolchain="trellis")

def resolved(platform):
    """Return {(resource, number, subsignal): (pins, others)} with connectors resolved."""
    r = {}
    for sig, pins, others, (name, number, sub) in platform.constraint_manager.get_sig_constraints():
        r[(name, number, sub)] = (pins, others)
    return r

def misc(others):
    return sorted(c.misc for c in others if isinstance(c, Misc))

def iostd(others):
    return [c.name for c in others if isinstance(c, IOStandard)]

# Test extensions ----------------------------------------------------------------------------------

class _SDCard(Extension):
    slots = {"pmod": None}
    def define_io(self, platform):
        pullup    = self.pullup(platform)
        slew_fast = self.slew_fast(platform)
        return [
            ("spisdcard", 0,
                Subsignal("clk",  Pins("pmod:3")),
                Subsignal("mosi", Pins("pmod:1"), *pullup),
                *slew_fast,
                *self.iostandard(platform),
            ),
            ("sdcard", 0,
                Subsignal("data", Pins("pmod:2 pmod:4 pmod:5 pmod:0"), *pullup),
                Subsignal("cd",   Pins("pmod:6")),
                *slew_fast,
                *self.iostandard(platform),
            ),
        ]

class _GPIO(Extension):
    slots = {"pmod": None}
    def define_io(self, platform):
        return [(self.bindings["pmod"], 0, Pins(" ".join(f"pmod:{i}" for i in range(8))), *self.iostandard(platform))]

class _UART(Extension):
    slots = {"pmod": None}
    def define_io(self, platform):
        return [("serial", 0, Subsignal("tx", Pins("pmod:1")), Subsignal("rx", Pins("pmod:2")), *self.iostandard(platform))]

class _USBHost(Extension):
    slots = {"pmod": None}
    def define_io(self, platform):
        return [
            ("usb_host", 0, Subsignal("dp", Pins("pmod:2")), Subsignal("dm", Pins("pmod:3"))),
            ("usb_host", 1, Subsignal("dp", Pins("pmod:0")), Subsignal("dm", Pins("pmod:1"))),
        ]

class _Dual(Extension):
    slots = {"a": None, "b": None}
    def define_io(self, platform):
        return [
            ("dvi", 0,
                Subsignal("clk", Pins("b:1")),
                Subsignal("r",   Pins("a:5 a:1 a:4 a:0")),
                *self.iostandard(platform),
            ),
        ]

# Carrier test extension ---------------------------------------------------------------------------

class _Carrier(Extension):
    slots = {"J1": "J1"}
    def define_io(self, platform):
        return [("user_led", 0, Pins("J1:9"), *self.iostandard(platform))]
    def define_connectors(self, platform):
        return [
            ("pmodc", "J1:1 J1:2 J1:3 J1:4 J1:5 J1:6 J1:7 J1:8"),
            ("hdr",   {"a": "J1:1", "b": "None"}),
        ]

# Tests --------------------------------------------------------------------------------------------

class TestExtension(unittest.TestCase):
    def test_io_attrs(self):
        self.assertEqual(misc(Xilinx7SeriesPlatform.get_io_attr("pullup")), ["PULLUP True"])
        self.assertEqual(misc(LatticeECP5Platform.get_io_attr("slew_fast")), ["SLEWRATE=FAST"])
        self.assertEqual(GenericPlatform.get_io_attr("pullup"), [])
        with self.assertRaises(ValueError):
            GenericPlatform.get_io_attr("unknown")

    def test_binding(self):
        with self.assertRaises(ValueError):
            _SDCard()                 # Unbound slot.
        with self.assertRaises(ValueError):
            _SDCard("pmoda", "pmodb") # Too many connectors.
        with self.assertRaises(ValueError):
            _SDCard(foo="pmoda")      # Unknown slot.
        self.assertEqual(_Dual(a="pmoda", b="pmodb").bindings, {"a": "pmoda", "b": "pmodb"})

    def test_sdcard_xilinx(self):
        platform = xilinx_platform()
        platform.add_extension(_SDCard("pmoda"))
        platform.request("sdcard")
        r = resolved(platform)
        pins, others = r[("sdcard", 0, "data")]
        self.assertEqual(pins, ["B3", "B5", "B6", "B1"])
        self.assertEqual(misc(others), ["PULLUP True", "SLEW=FAST"])
        self.assertEqual(iostd(others), ["LVCMOS33"])
        self.assertEqual(r[("sdcard", 0, "cd")][0], ["B7"])

    def test_sdcard_ecp5(self):
        platform = ecp5_platform()
        platform.add_extension(_SDCard("pmodb"))
        platform.request("spisdcard")
        pins, others = resolved(platform)[("spisdcard", 0, "mosi")]
        self.assertEqual(pins, ["C2"])
        self.assertEqual(misc(others), ["PULLMODE=UP", "SLEWRATE=FAST"])

    def test_options(self):
        platform = xilinx_platform()
        platform.add_extension(_UART("pmoda", number=1, iostandard="LVCMOS18"))
        platform.add_extension(_GPIO("pmodb"))
        platform.request("serial", 1)
        platform.request("pmodb")
        r = resolved(platform)
        self.assertEqual(iostd(r[("serial", 1, "tx")][1]), ["LVCMOS18"])
        self.assertEqual(r[("pmodb", 0, None)][0], [f"C{i}" for i in range(1, 9)])

    def test_dual_slots(self):
        platform = xilinx_platform()
        platform.add_extension(_Dual(a="pmoda", b="pmodb"))
        platform.request("dvi")
        r = resolved(platform)
        self.assertEqual(r[("dvi", 0, "r")][0], ["B6", "B2", "B5", "B1"])
        self.assertEqual(r[("dvi", 0, "clk")][0], ["C2"])

    def test_stacking(self):
        # Pmod plugged on a connector exposed by a carrier.
        platform = xilinx_platform()
        platform.add_extension(_Carrier())
        platform.add_extension(_UART("pmodc"))
        platform.request("user_led")
        platform.request("serial")
        r = resolved(platform)
        self.assertEqual(r[("user_led", 0, None)][0], ["D9"])
        self.assertEqual(r[("serial", 0, "tx")][0], ["D2"])

    def test_rebinding(self):
        # Carrier slot bound to another host connector name.
        platform = xilinx_platform()
        platform.add_connector(("J7", {9: "E9", 1: "E1"}))
        platform.add_extension(_Carrier(J1="J7"))
        platform.add_extension(_GPIO("pmodc"))
        platform.request("user_led")
        self.assertEqual(resolved(platform)[("user_led", 0, None)][0], ["E9"])

    def test_io_extension(self):
        ext = IOExtension("J7", io=[("led", 0, Pins("J1:1"))], slots={"J1": "J1"})
        io  = ext.get_io(xilinx_platform())
        self.assertEqual(io[0][2].identifiers, ["J7:1"])

    def test_connector_loop(self):
        platform = xilinx_platform()
        platform.add_connector([("X", "Y:0"), ("Y", "X:0")])
        platform.add_extension([("loop", 0, Pins("X:0"))])
        platform.request("loop")
        with self.assertRaises(ConstraintError):
            platform.constraint_manager.get_sig_constraints()

class TestExtensionOptions(unittest.TestCase):
    def test_name(self):
        platform = xilinx_platform()
        io = _UART("pmoda", name="console").get_io(platform)
        self.assertEqual(io[0][0], "console")
        io = _SDCard("pmoda", name={"sdcard": "sdcard_pmod"}).get_io(platform)
        self.assertEqual(sorted(r[0] for r in io), ["sdcard_pmod", "spisdcard"])
        with self.assertRaises(ValueError):
            _SDCard("pmoda", name="foo").get_io(platform) # Several resource names.

    def test_number_offset(self):
        io = _USBHost("pmoda", number=2).get_io(xilinx_platform())
        self.assertEqual([r[1] for r in io], [2, 3])

    def test_misc(self):
        io = _GPIO("pmoda", misc=Misc("DRIVE=8")).get_io(xilinx_platform())
        self.assertEqual(misc(io[0][2:]), ["DRIVE=8"])


if __name__ == "__main__":
    unittest.main()
