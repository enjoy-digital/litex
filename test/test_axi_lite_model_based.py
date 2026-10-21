import random

import pytest

from litex.soc.interconnect import axi
from migen import *

from .bus.axi_lite_stimulus import AXILiteMasterStimulus, HazardPolicy
from .bus.ref_models import MemoryReferenceModel
from .bus.transactions import TransactionPatternGen, TransactionPolicy
from .common.event_trace import EventTrace
from .common.param_space import ParamSpace

# Model-based AXI-Lite tests:
# - Generate read/write sequences using TransactionPatternGen
# - Predict expected outcomes with MemoryReferenceModel
# - Drive DUT via AXILiteMasterStimulus with varied channel timing

SEED = 42
SRAM_SIZE = 0x1000
ADDR_WIDTH = 32
MAX_CYCLES = 200_000
MAX_OUTSTANDING = 99

# -------------------------------- Testing starts here --------------------------------


axi_lite_core_timing_space = {
    "req_valid_delay": (0, 1, 2),
    "aw_w_skew": (-1, 0, 1),
    "r_ready_delay": (0, 1, 2),
    "b_ready_delay": (0, 1, 2),
}

axi_lite_extended_timing_space = {
    "req_valid_delay": (0, 1, 2, 4, 8),
    "aw_w_skew": (-4, -2, -1, 0, 1, 2, 4),
    "r_ready_delay": (0, 1, 2, 4, 8),
    "b_ready_delay": (0, 1, 2, 4, 8),
}


@pytest.fixture
def master_dw(sram_dw):
    """Default: master width equals SRAM width unless overridden by parametrized tests."""
    return sram_dw


@pytest.fixture
def axi_lite_timing_test_space():
    core_space = ParamSpace(axi_lite_core_timing_space,
                            mode="full")         # exhaustive small-range
    ext_space = ParamSpace(axi_lite_extended_timing_space,
                           mode="pairwise")  # bounded broad-range
    test_space = ParamSpace.iter_unique([core_space, ext_space])
    return test_space


@pytest.fixture()
def sram_dut(sram_dw):
    class DUT(Module):
        def __init__(self, data_width, addr_width, size_bytes):
            rng = random.Random(SEED)
            self.sram_bus = axi.AXILiteInterface(
                data_width=data_width, address_width=addr_width)
            self.word_bytes = data_width // 8
            self.sram_init = [rng.getrandbits(
                8 * self.word_bytes) for _ in range(size_bytes // self.word_bytes)]
            self.submodules.sram = axi.AXILiteSRAM(
                size_bytes, bus=self.sram_bus, init=self.sram_init)
            self.data_width = data_width
            self.size_bytes = size_bytes
    return DUT(data_width=sram_dw, addr_width=ADDR_WIDTH, size_bytes=SRAM_SIZE)


@pytest.fixture
def master_policy(sram_dut, master_dw):
    # TransactionPolicy describes the MASTER-side allowed access patterns.
    return TransactionPolicy(
        base_addr=0x0000,
        size_bytes=sram_dut.size_bytes,
        word_bytes=master_dw//8,
        aligned_only=True,
        max_outstanding_reads=MAX_OUTSTANDING,
        max_outstanding_writes=MAX_OUTSTANDING,
    )


@pytest.fixture
def sram_model(sram_dut):
    mem_model = MemoryReferenceModel(size_bytes=sram_dut.size_bytes,
                                     word_bytes=sram_dut.word_bytes)
    # init mem:
    be_full = (1 << sram_dut.word_bytes) - 1
    for i, w in enumerate(sram_dut.sram_init):
        mem_model.write_word_le(i * sram_dut.word_bytes,
                                w, be_full, sram_dut.word_bytes)
    return mem_model


@pytest.fixture
def op_stream(master_policy, sram_model, axi_lite_timing_test_space):
    rng = random.Random(SEED)
    pat = TransactionPatternGen(
        policy=master_policy,
        rng=rng,
        model=sram_model,
        pattern_cycles_per_timing=1,
    )
    pat.add_scatter_word_write_then_readback(count=8)
    pat.add_scatter_partial_writes_full_word_readback(
        count=16, allow_zero_byte_en=True)
    pat.add_sequential_write_block_then_read_block(block_len=8, wrap=True)
    pat.add_sequential_write_then_immediate_readback(count=16, wrap=True)
    pat.add_same_word_partial_writes_then_full_word_readback(
        writes_per_word=4,
        words=8,
        allow_zero_byte_en=True,
        random_lane_order=True,
    )
    pat.add_hazard_pingpong_raw_waw(iters=2)
    pat.add_boundary_edge_accesses_with_invalid(reps=1, include_invalid=False)
    return pat.stream(axi_lite_timing_test_space)


@pytest.mark.parametrize("sram_dw", [32, 64], ids=lambda dw: f"sram_dw={dw}")
def test_sram(sram_dut, master_policy, op_stream):
    trace = EventTrace()
    stim = AXILiteMasterStimulus(
        bus=sram_dut.sram_bus,
        op_source=op_stream,
        policy=master_policy,
        trace=trace,
        hazard_policy=HazardPolicy.STALL,
        max_cycles=MAX_CYCLES,
    )
    run_simulation(sram_dut, [stim.process()], vcd_name=None)
    # print(trace.dump())


@pytest.mark.xfail(reason="Known up converter bug (expected to fail until fixed)")
@pytest.mark.parametrize("master_dw, sram_dw", [pytest.param(32, 64, id="m32_to_s64")])
def test_upconverter(sram_dut, master_policy, op_stream, master_dw):
    trace = EventTrace()
    sram_dut.m_bus = axi.AXILiteInterface(
        data_width=master_dw, address_width=ADDR_WIDTH)
    sram_dut.submodules.up = axi.AXILiteUpConverter(
        sram_dut.m_bus, sram_dut.sram_bus)
    stim = AXILiteMasterStimulus(
        bus=sram_dut.m_bus,
        op_source=op_stream,
        policy=master_policy,
        trace=trace,
        hazard_policy=HazardPolicy.STALL,
        max_cycles=MAX_CYCLES,
    )
    run_simulation(sram_dut, [stim.process()], vcd_name=None)
    # print(trace.dump())


@pytest.mark.xfail(reason="Known down converter bug (expected to fail until fixed)")
@pytest.mark.parametrize("master_dw, sram_dw", [pytest.param(64, 32, id="m64_to_s32")])
def test_downconverter(sram_dut, master_policy, op_stream, master_dw):
    trace = EventTrace()
    sram_dut.m_bus = axi.AXILiteInterface(
        data_width=master_dw, address_width=ADDR_WIDTH)
    sram_dut.submodules.down = axi.AXILiteDownConverter(
        sram_dut.m_bus, sram_dut.sram_bus)
    stim = AXILiteMasterStimulus(
        bus=sram_dut.m_bus,
        op_source=op_stream,
        policy=master_policy,
        trace=trace,
        hazard_policy=HazardPolicy.STALL,
        max_cycles=MAX_CYCLES,
    )
    run_simulation(sram_dut, [stim.process()], vcd_name=None)
