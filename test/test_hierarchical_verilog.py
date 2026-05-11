import unittest
import re

from migen import *
from migen.fhdl.specials import Tristate

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


class _TristateLeaf(Module):
    def __init__(self, pad):
        self.o  = Signal(name="leaf_o")
        self.oe = Signal(name="leaf_oe")
        self.i  = Signal(name="leaf_i")

        self.comb += [
            self.o.eq(1),
            self.oe.eq(self.i),
        ]
        self.specials += Tristate(pad, self.o, self.oe, self.i)


class _TristateTop(Module):
    def __init__(self):
        self.pad = Signal(name="pad")
        self.submodules.leaf = _TristateLeaf(self.pad)


class _SharedLeaf(Module):
    def __init__(self, shared):
        self.o = Signal(name="leaf_o")
        self.comb += self.o.eq(shared)


class _SharedTop(Module):
    def __init__(self):
        self.dummy  = Signal(name="dummy")
        self.shared = Signal(name="shared")
        self.submodules.leaf = _SharedLeaf(self.shared)


class TestHierarchicalVerilog(unittest.TestCase):
    @staticmethod
    def _module_body(verilog, name):
        match = re.search(rf"module {name} \(.*?endmodule", verilog, re.S)
        if match is None:
            raise AssertionError(f"module {name} not found")
        return match.group(0)

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

    def test_hierarchical_tristate_keeps_child_controls_local(self):
        top = _TristateTop()

        old_top = LiteXContext.top
        try:
            LiteXContext.top = top
            verilog = convert(top, ios={top.pad}, name="top", hierarchical=True).main_source
        finally:
            LiteXContext.top = old_top

        leaf_module = self._module_body(verilog, "top__leaf")
        top_module  = self._module_body(verilog, "top")

        self.assertRegex(leaf_module, r"inout\s+wire\s+pad")
        self.assertNotRegex(leaf_module.split(");", 1)[0], r"leaf_[ioe]")
        self.assertRegex(leaf_module, r"wire\s+leaf_i;")
        self.assertRegex(leaf_module, r"wire\s+leaf_o;")
        self.assertRegex(leaf_module, r"wire\s+leaf_oe;")
        self.assertIn("assign pad = leaf_oe ? leaf_o : 1'bz;", leaf_module)
        self.assertIn("assign leaf_i = pad;", leaf_module)

        self.assertIn(".pad(pad)", top_module)
        self.assertNotIn("leaf_i", top_module)
        self.assertNotIn("leaf_o", top_module)
        self.assertNotIn("leaf_oe", top_module)

    def test_hierarchical_parent_signal_used_by_child_is_port(self):
        leaf = _SharedTop()

        old_top = LiteXContext.top
        try:
            LiteXContext.top = leaf
            verilog = convert(leaf, ios={leaf.dummy}, name="top", hierarchical=True).main_source
        finally:
            LiteXContext.top = old_top

        leaf_module = self._module_body(verilog, "top__leaf")
        top_module  = self._module_body(verilog, "top")

        self.assertRegex(leaf_module, r"input\s+wire\s+shared")
        self.assertIn(".shared(shared)", top_module)
