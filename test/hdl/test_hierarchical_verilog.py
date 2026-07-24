import unittest
import re

from migen import *
from migen.fhdl.decorators import ClockDomainsRenamer
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


class _InlineFSMLeaf(Module):
    def __init__(self):
        self.o = Signal(name="fsm_o")
        self.submodules.fsm = FSM(reset_state="IDLE")
        self.comb += self.o.eq(0)
        self.fsm.act("IDLE",
            NextState("RUN"),
        )
        self.fsm.act("RUN",
            self.o.eq(1),
            NextState("RUN"),
        )


class _InlineFSMTop(Module):
    def __init__(self):
        self.o = Signal(name="o")
        self.submodules.leaf = _InlineFSMLeaf()
        self.comb += self.o.eq(self.leaf.o)


class _ClockRenamedInlineFSMTop(Module):
    def __init__(self):
        self.clock_domains.cd_eth_tx = ClockDomain("eth_tx")
        self.o = Signal(name="o")
        self.submodules.leaf = ClockDomainsRenamer("eth_tx")(_InlineFSMLeaf())
        self.comb += self.o.eq(self.leaf.o)


class _MemoryLeaf(Module):
    def __init__(self):
        self.o = Signal(8, name="mem_o")
        mem = Memory(8, 4, init=[0x12, 0x34, 0x56, 0x78])
        port = mem.get_port()
        self.specials += mem
        self.comb += [
            port.adr.eq(0),
            self.o.eq(port.dat_r),
        ]


class _MemoryTop(Module):
    def __init__(self):
        self.o = Signal(8, name="o")
        self.submodules.leaf = _MemoryLeaf()
        self.comb += self.o.eq(self.leaf.o)


class _SharedMemoryOwner(Module):
    def __init__(self, mem):
        self.specials += mem


class _SharedMemoryReader(Module):
    def __init__(self, mem, adr):
        self.dat_r = Signal(8, name="shared_mem_dat_r")
        port = mem.get_port()
        self.specials += mem
        self.comb += [
            port.adr.eq(adr),
            self.dat_r.eq(port.dat_r),
        ]


class _SharedMemoryTop(Module):
    def __init__(self):
        self.adr = Signal(2, name="adr")
        self.o = Signal(8, name="o")
        mem = Memory(8, 4, init=[0x12, 0x34, 0x56, 0x78])
        self.submodules.owner = _SharedMemoryOwner(mem)
        self.submodules.reader = _SharedMemoryReader(mem, self.adr)
        self.comb += self.o.eq(self.reader.dat_r)


class _InlineDropLeaf(Module):
    def __init__(self):
        self.out = Signal(name="out")
        self.comb += self.out.eq(1)


class _InlineDropChild(Module):
    def __init__(self):
        self.trigger = Signal(name="trigger")
        self.submodules.leaf = _InlineDropLeaf()


class _InlineDropTop(Module):
    def __init__(self):
        self.io = Signal(name="io")
        self.submodules.child = _InlineDropChild()
        self.comb += self.io.eq(self.child.leaf.out)
        # Force the child and its subtree to be inlined.
        self.comb += self.child.trigger.eq(1)


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

    def test_hierarchical_inline_child_statements_are_not_duplicated(self):
        top = _InlineFSMTop()

        old_top = LiteXContext.top
        try:
            LiteXContext.top = top
            verilog = convert(top, ios={top.o}, name="top", hierarchical=True).main_source
        finally:
            LiteXContext.top = old_top

        leaf_module = self._module_body(verilog, "top__leaf")
        top_module  = self._module_body(verilog, "top")

        self.assertEqual(leaf_module.count("case (state)"), 1)
        self.assertEqual(leaf_module.count("always @(posedge sys_clk)"), 1)
        self.assertIn(".fsm_o(fsm_o)", top_module)
        self.assertNotIn(".state(state)", top_module)
        self.assertNotIn(".next_state(next_state)", top_module)

    def test_hierarchical_inline_child_preserves_renamed_clock_domain(self):
        top = _ClockRenamedInlineFSMTop()

        old_top = LiteXContext.top
        try:
            LiteXContext.top = top
            verilog = convert(top, ios={top.o}, name="top", hierarchical=True).main_source
        finally:
            LiteXContext.top = old_top

        leaf_module = self._module_body(verilog, "top__leaf")

        self.assertEqual(leaf_module.count("always @(posedge eth_tx_clk)"), 1)
        self.assertNotIn("sys_clk", leaf_module)
        self.assertNotIn("sys_rst", leaf_module)

    def test_hierarchical_memory_port_declares_clock(self):
        top = _MemoryTop()

        old_top = LiteXContext.top
        try:
            LiteXContext.top = top
            verilog = convert(top, ios={top.o}, name="top", hierarchical=True).main_source
        finally:
            LiteXContext.top = old_top

        leaf_module = self._module_body(verilog, "top__leaf")
        top_module  = self._module_body(verilog, "top")

        self.assertRegex(leaf_module, r"input\s+wire\s+sys_clk")
        self.assertIn("always @(posedge sys_clk)", leaf_module)
        self.assertIn(".sys_clk(sys_clk)", top_module)

    def test_hierarchical_inlined_child_keeps_grandchild_logic(self):
        top = _InlineDropTop()

        old_top = LiteXContext.top
        try:
            LiteXContext.top = top
            verilog = convert(top, ios={top.io}, name="top", hierarchical=True).main_source
        finally:
            LiteXContext.top = old_top

        top_module = self._module_body(verilog, "top")

        self.assertEqual(verilog.count("assign out = 1'd1"), 1)
        self.assertIn("assign out = 1'd1", top_module)
        self.assertNotIn("module top__child (", verilog)
        self.assertNotIn("module top__child__leaf (", verilog)

    def test_hierarchical_shared_memory_is_emitted_once(self):
        top = _SharedMemoryTop()

        old_top = LiteXContext.top
        try:
            LiteXContext.top = top
            verilog = convert(top, ios={top.adr, top.o}, name="top", hierarchical=True).main_source
        finally:
            LiteXContext.top = old_top

        owner_module = self._module_body(verilog, "top__owner")
        reader_module = self._module_body(verilog, "top__reader")

        self.assertEqual(verilog.count("reg [7:0] mem[0:3];"), 1)
        self.assertIn("reg [7:0] mem[0:3];", owner_module)
        self.assertNotIn("reg [7:0] mem[0:3];", reader_module)
        self.assertRegex(owner_module, r"output\s+wire\s+\[7:0\]\s+dat_r")
        self.assertRegex(reader_module, r"input\s+wire\s+\[7:0\]\s+dat_r")
