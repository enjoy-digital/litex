#
# This file is part of LiteX.
#
# Copyright (c) 2026 Matt Thompson <matt@boondocker.io>
# SPDX-License-Identifier: BSD-2-Clause

import os
import stat
import random
import tempfile
import unittest
from unittest import mock

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *

from litex.build.generic_platform import Pins, Subsignal
from litex.build.altera.platform import AlteraPlatform

from litex.soc.cores.ram.intel_cyclone5_lpddr2 import CycloneVLPDDR2


# Helpers ------------------------------------------------------------------------------------------

_io = [
    ("clk50", 0, Pins("A1")),
    ("rst_n", 0, Pins("A2")),
    ("lpddr2", 0,
        Subsignal("ca",    Pins("B1 B2 B3 B4 B5 B6 B7 B8 B9 B10")),
        Subsignal("dq",    Pins(" ".join(f"C{n}" for n in range(32)))),
        Subsignal("dm",    Pins("D1 D2 D3 D4")),
        Subsignal("cke",   Pins("E1 E2")),
        Subsignal("cs_n",  Pins("F1 F2")),
        Subsignal("ck_p",  Pins("G1")),
        Subsignal("ck_n",  Pins("G2")),
        Subsignal("dqs_p", Pins("H1 H2 H3 H4")),
        Subsignal("dqs_n", Pins("J1 J2 J3 J4")),
    ),
    ("lpddr2_rzq", 0, Pins("K1")),
]


class _DUT(LiteXModule):
    """512MiB (14 rows, 10 columns, 8 banks, 32-bit) LPDDR2 at 300MHz from a 50MHz reference."""
    def __init__(self, platform=None, **kwargs):
        if platform is None:
            platform = AlteraPlatform("5CGXFC5C6F27C7", _io)
        self.platform = platform
        self.pads     = platform.request("lpddr2")
        self.cd_sys   = ClockDomain()
        self.lpddr2   = CycloneVLPDDR2(platform,
            pads          = self.pads,
            rzq           = platform.request("lpddr2_rzq"),
            ref_clk       = platform.request("clk50"),
            ref_clk_freq  = 50e6,
            mem_clk_freq  = 300e6,
            speedgrade    = 7,
            row_bits      = 14,
            col_bits      = 10,
            bank_bits     = 3,
            reset_n       = platform.request("rst_n"),
            ip_parameters = {
                "MEM_TCL"      : 7,
                "MEM_TRFC_NS"  : 130.0,
                "MEM_TREFI_US" : 3.9,
            },
            **kwargs
        )


class _HMC:
    """Stand-in for the UniPHY/HMC IP in simulation: collects the IOs of the instance, driven by
    _hmc_model."""
    ios = {}

    @staticmethod
    def lower(instance):
        for item in instance.items:
            if isinstance(item, Instance._IO):
                _HMC.ios[item.name] = item.expr
        return Module()


class _AsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        m = Module()
        m.comb += dr.cd.rst.eq(dr.async_reset)
        return m


@passive
def _hmc_model(testcase, memory, log, prng, calibration=0b011, calibration_delay=8, read_latency=2):
    """Avalon-MM port 0 of the Multi-Port Front End: random ready, read data after read_latency."""
    ios = _HMC.ios

    # Calibration.
    yield ios["afi_reset_n"].eq(1)
    for _ in range(calibration_delay):
        testcase.assertEqual((yield ios["avl_read_req_0"]),  0)
        testcase.assertEqual((yield ios["avl_write_req_0"]), 0)
        yield
    yield ios["local_init_done"].eq(  (calibration >> 0) & 1)
    yield ios["local_cal_success"].eq((calibration >> 1) & 1)
    yield ios["local_cal_fail"].eq(   (calibration >> 2) & 1)

    # Transfers.
    reads   = []
    stalled = None
    while True:
        ready   = (yield ios["avl_ready_0"])
        read    = (yield ios["avl_read_req_0"])
        write   = (yield ios["avl_write_req_0"])
        begin   = (yield ios["avl_burstbegin_0"])
        request = (
            read,
            write,
            (yield ios["avl_addr_0"]),
            (yield ios["avl_wdata_0"]),
            (yield ios["avl_be_0"]),
        )
        testcase.assertFalse(read and write)
        if read or write:
            # Burst begin on the first cycle of the transfer only, request stable until ready.
            testcase.assertEqual(begin, stalled is None)
            if stalled is not None:
                testcase.assertEqual(request, stalled)
            stalled = None if ready else request
        else:
            testcase.assertEqual(begin, 0)
        if ready and write:
            _, _, adr, data, be = request
            value = memory.get(adr, 0)
            for byte in range(4):
                if (be >> byte) & 1:
                    value = (value & ~(0xff << (8*byte))) | (data & (0xff << (8*byte)))
            memory[adr] = value
            log.append(("write", adr, data, be))
        if ready and read:
            _, _, adr, _, be = request
            testcase.assertEqual(be, 0b1111)
            reads.append([read_latency, adr])
            log.append(("read", adr))
        yield ios["avl_rdata_valid_0"].eq(0)
        for read in reads:
            read[0] -= 1
        if reads and (reads[0][0] <= 0):
            yield ios["avl_rdata_valid_0"].eq(1)
            yield ios["avl_rdata_0"].eq(memory.get(reads.pop(0)[1], 0))
        yield ios["avl_ready_0"].eq(prng.random() < 0.6)
        yield


def _ip_generate(root):
    """Stand-in for Quartus ip-generate (records its arguments) in a Quartus-like tree."""
    bin_dir = os.path.join(root, "sopc_builder", "bin")
    os.makedirs(bin_dir)
    ip_generate = os.path.join(bin_dir, "ip-generate")
    with open(ip_generate, "w") as f:
        f.write("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$(dirname \"$0\")/ip-generate.args\"\n")
    os.chmod(ip_generate, os.stat(ip_generate).st_mode | stat.S_IXUSR)
    return os.path.join(bin_dir, "ip-generate.args")


# Tests --------------------------------------------------------------------------------------------

class TestCycloneVLPDDR2(unittest.TestCase):
    def run_dut(self, dut, generator, memory=None, log=None, **kwargs):
        memory = {} if memory is None else memory
        log    = [] if log    is None else log
        _HMC.ios = {}
        run_simulation(dut,
            generators = {
                "sys"    : [generator()],
                "lpddr2" : [_hmc_model(self, memory, log, random.Random(0), **kwargs)],
            },
            clocks = {"sys": 20, "lpddr2": 13, "lpddr2_por": 20},
            special_overrides = {
                Instance               : _HMC,
                AsyncResetSynchronizer : _AsyncResetSynchronizer,
            },
        )

    def test_parameters(self):
        dut = _DUT()
        self.assertEqual(dut.lpddr2.size, 512*1024*1024)
        self.assertEqual(dut.lpddr2.bus.data_width, 32)
        self.assertEqual(list(dut.lpddr2.ip_parameters.items()), [
            ("HARD_EMIF",           "true"),
            ("HARD_PHY",            "true"),
            ("RATE",                "Full"),
            ("SPEED_GRADE",         7),
            ("MEM_CLK_FREQ",        300.0),
            ("REF_CLK_FREQ",        50.0),
            ("MEM_DQ_WIDTH",        32),
            ("MEM_ROW_ADDR_WIDTH",  14),
            ("MEM_COL_ADDR_WIDTH",  10),
            ("MEM_BANKADDR_WIDTH",  3),
            ("MEM_TCL",             7),
            ("MEM_TRFC_NS",         130.0),
            ("MEM_TREFI_US",        3.9),
            ("AVL_DATA_WIDTH_PORT", "32 32 32 32 32 32"),
            ("EXPORT_AFI_HALF_CLK", "true"),
            ("USER_DEBUG_LEVEL",    0),
        ])

    def test_verilog(self):
        # Elaboration without Quartus: instance of the IP, ports and clock domains.
        dut = _DUT(ip_name="lpddr2_ip")
        v   = str(dut.platform.get_verilog(dut))
        self.assertIn("lpddr2_ip lpddr2_ip(", v)
        self.assertIn(".pll_ref_clk                (clk50)", v)
        self.assertIn(".afi_half_clk               (lpddr2_clk)", v)
        self.assertIn(".mem_dq                     (lpddr2_dq)", v)
        self.assertIn(".avl_size_0                 (1'd1)", v)
        self.assertIn("& rst_n)", v)
        self.assertIn("lpddr2_por_done", v)
        self.assertIn("lpddr2_status_meta", v)
        self.assertIn("assign lpddr2_cs_n = {1'd1, ", v)

    def test_calibration_status(self):
        # Calibration status: driven by its fields only, read by software after calibration.
        dut = _DUT()
        v   = str(dut.platform.get_verilog(dut))
        self.assertEqual(len([l for l in v.splitlines() if "calibration_status <=" in l]), 0)

        dut = _DUT()

        def generator():
            self.assertEqual((yield from dut.lpddr2.calibration.read()), 0b000)
            for _ in range(64):
                yield
            self.assertEqual((yield from dut.lpddr2.calibration.read()), 0b011)

        self.run_dut(dut, generator)

    def test_constraints(self):
        dut = _DUT(ip_name="lpddr2_ip")
        self.assertEqual(dut.platform.toolchain.additional_sdc_commands, [
            "set_false_path -to [get_registers {*lpddr2_status_meta*}]",
            "set_false_path -from [get_registers {*lpddr2_por_done*}] "
            "-to [get_registers {*lpddr2_ip*|*}]",
        ])
        commands = [(command, id(signals["pad"]))
            for command, signals in dut.platform.constraint_manager.get_platform_commands()]
        expected = []
        for name, suffix in [
            ("ca",    "[*]"),
            ("ck_p",  ""),
            ("ck_n",  ""),
            ("dm",    "[*]"),
            ("dq",    "[*]"),
            ("dqs_p", "[*]"),
            ("dqs_n", "[*]"),
            ("cke",   "[0]"), # Only the first rank is used.
            ("cs_n",  "[0]"),
        ]:
            for assignment in [
                "OUTPUT_TERMINATION \"SERIES 34 OHM WITH CALIBRATION\"",
                "PACKAGE_SKEW_COMPENSATION OFF",
            ]:
                expected.append((
                    f"set_instance_assignment -name {assignment} -to {{pad}}{suffix}",
                    id(getattr(dut.pads, name)),
                ))
        self.assertEqual(commands, expected)

        # Other IO assignments.
        dut = _DUT(io_assignments=["PACKAGE_SKEW_COMPENSATION OFF"])
        self.assertEqual(len(dut.platform.constraint_manager.get_platform_commands()), 9)

    def test_generate_ip(self):
        dut = _DUT(ip_name="lpddr2_ip")
        with tempfile.TemporaryDirectory() as tmp:
            quartus    = os.path.realpath(os.path.join(tmp, "quartus"))
            output_dir = os.path.realpath(os.path.join(tmp, "gateware", "lpddr2"))
            args_file  = _ip_generate(quartus)

            def check(env, which):
                if os.path.exists(args_file):
                    os.remove(args_file)
                dut.platform.ips.clear()
                with mock.patch.dict(os.environ, env), mock.patch("shutil.which", return_value=which):
                    if "QUARTUS_ROOTDIR" not in env:
                        os.environ.pop("QUARTUS_ROOTDIR", None)
                    ip = dut.lpddr2.generate_ip(output_dir)
                self.assertEqual(ip, os.path.join(output_dir, "lpddr2_ip.qip"))
                self.assertEqual(dut.platform.ips, {ip})
                with open(args_file) as f:
                    self.assertEqual(f.read().splitlines(), [
                        "--component-name=altera_mem_if_lpddr2_emif",
                        "--file-set=QUARTUS_SYNTH",
                        "--standard-reports",
                        "--part=5CGXFC5C6F27C7",
                        "--output-name=lpddr2_ip",
                        f"--output-directory={output_dir}",
                        "--component-parameter=HARD_EMIF=true",
                        "--component-parameter=HARD_PHY=true",
                        "--component-parameter=RATE=Full",
                        "--component-parameter=SPEED_GRADE=7",
                        "--component-parameter=MEM_CLK_FREQ=300.0",
                        "--component-parameter=REF_CLK_FREQ=50.0",
                        "--component-parameter=MEM_DQ_WIDTH=32",
                        "--component-parameter=MEM_ROW_ADDR_WIDTH=14",
                        "--component-parameter=MEM_COL_ADDR_WIDTH=10",
                        "--component-parameter=MEM_BANKADDR_WIDTH=3",
                        "--component-parameter=MEM_TCL=7",
                        "--component-parameter=MEM_TRFC_NS=130.0",
                        "--component-parameter=MEM_TREFI_US=3.9",
                        "--component-parameter=AVL_DATA_WIDTH_PORT=32 32 32 32 32 32",
                        "--component-parameter=EXPORT_AFI_HALF_CLK=true",
                        "--component-parameter=USER_DEBUG_LEVEL=0",
                    ])

            # ip-generate from QUARTUS_ROOTDIR, then from the Quartus binaries on the PATH.
            check(env={"QUARTUS_ROOTDIR": quartus}, which=None)
            check(env={}, which=os.path.join(quartus, "bin", "quartus_map"))

            # Without Quartus.
            with mock.patch.dict(os.environ), mock.patch("shutil.which", return_value=None):
                os.environ.pop("QUARTUS_ROOTDIR", None)
                with self.assertRaisesRegex(OSError, "QUARTUS_ROOTDIR"):
                    dut.lpddr2.generate_ip(output_dir)

    def test_write_and_readback(self):
        dut    = _DUT()
        memory = {}
        log    = []
        data   = {adr: (0x01020304*(adr + 1)) & 0xffffffff for adr in [0, 1, 5, 0x3ff_ffff, 0x7ff_ffff]}

        def generator():
            for adr, value in data.items():
                yield from dut.lpddr2.bus.write(adr, value)
            for adr, value in data.items():
                self.assertEqual((yield from dut.lpddr2.bus.read(adr)), value)
            self.assertEqual((yield from dut.lpddr2.calibration.read()), 0b011)

        self.run_dut(dut, generator, memory, log)
        self.assertEqual(memory, data)
        self.assertEqual(log,
            [("write", adr, value, 0b1111) for adr, value in data.items()] +
            [("read",  adr)                for adr        in data.keys()])

    def test_byte_enables(self):
        dut    = _DUT()
        memory = {3: 0xaabbccdd}

        def generator():
            yield from dut.lpddr2.bus.write(3, 0x11223344, sel=0b1010)
            self.assertEqual((yield from dut.lpddr2.bus.read(3)), 0x11bb33dd)

        self.run_dut(dut, generator, memory)
        self.assertEqual(memory, {3: 0x11bb33dd})

    def test_accesses_wait_for_calibration(self):
        dut = _DUT()
        log = []

        def generator():
            # Access started before the end of the calibration (checked by the model).
            yield from dut.lpddr2.bus.write(1, 0x12345678)
            self.assertEqual((yield from dut.lpddr2.bus.read(1)), 0x12345678)

        self.run_dut(dut, generator, log=log, calibration_delay=64)
        self.assertEqual(log, [("write", 1, 0x12345678, 0b1111), ("read", 1)])

    def test_calibration_failure(self):
        dut = _DUT()
        log = []

        def generator():
            bus = dut.lpddr2.bus
            yield bus.adr.eq(1)
            yield bus.we.eq(1)
            yield bus.sel.eq(0b1111)
            yield bus.cyc.eq(1)
            yield bus.stb.eq(1)
            yield
            while not (yield bus.err):
                self.assertEqual((yield bus.ack), 0)
                yield
            yield bus.cyc.eq(0)
            yield bus.stb.eq(0)
            yield
            self.assertEqual((yield from dut.lpddr2.calibration.read()), 0b101)

        self.run_dut(dut, generator, log=log, calibration=0b101)
        self.assertEqual(log, [])


if __name__ == "__main__":
    unittest.main()
