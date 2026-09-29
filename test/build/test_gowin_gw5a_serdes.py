#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import re
import unittest

from migen import *

from litex.gen.fhdl import verilog

from litex.build.io import SerDesInput, SerDesOutput, SerDesTristate, DifferentialTristate
from litex.build.gowin.common import Gw5AOSER, Gw5AIDES, Gw5AIODELAY
from litex.build.gowin.common import gowin_special_overrides, gw5a_special_overrides

# Helpers ------------------------------------------------------------------------------------------

def _convert(module, ios):
    return str(verilog.convert(module, ios=ios))

def _instance(v, primitive):
    """Return the parameters/ports text of the (single) primitive instance."""
    m = re.search(rf"\n{primitive} (?:#\((?P<params>.*?)\) )?\w+\s*\((?P<ports>.*?)\n\);", v, re.S)
    assert m is not None, f"{primitive} instance not found."
    return re.sub(r"\s", "", m.group("params") or ""), m.group("ports")

def _instance_name(v, primitive):
    return re.search(rf"\n{primitive} (?:#\(.*?\) )?(\w+)\s*\(", v, re.S).group(1)

def _connections(ports):
    return dict(re.findall(r"\.(\w+)\s*\(([^()]*)\)", ports))

# Gw5A SerDes --------------------------------------------------------------------------------------

class TestGw5ASerDes(unittest.TestCase):
    def test_oser_ratios(self):
        for ratio in [4, 8, 10, 16]:
            with self.subTest(ratio=ratio):
                d    = Signal(ratio, name="d")
                q    = Signal(name="q")
                pclk = Signal(name="pclk")
                fclk = Signal(name="fclk")
                v    = _convert(Gw5AOSER(d, q, pclk, fclk), {d, q, pclk, fclk})
                _, ports = _instance(v, f"OSER{ratio}")
                c = _connections(ports)
                # d[0] on D0 (sent first) ... d[n-1] on D(n-1).
                for n in range(ratio):
                    self.assertEqual(c[f"D{n}"], f"d[{n}]")
                self.assertEqual(c["PCLK"], "pclk")
                self.assertEqual(c["FCLK"], "fclk")
                self.assertEqual(c["Q0" if ratio in [4, 8] else "Q"], "q")
                self.assertEqual(_instance_name(v, f"OSER{ratio}"), f"gw5a_oser{ratio}")

    def test_oser_tristate(self):
        for ratio, txs in [(4, 2), (8, 4)]:
            with self.subTest(ratio=ratio):
                d    = Signal(ratio, name="d")
                q    = Signal(name="q")
                t    = Signal(name="t")
                q_t  = Signal(name="q_t")
                pclk = Signal(name="pclk")
                fclk = Signal(name="fclk")
                v    = _convert(Gw5AOSER(d, q, pclk, fclk, t=t, q_t=q_t), {d, q, t, q_t, pclk, fclk})
                params, ports = _instance(v, f"OSER{ratio}")
                c = _connections(ports)
                for n in range(txs):
                    self.assertEqual(c[f"TX{n}"], "t")
                self.assertEqual(c["Q1"], "q_t")
                self.assertIn(".HWL(\"false\")", params)

    def test_oser_no_tristate_path(self):
        d = Signal(16)
        with self.assertRaises(ValueError):
            Gw5AOSER(d, Signal(), Signal(), Signal(), t=Signal())

    def test_ides_ratios(self):
        for ratio in [4, 8, 10, 16]:
            with self.subTest(ratio=ratio):
                d     = Signal(name="d")
                q     = Signal(ratio, name="q")
                pclk  = Signal(name="pclk")
                fclk  = Signal(name="fclk")
                calib = Signal(name="calib")
                v     = _convert(Gw5AIDES(d, q, pclk, fclk, calib=calib), {d, q, pclk, fclk, calib})
                _, ports = _instance(v, f"IDES{ratio}")
                c = _connections(ports)
                # Q0 (received first) on q[0] ... Q(n-1) on q[n-1].
                for n in range(ratio):
                    self.assertEqual(c[f"Q{n}"], f"q[{n}]")
                self.assertEqual(c["D"],     "d")
                self.assertEqual(c["CALIB"], "calib")
                self.assertEqual(_instance_name(v, f"IDES{ratio}"), f"gw5a_ides{ratio}")

    def test_invalid_ratios(self):
        for ratio in [2, 6, 12]:
            with self.subTest(ratio=ratio):
                with self.assertRaises(ValueError):
                    Gw5AOSER(Signal(ratio), Signal(), Signal(), Signal())
                with self.assertRaises(ValueError):
                    Gw5AIDES(Signal(), Signal(ratio), Signal(), Signal())

# Gw5A IODelay -------------------------------------------------------------------------------------

class TestGw5AIODelay(unittest.TestCase):
    def test_iodelay(self):
        i = Signal(name="i")
        o = Signal(name="o")
        v = _convert(Gw5AIODELAY(i, o, delay=12), {i, o})
        params, ports = _instance(v, "IODELAY")
        c = _connections(ports)
        self.assertIn(".C_STATIC_DLY(4'd12)", params)
        self.assertEqual(c["DI"], "i")
        self.assertEqual(c["DO"], "o")
        self.assertEqual(_instance_name(v, "IODELAY"), "gw5a_iodelay")

    def test_iodelay_range(self):
        with self.assertRaises(ValueError):
            Gw5AIODELAY(Signal(), Signal(), delay=256)

# Generic Specials (GW5A lowering) -----------------------------------------------------------------

_GW5A_OVERRIDES = {**gowin_special_overrides, **gw5a_special_overrides}

def _convert_special(special, ios):
    m = Module()
    m.specials += special
    return str(verilog.convert(m, ios=ios, special_overrides=_GW5A_OVERRIDES))

class TestGw5ASpecials(unittest.TestCase):
    def test_serdes_output(self):
        i, o, clk, clk_fast = Signal(16, name="i"), Signal(name="o"), Signal(name="clk"), Signal(name="clk_fast")
        v = _convert_special(SerDesOutput(i, o, clk, clk_fast), {i, o, clk, clk_fast})
        _, ports = _instance(v, "OSER16")
        c = _connections(ports)
        self.assertEqual(c["D0"],   "i[0]")
        self.assertEqual(c["Q"],    "o")
        self.assertEqual(c["PCLK"], "clk")
        self.assertEqual(c["FCLK"], "clk_fast")

    def test_serdes_input(self):
        i, o, clk, clk_fast = Signal(name="i"), Signal(8, name="o"), Signal(name="clk"), Signal(name="clk_fast")
        v = _convert_special(SerDesInput(i, o, clk, clk_fast), {i, o, clk, clk_fast})
        _, ports = _instance(v, "IDES8")
        c = _connections(ports)
        self.assertEqual(c["Q0"], "o[0]")
        self.assertEqual(c["D"],  "i")

    def test_serdes_tristate(self):
        for ratio in [4, 8]:
            with self.subTest(ratio=ratio):
                io, oe        = Signal(name="io"), Signal(name="oe")
                o, i          = Signal(ratio, name="o"), Signal(ratio, name="i")
                clk, clk_fast = Signal(name="clk"), Signal(name="clk_fast")
                ios = {io, o, oe, i, clk, clk_fast}
                v   = _convert_special(SerDesTristate(io, o, oe, i, clk, clk_fast), ios)
                ports_oser = _instance(v, f"OSER{ratio}")[1]
                oser = _connections(ports_oser)
                ides = _connections(_instance(v, f"IDES{ratio}")[1])
                buf  = _connections(_instance(v, "IOBUF")[1])
                # Serialized data/output enable to the IOBUF, IOBUF output deserialized.
                self.assertEqual(oser["D0"],   "o[0]")
                self.assertRegex(ports_oser, r"\.TX0\s*\(\(~oe\)\)")
                self.assertEqual(oser["Q0"],   buf["I"])
                self.assertEqual(oser["Q1"],   buf["OEN"])
                self.assertEqual(buf["IO"],    "io")
                self.assertEqual(ides["D"],    buf["O"])
                self.assertEqual(ides["Q0"],   "i[0]")
                self.assertEqual(ides["PCLK"], "clk")
                self.assertEqual(ides["FCLK"], "clk_fast")
                self.assertEqual(_instance_name(v, "IOBUF"), "gw5a_serdes_iobuf")

    def test_serdes_tristate_output_only(self):
        io, oe, o = Signal(name="io"), Signal(name="oe"), Signal(4, name="o")
        clk, clk_fast = Signal(name="clk"), Signal(name="clk_fast")
        v = _convert_special(SerDesTristate(io, o, oe, None, clk, clk_fast), {io, o, oe, clk, clk_fast})
        self.assertIsNotNone(_instance(v, "OSER4"))
        self.assertNotIn("IDES4", v)

    def test_serdes_tristate_widths(self):
        with self.assertRaises(ValueError):
            SerDesTristate(Signal(), Signal(4), Signal(), Signal(8), Signal(), Signal())
        with self.assertRaises(ValueError):
            SerDesTristate(Signal(2), Signal(4), Signal(), Signal(4), Signal(), Signal())

    def test_differential_tristate(self):
        io_p, io_n = Signal(name="io_p"), Signal(name="io_n")
        o, oe, i   = Signal(name="o"), Signal(name="oe"), Signal(name="i")
        v = _convert_special(DifferentialTristate(io_p, io_n, o, oe, i), {io_p, io_n, o, oe, i})
        self.assertEqual(_instance_name(v, "ELVDS_IOBUF"), "gw5a_elvds_iobuf")
        _, ports = _instance(v, "ELVDS_IOBUF")
        c = _connections(ports)
        self.assertEqual(c["IO"],  "io_p")
        self.assertEqual(c["IOB"], "io_n")
        self.assertEqual(c["O"],   "i")

    def test_not_supported_generic(self):
        # Without vendor lowering: explicit error.
        with self.assertRaises(NotImplementedError):
            m = Module()
            m.specials += SerDesOutput(Signal(4), Signal(), Signal(), Signal())
            verilog.convert(m)
        with self.assertRaises(NotImplementedError):
            m = Module()
            m.specials += SerDesTristate(Signal(), Signal(4), Signal(), Signal(4), Signal(), Signal())
            verilog.convert(m)
