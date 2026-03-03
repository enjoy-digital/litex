import unittest
import re

from migen import *

from litex.gen import LiteXContext
from litex.gen.fhdl.hierarchy import LiteXHierarchyExplorer
from litex.gen.fhdl.verilog import convert


class _Leaf(Module):
    def __init__(self):
        # Intentionally unnamed submodule to exercise generated-name policy.
        self.submodules += Module()


class _Top(Module):
    def __init__(self):
        self.i = Signal()
        self.o = Signal()
        self.comb += self.o.eq(self.i)
        self.submodules.leaf = _Leaf()
        self.specials += Instance("MY_BB")


class TestHierarchicalVerilog(unittest.TestCase):
    def test_hierarchy_golden_text(self):
        expected = "\n".join([
            "_Top",
            "\u251c\u2500\u2500 leaf (_Leaf)",
            "\u2502    \u2514\u2500\u2500 module_0 (Module) [Gen]",
            "\u2514\u2500\u2500 [BB:MY_BB]",
            "Legend:",
            "  [Gen]: Auto-generated instance name.",
            "  [BB:NAME]: Blackbox instance (verilog Instance).",
            "",
        ])

        hierarchy = LiteXHierarchyExplorer(top=_Top(), with_colors=False).get_hierarchy()
        self.assertEqual(hierarchy, expected)

    def test_flat_and_hierarchical_smoke(self):
        flat_top = _Top()
        hier_top = _Top()
        flat_ios = {flat_top.i, flat_top.o}
        hier_ios = {hier_top.i, hier_top.o}

        old_top = LiteXContext.top
        try:
            LiteXContext.top = flat_top

            flat = convert(flat_top, ios=flat_ios, name="top", hierarchical=False).main_source
            LiteXContext.top = hier_top
            hier = convert(hier_top, ios=hier_ios, name="top", hierarchical=True).main_source
        finally:
            LiteXContext.top = old_top

        # Parity smoke: top-level interface and direct path are present in both.
        self.assertIn("module top (", flat)
        self.assertIn("module top (", hier)
        self.assertRegex(flat, r"input\s+wire\s+i")
        self.assertRegex(hier, r"input\s+wire\s+i")
        self.assertRegex(flat, r"output\s+wire\s+o")
        self.assertRegex(hier, r"output\s+wire\s+o")
        self.assertIn("assign o = i;", flat)
        self.assertIn("assign o = i;", hier)

        # Hierarchical mode should emit child module and submodule instantiation.
        self.assertIn("module top__leaf", hier)
        self.assertIn("top__leaf leaf", hier)
