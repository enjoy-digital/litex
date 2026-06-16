#
# This file is part of LiteX
#
# Copyright (c) 2019-2024 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2024 MoTeC <www.motec.com.au>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import *

from litex.soc.cores.hyperbus import (
    HyperRAM,
    HyperRAMAXIFrontend,
    HyperRAMAXILiteFrontend,
    HyperRAMClkGen,
    HyperRAMNativePort,
    HyperRAMWishboneFrontend,
    hyperam_ios_layout,
    hyperram_ios_layout,
    hyperram_phy_tx_layout,
)
from litex.soc.interconnect import axi, wishbone
from litex.soc.integration.soc import SoCBusHandler, SoCRegion

def c2bool(c):
    return {"-": 1, "_": 0}[c]


class Pads: pass

class HyperRamPads:
    def __init__(self, dw=8):
        self.clk   = Signal()
        self.rst_n = Signal()
        self.cs_n  = Signal()
        self.dq    = Record([("oe", 1), ("o", dw),     ("i", dw)])
        self.rwds  = Record([("oe", 1), ("o", dw//8),  ("i", dw//8)])

class HyperRamSplitPads:
    def __init__(self, dw=8):
        self.clk     = Signal()
        self.rst_n   = Signal()
        self.cs_n    = Signal()
        self.dq_o    = Signal(dw)
        self.dq_oe   = Signal()
        self.dq_i    = Signal(dw)
        self.rwds_o  = Signal(dw//8)
        self.rwds_oe = Signal()
        self.rwds_i  = Signal(dw//8)

class HyperRAMAXIFrontendDUT(LiteXModule):
    def __init__(self, id_width=4):
        self.axi = axi.AXIInterface(data_width=32, address_width=32, id_width=id_width)
        self.port = HyperRAMNativePort()
        self.frontend = HyperRAMAXIFrontend(self.axi, self.port)
        self.errors = 0

class HyperRAMAXILiteFrontendDUT(LiteXModule):
    def __init__(self):
        self.axi_lite = axi.AXILiteInterface(data_width=32, address_width=32)
        self.port = HyperRAMNativePort()
        self.frontend = HyperRAMAXILiteFrontend(self.axi_lite, self.port)
        self.errors = 0

class HyperRAMWishboneFrontendDUT(LiteXModule):
    def __init__(self):
        self.wishbone = wishbone.Interface(
            data_width    = 32,
            address_width = 32,
            addressing    = "word",
            bursting      = True,
        )
        self.port = HyperRAMNativePort()
        self.frontend = HyperRAMWishboneFrontend(self.wishbone, self.port)
        self.errors = 0

def axi_aw_send(bus, addr, burst_len=0, burst_type=axi.BURST_INCR, size=2, id=0):
    yield bus.aw.valid.eq(1)
    yield bus.aw.addr.eq(addr)
    yield bus.aw.burst.eq(burst_type)
    yield bus.aw.len.eq(burst_len)
    yield bus.aw.size.eq(size)
    yield bus.aw.id.eq(id)
    yield
    while (yield bus.aw.ready) == 0:
        yield
    yield bus.aw.valid.eq(0)

def axi_w_send(bus, data, last, strb=0xf):
    yield bus.w.valid.eq(1)
    yield bus.w.data.eq(data)
    yield bus.w.strb.eq(strb)
    yield bus.w.last.eq(int(last))
    yield
    while (yield bus.w.ready) == 0:
        yield
    yield bus.w.valid.eq(0)

def axi_b_recv(bus, ready_delay=0):
    for _ in range(ready_delay):
        yield
    yield bus.b.ready.eq(1)
    yield
    while (yield bus.b.valid) == 0:
        yield
    resp = (yield bus.b.resp)
    bid  = (yield bus.b.id)
    yield bus.b.ready.eq(0)
    yield
    return resp, bid

def axi_ar_send(bus, addr, burst_len=0, burst_type=axi.BURST_INCR, size=2, id=0):
    yield bus.ar.valid.eq(1)
    yield bus.ar.addr.eq(addr)
    yield bus.ar.burst.eq(burst_type)
    yield bus.ar.len.eq(burst_len)
    yield bus.ar.size.eq(size)
    yield bus.ar.id.eq(id)
    yield
    while (yield bus.ar.ready) == 0:
        yield
    yield bus.ar.valid.eq(0)

def axi_r_recv_one(bus, ready_delay=0):
    for _ in range(ready_delay):
        yield
    yield bus.r.ready.eq(1)
    while (yield bus.r.valid) == 0:
        yield
    data = (yield bus.r.data)
    resp = (yield bus.r.resp)
    rid  = (yield bus.r.id)
    last = (yield bus.r.last)
    yield bus.r.ready.eq(0)
    yield
    while (yield bus.r.valid):
        yield
    return data, resp, rid, last

def axi_write_burst(bus, addr, values, strbs=None, burst_type=axi.BURST_INCR, size=2, id=0, b_ready_delay=0):
    if strbs is None:
        strbs = [0xf]*len(values)
    yield from axi_aw_send(bus, addr, burst_len=len(values) - 1, burst_type=burst_type, size=size, id=id)
    for n, (value, strb) in enumerate(zip(values, strbs)):
        yield from axi_w_send(bus, value, last=(n == len(values) - 1), strb=strb)
    return (yield from axi_b_recv(bus, ready_delay=b_ready_delay))

def axi_read_burst(bus, addr, length, burst_type=axi.BURST_INCR, size=2, id=0, r_ready_delay=0):
    yield from axi_ar_send(bus, addr, burst_len=length - 1, burst_type=burst_type, size=size, id=id)
    data = []
    for n in range(length):
        data.append((yield from axi_r_recv_one(bus, ready_delay=r_ready_delay if n == 0 else 0)))
    return data

@passive
def native_port_model(port, log, read_data=None, ready_delay=1):
    if read_data is None:
        read_data = {}
    while True:
        yield port.req_ready.eq(0)
        yield port.rsp_valid.eq(0)
        while not (yield port.req_valid):
            yield
        for _ in range(ready_delay):
            yield
        adr = (yield port.req_addr)
        write = (yield port.req_write)
        log.append({
            "adr"   : adr,
            "we"    : write,
            "dat_w" : (yield port.req_wdata),
            "sel"   : (yield port.req_sel),
            "burst" : (yield port.req_burst),
        })
        yield port.req_ready.eq(1)
        yield
        yield port.req_ready.eq(0)
        if write:
            yield port.rsp_valid.eq(1)
            yield
            yield port.rsp_valid.eq(0)
        else:
            while not (yield port.rsp_ready):
                yield
            yield port.rsp_rdata.eq(read_data.get(adr, 0x1000_0000 | adr))
            yield port.rsp_valid.eq(1)
            yield
            yield port.rsp_valid.eq(0)
        yield

class TestHyperRAM(unittest.TestCase):
    def test_hyperram_clkgen_phase_pattern(self):
        def generator(dut):
            expected = [
                (0, 0, 0, 0),
                (1, 0, 1, 1),
                (2, 0, 1, 0),
                (3, 1, 0, 0),
                (0, 0, 0, 0),
            ]
            for phase, rise, clk, fall in expected:
                self.assertEqual((yield dut.phase), phase)
                self.assertEqual((yield dut.rise), rise)
                self.assertEqual((yield dut.cd_hyperram.clk), clk)
                self.assertEqual((yield dut.fall), fall)
                yield

        dut = HyperRAMClkGen()
        run_simulation(dut, generator(dut))

    def test_hyperram_layout_helpers_validate_data_width(self):
        self.assertEqual(hyperram_ios_layout(8), hyperam_ios_layout(8))
        self.assertEqual(hyperram_phy_tx_layout(16)[3], ("dq", 16))
        with self.assertRaisesRegex(ValueError, "data buses"):
            hyperram_ios_layout(12)

    def test_hyperram_syntax(self):
        pads = Record([("clk", 1), ("rst_n", 1), ("cs_n", 1), ("dq", 8), ("rwds", 1)])
        hyperram = HyperRAM(pads)

        pads = Record([("clk_p", 1), ("clk_n", 1), ("rst_n", 1), ("cs_n", 1), ("dq", 8), ("rwds", 1)])
        hyperram = HyperRAM(pads)

        pads = HyperRamSplitPads(dw=16)
        hyperram = HyperRAM(pads)

    def test_hyperram_rejects_invalid_pads(self):
        pads = HyperRamPads(dw=16)
        pads.rwds = Signal(1)
        with self.assertRaisesRegex(ValueError, "RWDS width"):
            HyperRAM(pads)

        pads = HyperRamSplitPads(dw=8)
        del pads.rwds_oe
        with self.assertRaisesRegex(ValueError, "rwds"):
            HyperRAM(pads)

        pads = HyperRamSplitPads(dw=8)
        del pads.clk
        with self.assertRaisesRegex(ValueError, "clk"):
            HyperRAM(pads)

        pads = HyperRamSplitPads(dw=8)
        del pads.clk
        pads.clk_p = Signal()
        with self.assertRaisesRegex(ValueError, "clk_p and clk_n"):
            HyperRAM(pads)

    def test_hyperram_rejects_invalid_parameters(self):
        with self.assertRaisesRegex(ValueError, "latency"):
            HyperRAM(HyperRamPads(), latency=2)
        with self.assertRaisesRegex(ValueError, "latency"):
            HyperRAM(HyperRamPads(), latency=8)
        with self.assertRaisesRegex(ValueError, "latency mode"):
            HyperRAM(HyperRamPads(), latency_mode="invalid")
        with self.assertRaisesRegex(ValueError, "clock ratio"):
            HyperRAM(HyperRamPads(), clk_ratio="1:1")
        with self.assertRaisesRegex(ValueError, "bus standard"):
            HyperRAM(HyperRamPads(), bus_standard="avalon")
        with self.assertRaisesRegex(ValueError, "AXI ID width"):
            HyperRAM(HyperRamPads(), bus_standard="axi", axi_id_width=0)

    def test_hyperram_bus_standard_interfaces(self):
        self.assertIsInstance(HyperRAM(HyperRamPads(), with_csr=False).bus, wishbone.Interface)
        self.assertIsInstance(
            HyperRAM(HyperRamPads(), bus_standard="axi-lite", with_csr=False).bus,
            axi.AXILiteInterface)
        hyperram = HyperRAM(HyperRamPads(), bus_standard="axi", axi_id_width=4, with_csr=False)
        self.assertIsInstance(hyperram.bus, axi.AXIInterface)
        self.assertEqual(hyperram.bus.id_width, 4)

    def test_hyperram_wishbone_write_ack_is_data_phase(self):
        def generator(dut):
            yield dut.bus.cyc.eq(1)
            yield dut.bus.stb.eq(1)
            yield dut.bus.we.eq(1)
            yield dut.bus.adr.eq(0x1234)
            yield dut.bus.dat_w.eq(0xdeadbeef)
            yield dut.bus.sel.eq(0xf)

            for _ in range(8):
                yield
                self.assertEqual((yield dut.bus.ack), 0)

            ack_seen = False
            for _ in range(128):
                yield
                if (yield dut.bus.ack):
                    ack_seen = True
                    break

            self.assertTrue(ack_seen)
            yield dut.bus.cyc.eq(0)
            yield dut.bus.stb.eq(0)
            yield dut.bus.we.eq(0)
            yield

        dut = HyperRAM(HyperRamPads(), latency=5, latency_mode="fixed")
        run_simulation(dut, generator(dut))

    def test_hyperram_wishbone_frontend_allows_burst_overlap(self):
        def generator(dut):
            yield dut.wishbone.cyc.eq(1)
            yield dut.wishbone.stb.eq(1)
            yield dut.wishbone.we.eq(0)
            yield dut.wishbone.adr.eq(0)
            yield dut.wishbone.cti.eq(wishbone.CTI_BURST_INCREMENTING)
            yield dut.port.req_ready.eq(1)
            yield
            self.assertEqual((yield dut.port.req_valid), 1)
            yield dut.port.req_ready.eq(0)
            yield dut.wishbone.adr.eq(1)
            yield dut.port.rsp_valid.eq(1)
            yield dut.port.req_ready.eq(1)
            yield
            self.assertEqual((yield dut.wishbone.ack), 1)
            self.assertEqual((yield dut.port.req_valid), 1)
            self.assertEqual((yield dut.port.req_addr), 1)

            yield dut.port.rsp_valid.eq(0)
            yield dut.port.req_ready.eq(0)
            yield dut.wishbone.we.eq(1)
            yield dut.wishbone.adr.eq(2)
            yield dut.wishbone.dat_w.eq(0x12345678)
            yield dut.wishbone.cti.eq(wishbone.CTI_BURST_INCREMENTING)
            yield dut.port.req_ready.eq(1)
            yield dut.port.rsp_valid.eq(1)
            yield
            self.assertEqual((yield dut.wishbone.ack), 1)
            self.assertEqual((yield dut.port.req_valid), 1)
            self.assertEqual((yield dut.port.req_addr), 2)
            yield

        dut = HyperRAMWishboneFrontendDUT()
        run_simulation(dut, generator(dut))

    def test_hyperram_wishbone_write_burst_uses_single_command(self):
        command_starts = []

        def fpga_gen(dut):
            values = [0x01234567, 0x89abcdef, 0xdeadbeef, 0xc0ffee00]
            yield dut.bus.cyc.eq(1)
            yield dut.bus.stb.eq(1)
            yield dut.bus.we.eq(1)
            yield dut.bus.sel.eq(0xf)
            yield dut.bus.adr.eq(0)
            yield dut.bus.dat_w.eq(values[0])
            yield dut.bus.cti.eq(wishbone.CTI_BURST_INCREMENTING)

            for n, value in enumerate(values):
                for _ in range(256):
                    if (yield dut.bus.ack):
                        break
                    yield
                else:
                    self.fail("Wishbone write burst timed out.")

                if n == (len(values) - 1):
                    break
                yield dut.bus.adr.eq(n + 1)
                yield dut.bus.dat_w.eq(values[n + 1])
                yield dut.bus.cti.eq(
                    wishbone.CTI_BURST_END if n == (len(values) - 2) else
                    wishbone.CTI_BURST_INCREMENTING)
                yield

            yield dut.bus.cyc.eq(0)
            yield dut.bus.stb.eq(0)
            yield dut.bus.we.eq(0)
            yield dut.bus.cti.eq(wishbone.CTI_BURST_NONE)
            for _ in range(64):
                yield

        def monitor(dut):
            was_cmd_address = 0
            for cycle in range(512):
                is_cmd_address = (yield dut.core.fsm.state) == cmd_address
                if is_cmd_address and not was_cmd_address:
                    command_starts.append(cycle)
                was_cmd_address = is_cmd_address
                yield

        dut = HyperRAM(HyperRamPads(), latency=5, latency_mode="fixed")
        cmd_address = dut.core.fsm.encoding["CMD-ADDRESS"]
        run_simulation(dut, [fpga_gen(dut), monitor(dut)])

        self.assertEqual(len(command_starts), 1)

    def test_hyperram_soc_bus_kwargs_keep_native_slave(self):
        cases = [
            ("wishbone", wishbone.Interface),
            ("axi-lite", axi.AXILiteInterface),
            ("axi",      axi.AXIInterface),
        ]

        for bus_standard, interface_cls in cases:
            with self.subTest(bus_standard=bus_standard):
                soc_bus = SoCBusHandler(standard=bus_standard)
                if bus_standard == "axi":
                    soc_bus.add_master("cpu", axi.AXIInterface(data_width=32, address_width=32, id_width=4))

                hyperram = HyperRAM(HyperRamPads(),
                    with_csr = False,
                    **soc_bus.get_bus_standard_kwargs(with_axi_id_width=True))
                soc_bus.add_slave("hyperram", hyperram.bus, SoCRegion(origin=0x00000000, size=0x1000))

                self.assertIsInstance(hyperram.bus, interface_cls)
                self.assertIs(soc_bus.slaves["hyperram"], hyperram.bus)
                if bus_standard == "axi":
                    self.assertEqual(hyperram.bus.id_width, 4)

    def test_hyperram_axi_frontend_write_incr_burst(self):
        log = []
        values = [0x01234567, 0x89abcdef, 0xdeadbeef, 0xc0ffee00]
        strbs  = [0xf, 0x3, 0xc, 0xf]

        def generator(dut):
            resp, bid = yield from axi_write_burst(
                dut.axi,
                addr  = 0x1000,
                values= values,
                strbs = strbs,
                id    = 5)
            self.assertEqual(resp, axi.RESP_OKAY)
            self.assertEqual(bid, 5)

        dut = HyperRAMAXIFrontendDUT(id_width=4)
        run_simulation(dut, [generator(dut), native_port_model(dut.port, log)])

        self.assertEqual([entry["adr"] for entry in log], [0x400, 0x401, 0x402, 0x403])
        self.assertEqual([entry["dat_w"] for entry in log], values)
        self.assertEqual([entry["sel"] for entry in log], strbs)
        self.assertEqual([entry["we"] for entry in log], [1, 1, 1, 1])
        self.assertEqual([entry["burst"] for entry in log], [1, 1, 1, 0])

    def test_hyperram_axi_frontend_read_incr_burst(self):
        log = []
        read_data = {
            0x20: 0x11111111,
            0x21: 0x22222222,
            0x22: 0x33333333,
            0x23: 0x44444444,
        }

        def generator(dut):
            beats = yield from axi_read_burst(dut.axi, addr=0x80, length=4, id=6)
            self.assertEqual([beat[0] for beat in beats], [
                read_data[0x20],
                read_data[0x21],
                read_data[0x22],
                read_data[0x23],
            ])
            self.assertEqual([beat[1] for beat in beats], [axi.RESP_OKAY]*4)
            self.assertEqual([beat[2] for beat in beats], [6]*4)
            self.assertEqual([beat[3] for beat in beats], [0, 0, 0, 1])

        dut = HyperRAMAXIFrontendDUT(id_width=4)
        run_simulation(dut, [generator(dut), native_port_model(dut.port, log, read_data)])

        self.assertEqual([entry["adr"] for entry in log], [0x20, 0x21, 0x22, 0x23])
        self.assertEqual([entry["we"] for entry in log], [0, 0, 0, 0])
        self.assertEqual([entry["burst"] for entry in log], [1, 1, 1, 0])

    def test_hyperram_axi_frontend_wrap_and_fixed_are_decomposed(self):
        log = []

        def generator(dut):
            resp, bid = yield from axi_write_burst(
                dut.axi,
                addr       = 0x108,
                values     = [0x10, 0x11, 0x12, 0x13],
                burst_type = axi.BURST_WRAP,
                id         = 1)
            self.assertEqual(resp, axi.RESP_OKAY)
            self.assertEqual(bid, 1)

            resp, bid = yield from axi_write_burst(
                dut.axi,
                addr       = 0x200,
                values     = [0x20, 0x21, 0x22],
                burst_type = axi.BURST_FIXED,
                id         = 2)
            self.assertEqual(resp, axi.RESP_OKAY)
            self.assertEqual(bid, 2)

        dut = HyperRAMAXIFrontendDUT(id_width=4)
        run_simulation(dut, [generator(dut), native_port_model(dut.port, log)])

        self.assertEqual([entry["adr"] for entry in log], [
            0x42, 0x43, 0x40, 0x41,
            0x80, 0x80, 0x80,
        ])
        self.assertEqual([entry["burst"] for entry in log], [0]*7)

    def test_hyperram_axi_frontend_rejects_unsupported_requests(self):
        log = []

        def generator(dut):
            resp, bid = yield from axi_write_burst(
                dut.axi,
                addr  = 0x100,
                values= [0x12345678],
                size  = 3,
                id    = 3)
            self.assertEqual(resp, axi.RESP_SLVERR)
            self.assertEqual(bid, 3)

            beats = yield from axi_read_burst(
                dut.axi,
                addr       = 0x100,
                length     = 1,
                burst_type = axi.BURST_RESERVED,
                id         = 4)
            self.assertEqual(beats, [(0, axi.RESP_SLVERR, 4, 1)])

        dut = HyperRAMAXIFrontendDUT(id_width=4)
        run_simulation(dut, [generator(dut), native_port_model(dut.port, log)])
        self.assertEqual(log, [])

    def test_hyperram_axi_frontend_holds_responses_under_backpressure(self):
        log = []
        read_data = {0x40: 0xfeedface}

        def generator(dut):
            resp, bid = yield from axi_write_burst(
                dut.axi,
                addr          = 0x100,
                values        = [0xa5a5a5a5],
                id            = 7,
                b_ready_delay = 4)
            self.assertEqual(resp, axi.RESP_OKAY)
            self.assertEqual(bid, 7)

            yield from axi_ar_send(dut.axi, addr=0x100, id=8)
            for _ in range(4):
                self.assertEqual((yield dut.axi.r.ready), 0)
                yield
            data, resp, rid, last = yield from axi_r_recv_one(dut.axi)
            self.assertEqual((data, resp, rid, last), (0xfeedface, axi.RESP_OKAY, 8, 1))

        dut = HyperRAMAXIFrontendDUT(id_width=4)
        run_simulation(dut, [generator(dut), native_port_model(dut.port, log, read_data)])

        self.assertEqual([entry["adr"] for entry in log], [0x40, 0x40])

    def test_hyperram_axi_lite_frontend_single_accesses(self):
        log = []
        read_data = {0x41: 0x1234abcd}

        def generator(dut):
            resp = yield from dut.axi_lite.write(0x100, 0xdeadbeef, strb=0b0101)
            self.assertEqual(resp, axi.RESP_OKAY)

            data, resp = yield from dut.axi_lite.read(0x104)
            self.assertEqual((data, resp), (0x1234abcd, axi.RESP_OKAY))

        dut = HyperRAMAXILiteFrontendDUT()
        run_simulation(dut, [generator(dut), native_port_model(dut.port, log, read_data)])

        self.assertEqual([entry["adr"] for entry in log], [0x40, 0x41])
        self.assertEqual([entry["we"] for entry in log], [1, 0])
        self.assertEqual(log[0]["dat_w"], 0xdeadbeef)
        self.assertEqual(log[0]["sel"], 0b0101)
        self.assertEqual([entry["burst"] for entry in log], [0, 0])

    def test_hyperram_write_latency_5_2x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "----__________________________________________________________------"
            dq_oe   = "______------------____________________________________--------______"
            dq_o    = "0000002000048d0000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "______________________________________________________--------______"
            rwds_o  = "________________________________________________________----________"
            yield
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]),   (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]),  (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(dw=8), latency=5, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_write_latency_5_2x_sys2x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "________________--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "_------------__________________________________________________________------"
            dq_oe   = "_______________------------____________________________________--------______"
            dq_o    = "0000000000000002000048d0000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "_______________________________________________________________--------______"
            rwds_o  = "_________________________________________________________________----________"
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                #if (yield dut.pads.dq.oe):
                #    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield
            for i in range(128):
                yield

        dut = HyperRAM(HyperRamPads(), latency=5, latency_mode="fixed", clk_ratio="2:1")
        generators = {
            "sys"   : fpga_gen(dut),
            "sys2x" : hyperram_gen(dut),
        }
        clocks = {
            "sys"   : 4,
            "sys2x" : 2,
        }
        run_simulation(dut, generators, clocks, vcd_name="sim.vcd")

    def test_hyperram_write_latches_cti(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001, cti=0b010)
            yield
            self.assertEqual((yield dut.core.bus_cti), 0b010)
            yield

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "----__________________________________________________________________------"
            dq_oe   = "______------------____________________________________________--------______"
            dq_o    = "0000002000048d000000000000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "______________________________________________________________--------______"
            rwds_o  = "________________________________________________________________----________"
            yield
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(), latency=6, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_write_latency_6_2x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "----__________________________________________________________________------"
            dq_oe   = "______------------____________________________________________--------______"
            dq_o    = "0000002000048d000000000000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "______________________________________________________________--------______"
            rwds_o  = "________________________________________________________________----________"
            yield
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(), latency=6, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_write_latency_7_2x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "----__________________________________________________________________________------"
            dq_oe   = "______------------____________________________________________________--------______"
            dq_o    = "0000002000048d00000000000000000000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "______________________________________________________________________--------______"
            rwds_o  = "________________________________________________________________________----________"
            yield
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(), latency=7, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_write_latency_7_1x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "----______________________________________________------"
            dq_oe   = "______------------________________________--------______"
            dq_o    = "0000002000048d0000000000000000000000000000deadbeef000000"
            rwds_oe = "__________________________________________--------______"
            rwds_o  = "____________________________________________----________"
            yield
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(), latency=7, latency_mode="variable")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_read_latency_5_2x(self):
        def fpga_gen(dut):
            dat = yield from dut.bus.read(0x1234)
            self.assertEqual(dat, 0xdeadbeef)

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_____"
            cs_n    = "----______________________________________________________________________________----"
            dq_oe   = "______------------____________________________________________________________________"
            dq_o    = "000000a000048d000000000000000000000000000000000000000000000000000000000000000000000000"
            dq_i    = "000000000000000000000000000000000000000000000000000000deadbeefcafefade0000000000000000"
            rwds_oe = "______________________________________________________________________________________"
            rwds_i  = "______________________________________________________--__--__--__--__________________"
            yield
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                yield dut.pads.rwds.i.eq(c2bool(rwds_i[i]))
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                yield

        dut = HyperRAM(HyperRamPads(), latency=5, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_read_latency_6_2x(self):
        def fpga_gen(dut):
            dat = yield from dut.bus.read(0x1234)
            self.assertEqual(dat, 0xdeadbeef)

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_____"
            cs_n    = "----______________________________________________________________________________________----"
            dq_oe   = "______------------____________________________________________________________________________"
            dq_o    = "000000a000048d00000000000000000000000000000000000000000000000000000000000000000000000000000000"
            dq_i    = "00000000000000000000000000000000000000000000000000000000000000deadbeefcafefade0000000000000000"
            rwds_oe = "______________________________________________________________________________________________"
            rwds_i  = "______________________________________________________________--__--__--__--__________________"
            yield
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                yield dut.pads.rwds.i.eq(c2bool(rwds_i[i]))
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                yield

        dut = HyperRAM(HyperRamPads(), latency=6, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_read_latency_7_2x(self):
        def fpga_gen(dut):
            dat = yield from dut.bus.read(0x1234)
            self.assertEqual(dat, 0xdeadbeef)


        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_____"
            cs_n    = "----______________________________________________________________________________________________----"
            dq_oe   = "______------------____________________________________________________________________________________"
            dq_o    = "000000a000048d0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
            dq_i    = "0000000000000000000000000000000000000000000000000000000000000000000000deadbeefcafefade0000000000000000"
            rwds_oe = "______________________________________________________________________________________________________"
            rwds_i  = "______________________________________________________________________--__--__--__--__________________"
            yield
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                yield dut.pads.rwds.i.eq(c2bool(rwds_i[i]))
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                yield

        dut = HyperRAM(HyperRamPads(), latency=7, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_read_latency_7_1x(self):
        def fpga_gen(dut):
            dat = yield from dut.bus.read(0x1234)
            self.assertEqual(dat, 0xdeadbeef)

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__-______"
            cs_n    = "----________________________________________________________________------"
            dq_oe   = "______------------________________________________________________________"
            dq_o    = "000000a000048d000000000000000000000000000000000000000000000000000000000000"
            dq_i    = "0000000000000000000000000000000000000000deadbeefcafefade000000000000000000"
            rwds_oe = "__________________________________________________________________________"
            rwds_i  = "________________________________________--__--__--__--____________________"
            yield
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                yield dut.pads.rwds.i.eq(c2bool(rwds_i[i]))
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                yield

        dut = HyperRAM(HyperRamPads(), latency=7, latency_mode="variable")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_reg_write(self):
        def fpga_gen(dut):
            yield dut.core.reg.adr.eq(2)
            yield dut.core.reg.dat_w.eq(0x1234)
            yield
            yield dut.core.reg.stb.eq(1)
            yield dut.core.reg.we.eq(1)
            while (yield dut.core.reg.ack) == 0:
                yield
            yield dut.core.reg.stb.eq(0)

        def hyperram_gen(dut):
            clk     = "___________--__--__--__--___________"
            cs_n    = "--------__________________----------"
            dq_oe   = "__________----------------__________"
            dq_o    = "000000000060000100000012340000000000"
            rwds_oe = "____________________________________"
            rwds_o  = "____________________________________"
            yield
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(), with_csr=False)
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")#
