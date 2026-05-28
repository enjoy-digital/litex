import unittest
import re

from migen import *
from migen.fhdl.decorators import ClockDomainsRenamer
from migen.fhdl.structure import DUID
from migen.fhdl.specials import Tristate

from litex.build.sim.common import sim_special_overrides
from litex.gen import LiteXContext
from litex.gen.fhdl.hierarchy import LiteXHierarchyExplorer
from litex.gen.fhdl.verilog import convert
from litex.soc.interconnect import stream


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


class _FIFONamingTop(Module):
    def __init__(self, with_inserted_fifo=False):
        self.clock_domains.cd_sys = ClockDomain("sys")

        self.rx_o = Signal(8, name="rx_o")
        self.tx_o = Signal(8, name="tx_o")

        self.submodules.rx_fifo = stream.SyncFIFO([("data", 8)], 4)
        if with_inserted_fifo:
            self.submodules.mid_fifo = stream.SyncFIFO([("data", 8)], 4)
        self.submodules.tx_fifo = stream.SyncFIFO([("data", 8)], 4, buffered=True)

        self.comb += [
            self.rx_o.eq(self.rx_fifo.source.data),
            self.tx_o.eq(self.tx_fifo.source.data),
        ]


class _GenericFIFONamingTop(Module):
    def __init__(self):
        self.clock_domains.cd_sys = ClockDomain("sys")

        self.o = Signal(8, name="o")
        self.submodules.fifo = stream.SyncFIFO([("data", 8)], 4)
        self.comb += self.o.eq(self.fifo.source.data)


class _AnonymousFIFONamingTop(Module):
    def __init__(self):
        self.clock_domains.cd_sys = ClockDomain("sys")

        data_buffer = stream.SyncFIFO([("data", 8)], 4)
        self.submodules += data_buffer

        self.o = Signal(8, name="o")
        self.comb += self.o.eq(data_buffer.source.data)


class _AnonymousFIFOListNamingTop(Module):
    def __init__(self):
        self.clock_domains.cd_sys = ClockDomain("sys")

        buffers = [stream.SyncFIFO([("data", 8)], 4) for _ in range(2)]
        self.submodules += buffers[0]
        self.submodules += buffers[1]

        self.o0 = Signal(8, name="o0")
        self.o1 = Signal(8, name="o1")
        self.comb += [
            self.o0.eq(buffers[0].source.data),
            self.o1.eq(buffers[1].source.data),
        ]


class _AsyncFIFONamingTop(Module):
    def __init__(self):
        self.clock_domains.cd_sys = ClockDomain("sys")
        self.clock_domains.cd_rx  = ClockDomain("rx")
        self.clock_domains.cd_tx  = ClockDomain("tx")

        self.rx_o = Signal(8, name="rx_o")
        self.tx_o = Signal(8, name="tx_o")

        self.submodules.rx_fifo = ClockDomainsRenamer({"write": "rx", "read": "sys"})(
            stream.AsyncFIFO([("data", 8)], 4))
        self.submodules.tx_fifo = ClockDomainsRenamer({"write": "sys", "read": "tx"})(
            stream.AsyncFIFO([("data", 8)], 4, buffered=True))

        self.comb += [
            self.rx_o.eq(self.rx_fifo.source.data),
            self.tx_o.eq(self.tx_fifo.source.data),
        ]


class _CDCNamingTop(Module):
    def __init__(self):
        self.clock_domains.cd_sys  = ClockDomain("sys")
        self.clock_domains.cd_fast = ClockDomain("fast")

        self.o0 = Signal(8, name="o0")
        self.o1 = Signal(8, name="o1")

        self.submodules.rx_cdc = stream.ClockDomainCrossing(
            [("data", 8)],
            cd_from         = "fast",
            cd_to           = "sys",
            with_common_rst = True,
        )
        self.submodules.tx_cdc = stream.ClockDomainCrossing(
            [("data", 8)],
            cd_from         = "sys",
            cd_to           = "fast",
            with_common_rst = True,
        )

        self.comb += [
            self.o0.eq(self.rx_cdc.source.data),
            self.o1.eq(self.tx_cdc.source.data),
        ]


class _PrefixStabilityBlock(Module):
    def __init__(self):
        self.a = Signal(8)
        self.o = Signal(8, name="o")

        self.comb += self.o.eq(self.a)


class _PrefixStabilityTop(Module):
    def __init__(self, with_sibling=False):
        self.submodules.main = _PrefixStabilityBlock()

        self.o = Signal(8, name="o")
        self.comb += self.o.eq(self.main.o)

        if with_sibling:
            self.submodules.other = _PrefixStabilityBlock()
            self.o2 = Signal(8, name="o2")
            self.comb += self.o2.eq(self.other.o)


class _MemoryNamingTop(Module):
    def __init__(self):
        self.clock_domains.cd_sys = ClockDomain("sys")

        self.named_mem = Memory(8, 4, name="explicit_mem")
        self.plain_mem = Memory(8, 4)

        named_port = self.named_mem.get_port(async_read=True)
        plain_port = self.plain_mem.get_port(async_read=True)
        named_port.clock = self.cd_sys.clk
        plain_port.clock = self.cd_sys.clk

        self.specials += self.named_mem, self.plain_mem

        self.o0 = Signal(8, name="o0")
        self.o1 = Signal(8, name="o1")
        self.comb += [
            named_port.adr.eq(0),
            plain_port.adr.eq(0),
            self.o0.eq(named_port.dat_r),
            self.o1.eq(plain_port.dat_r),
        ]


class TestHierarchicalVerilog(unittest.TestCase):
    @staticmethod
    def _module_body(verilog, name):
        match = re.search(rf"module {name} \(.*?endmodule", verilog, re.S)
        if match is None:
            raise AssertionError(f"module {name} not found")
        return match.group(0)

    @staticmethod
    def _memory_names(verilog):
        return re.findall(r"// Memory ([a-zA-Z0-9_]+):", verilog)

    @staticmethod
    def _declared_signal_names(verilog):
        return re.findall(r"^\s*(?:wire|reg)\s+(?:\[[^\]]+\]\s*)?([a-zA-Z0-9_]+)", verilog, re.M)

    @staticmethod
    def _normalized_verilog(verilog):
        verilog = re.sub(r"Date       : .*", "Date       : <date>", verilog)
        verilog = re.sub(
            r"Auto-Generated by LiteX on .*",
            "Auto-Generated by LiteX on <date>.",
            verilog)
        return verilog

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

    def test_flat_fifo_memory_names_use_owner(self):
        top = _FIFONamingTop(with_inserted_fifo=False)
        verilog = convert(
            top,
            ios={top.cd_sys.clk, top.cd_sys.rst, top.rx_o, top.tx_o},
            name="top",
        ).main_source

        self.assertIn("rx_fifo_storage", self._memory_names(verilog))
        self.assertIn("tx_fifo_storage", self._memory_names(verilog))
        self.assertNotIn("storage_1", self._memory_names(verilog))

    def test_flat_fifo_memory_names_survive_inserted_fifo(self):
        top = _FIFONamingTop(with_inserted_fifo=True)
        verilog = convert(
            top,
            ios={top.cd_sys.clk, top.cd_sys.rst, top.rx_o, top.tx_o},
            name="top",
        ).main_source

        memory_names = self._memory_names(verilog)
        self.assertIn("rx_fifo_storage", memory_names)
        self.assertIn("mid_fifo_storage", memory_names)
        self.assertIn("tx_fifo_storage", memory_names)

    def test_flat_generic_fifo_name_is_not_lost(self):
        top = _GenericFIFONamingTop()
        verilog = convert(
            top,
            ios={top.cd_sys.clk, top.cd_sys.rst, top.o},
            name="top",
        ).main_source

        self.assertIn("fifo_storage", self._memory_names(verilog))
        self.assertNotIn("top_storage", self._memory_names(verilog))

    def test_flat_anonymous_fifo_memory_name_uses_trace_owner(self):
        top = _AnonymousFIFONamingTop()
        verilog = convert(
            top,
            ios={top.cd_sys.clk, top.cd_sys.rst, top.o},
            name="top",
        ).main_source

        memory_names = self._memory_names(verilog)
        self.assertIn("data_buffer_storage", memory_names)
        self.assertNotIn("fifo_storage", memory_names)

    def test_flat_anonymous_fifo_list_memory_names_use_trace_owner(self):
        top = _AnonymousFIFOListNamingTop()
        verilog = convert(
            top,
            ios={top.cd_sys.clk, top.cd_sys.rst, top.o0, top.o1},
            name="top",
        ).main_source

        memory_names = self._memory_names(verilog)
        self.assertIn("buffers_storage", memory_names)
        self.assertIn("buffers_storage_1", memory_names)
        self.assertNotIn("fifo_storage", memory_names)

    def test_flat_clock_renamed_async_fifo_memory_names_use_owner(self):
        top = _AsyncFIFONamingTop()
        verilog = convert(
            top,
            ios={
                top.cd_sys.clk, top.cd_sys.rst,
                top.cd_rx.clk,  top.cd_rx.rst,
                top.cd_tx.clk,  top.cd_tx.rst,
                top.rx_o,       top.tx_o,
            },
            name="top",
        ).main_source

        memory_names = self._memory_names(verilog)
        self.assertIn("rx_fifo_storage", memory_names)
        self.assertIn("tx_fifo_storage", memory_names)
        self.assertNotIn("top_storage", memory_names)

    def test_flat_cdc_common_reset_domains_use_owner_signal_names(self):
        top = _CDCNamingTop()
        verilog = convert(
            top,
            ios={
                top.cd_sys.clk,  top.cd_sys.rst,
                top.cd_fast.clk, top.cd_fast.rst,
                top.o0,          top.o1,
            },
            name="top",
            special_overrides=sim_special_overrides,
        ).main_source

        self.assertIn("rx_cdc_from_clk", verilog)
        self.assertIn("rx_cdc_to_clk", verilog)
        self.assertIn("tx_cdc_from_clk", verilog)
        self.assertIn("tx_cdc_to_clk", verilog)
        self.assertNotRegex(verilog, r"\bfrom\d+_(clk|rst)\b")
        self.assertNotRegex(verilog, r"\bto\d+_(clk|rst)\b")

    def test_flat_named_submodule_signal_names_are_prefixed_without_conflict(self):
        top = _PrefixStabilityTop(with_sibling=False)
        verilog = convert(top, ios={top.o}, name="top").main_source

        signal_names = self._declared_signal_names(verilog)
        self.assertIn("main_a", signal_names)
        self.assertNotIn("a", signal_names)

    def test_flat_named_submodule_signal_names_survive_sibling_insertion(self):
        top = _PrefixStabilityTop(with_sibling=True)
        verilog = convert(top, ios={top.o, top.o2}, name="top").main_source

        signal_names = self._declared_signal_names(verilog)
        self.assertIn("main_a", signal_names)
        self.assertIn("other_a", signal_names)

    def test_flat_cdc_common_reset_source_is_duid_stable(self):
        def generate(noise_count):
            for _ in range(noise_count):
                DUID()
            top = _CDCNamingTop()
            verilog = convert(
                top,
                ios={
                    top.cd_sys.clk,  top.cd_sys.rst,
                    top.cd_fast.clk, top.cd_fast.rst,
                    top.o0,          top.o1,
                },
                name="top",
                special_overrides=sim_special_overrides,
            ).main_source
            return self._normalized_verilog(verilog)

        self.assertEqual(generate(noise_count=0), generate(noise_count=20))

    def test_flat_non_fifo_memory_names_are_unchanged(self):
        top = _MemoryNamingTop()
        verilog = convert(top, ios={top.o0, top.o1}, name="top").main_source

        memory_names = self._memory_names(verilog)
        self.assertIn("explicit_mem", memory_names)
        self.assertIn("plain_mem", memory_names)

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
