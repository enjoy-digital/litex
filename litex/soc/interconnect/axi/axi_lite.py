#
# This file is part of LiteX.
#
# Copyright (c) 2018-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""AXI4-Full/Lite support for LiteX"""

from migen import *
from migen.genlib import roundrobin

from litex.gen import *

from litex.gen.genlib.misc import WaitTimer

from litex.build.generic_platform import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.axi.axi_common import *

# AXI-Lite Definition ------------------------------------------------------------------------------

def ax_lite_description(address_width):
    return [
        ("addr",  address_width),
        ("prot",  3), # *
    ]
    # * present for interconnect with others cores but not used by LiteX.

def w_lite_description(data_width):
    return [
        ("data", data_width),
        ("strb", data_width//8)
    ]

def b_lite_description():
    return [("resp", 2)]

def r_lite_description(data_width):
    return [
        ("resp", 2),
        ("data", data_width)
    ]

class AXILiteInterface:
    def __init__(self, data_width=32, address_width=32, clock_domain="sys", name=None, bursting=False):
        self.data_width    = data_width
        self.address_width = address_width
        self.clock_domain  = clock_domain
        if bursting is not False:
            raise NotImplementedError("AXI-Lite does not support bursting")

        self.aw = stream.Endpoint(ax_lite_description(address_width), name=name)
        self.w  = stream.Endpoint(w_lite_description(data_width),     name=name)
        self.b  = stream.Endpoint(b_lite_description(),               name=name)
        self.ar = stream.Endpoint(ax_lite_description(address_width), name=name)
        self.r  = stream.Endpoint(r_lite_description(data_width),     name=name)

    def get_ios(self, bus_name="wb"):
        subsignals = []
        for channel in ["aw", "w", "b", "ar", "r"]:
            for name in ["valid", "ready"]:
                subsignals.append(Subsignal(channel + name, Pins(1)))
            for name, width in getattr(self, channel).description.payload_layout:
                subsignals.append(Subsignal(channel + name, Pins(width)))
        ios = [(bus_name , 0) + tuple(subsignals)]
        return ios

    def connect_to_pads(self, pads, mode="master"):
        return connect_to_pads(self, pads, mode)

    def connect(self, slave, **kwargs):
        return connect_axi(self, slave, **kwargs)

    def layout_flat(self):
        return list(axi_layout_flat(self))

    def write(self, addr, data, strb=None):
        if strb is None:
            strb = 2**len(self.w.strb) - 1
        # aw + w
        yield self.aw.valid.eq(1)
        yield self.aw.addr.eq(addr)
        yield self.w.data.eq(data)
        yield self.w.valid.eq(1)
        yield self.w.strb.eq(strb)
        yield
        while not (yield self.aw.ready):
            yield
        yield self.aw.valid.eq(0)
        yield self.aw.addr.eq(0)
        while not (yield self.w.ready):
            yield
        yield self.w.valid.eq(0)
        yield self.w.strb.eq(0)
        # b
        yield self.b.ready.eq(1)
        while not (yield self.b.valid):
            yield
        resp = (yield self.b.resp)
        yield self.b.ready.eq(0)
        return resp

    def read(self, addr):
        # ar
        yield self.ar.valid.eq(1)
        yield self.ar.addr.eq(addr)
        yield
        while not (yield self.ar.ready):
            yield
        yield self.ar.valid.eq(0)
        # r
        yield self.r.ready.eq(1)
        while not (yield self.r.valid):
            yield
        data = (yield self.r.data)
        resp = (yield self.r.resp)
        yield self.r.ready.eq(0)
        return (data, resp)

# AXI-Lite to Simple Bus ---------------------------------------------------------------------------

def axi_lite_to_simple(axi_lite, port_adr, port_dat_r, port_dat_w=None, port_we=None):
    """Connection of AXILite to simple bus with 1-cycle latency, such as CSR bus or Memory port"""
    bus_data_width = axi_lite.data_width
    adr_shift      = log2_int(bus_data_width//8)
    do_read        = Signal()
    do_write       = Signal()
    last_was_read  = Signal()

    comb = []
    if port_dat_w is not None:
        comb.append(port_dat_w.eq(axi_lite.w.data))
    if port_we is not None:
        if len(port_we) > 1:
            for i in range(bus_data_width//8):
                comb.append(port_we[i].eq(axi_lite.w.valid & axi_lite.w.ready & axi_lite.w.strb[i]))
        else:
            comb.append(port_we.eq(axi_lite.w.valid & axi_lite.w.ready & (axi_lite.w.strb != 0)))

    fsm = FSM()
    fsm.act("START-TRANSACTION",
        # If the last access was a read, do a write, and vice versa.
        If(axi_lite.aw.valid & axi_lite.ar.valid,
            do_write.eq(last_was_read),
            do_read.eq(~last_was_read),
        ).Else(
            do_write.eq(axi_lite.aw.valid),
            do_read.eq(axi_lite.ar.valid),
        ),
        # Start reading/writing immediately not to waste a cycle.
        axi_lite.aw.ready.eq(last_was_read  | ~axi_lite.ar.valid),
        axi_lite.ar.ready.eq(~last_was_read | ~axi_lite.aw.valid),
        If(do_write,
            port_adr.eq(axi_lite.aw.addr[adr_shift:]),
            If(axi_lite.w.valid,
                axi_lite.w.ready.eq(1),
                NextState("SEND-WRITE-RESPONSE")
            )
        ).Elif(do_read,
            port_adr.eq(axi_lite.ar.addr[adr_shift:]),
            NextState("SEND-READ-RESPONSE"),
        )
    )
    fsm.act("SEND-READ-RESPONSE",
        NextValue(last_was_read, 1),
        # As long as we have correct address port.dat_r will be valid.
        port_adr.eq(axi_lite.ar.addr[adr_shift:]),
        axi_lite.r.data.eq(port_dat_r),
        axi_lite.r.resp.eq(RESP_OKAY),
        axi_lite.r.valid.eq(1),
        If(axi_lite.r.ready,
            NextState("START-TRANSACTION")
        )
    )
    fsm.act("SEND-WRITE-RESPONSE",
        NextValue(last_was_read, 0),
        axi_lite.b.valid.eq(1),
        axi_lite.b.resp.eq(RESP_OKAY),
        If(axi_lite.b.ready,
            NextState("START-TRANSACTION")
        )
    )
    return fsm, comb

# AXI-Lite SRAM ------------------------------------------------------------------------------------

class AXILiteSRAM(LiteXModule):
    def __init__(self, mem_or_size, read_only=None, init=None, bus=None, name=None):
        if bus is None:
            bus = AXILiteInterface()
        self.bus = bus

        bus_data_width = len(self.bus.r.data)
        if isinstance(mem_or_size, Memory):
            assert(mem_or_size.width <= bus_data_width)
            self.mem = mem_or_size
        else:
            self.mem = Memory(bus_data_width, mem_or_size//(bus_data_width//8), init=init, name=name)

        if read_only is None:
            if hasattr(self.mem, "bus_read_only"):
                read_only = self.mem.bus_read_only
            else:
                read_only = False

        # # #

        # Create memory port
        port = self.mem.get_port(write_capable=not read_only, we_granularity=8,
            mode=READ_FIRST if read_only else WRITE_FIRST)
        self.specials += self.mem, port

        # Generate write enable signal
        if not read_only:
            self.comb += port.dat_w.eq(self.bus.w.data),
            self.comb += [port.we[i].eq(self.bus.w.valid & self.bus.w.ready & self.bus.w.strb[i])
                for i in range(bus_data_width//8)]

        # Transaction logic
        fsm, comb = axi_lite_to_simple(
            axi_lite   = self.bus,
            port_adr   = port.adr,
            port_dat_r = port.dat_r,
            port_dat_w = port.dat_w if not read_only else None,
            port_we    = port.we if not read_only else None)
        self.fsm = fsm
        self.comb += comb

# AXI-Lite Data-Width Converter --------------------------------------------------------------------

class _AXILiteDownConverterWrite(LiteXModule):
    def __init__(self, master, slave):
        assert isinstance(master, AXILiteInterface) and isinstance(slave, AXILiteInterface)
        dw_from      = len(master.w.data)
        dw_to        = len(slave.w.data)
        ratio        = dw_from//dw_to

        skip         = Signal()
        counter      = Signal(max=ratio)
        aw_ready     = Signal()
        w_ready      = Signal()
        resp         = Signal.like(master.b.resp)

        # # #

        # Data path
        self.comb += [
            slave.aw.addr.eq(master.aw.addr + counter*(dw_to//8)),
            Case(counter, {i: slave.w.data.eq(master.w.data[i*dw_to:]) for i in range(ratio)}),
            Case(counter, {i: slave.w.strb.eq(master.w.strb[i*dw_to//8:]) for i in range(ratio)}),
            master.b.resp.eq(resp),
        ]

        # Control Path
        self.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))
        # Reset the converter state if master breaks a request, we can do that as
        # aw.valid and w.valid are kept high in CONVERT and RESPOND-SLAVE, and
        # acknowledged only when moving to RESPOND-MASTER, and then b.valid is 1.
        self.comb += fsm.reset.eq(~((master.aw.valid | master.w.valid) | master.b.valid))

        fsm.act("IDLE",
            NextValue(counter, 0),
            NextValue(resp, RESP_OKAY),
            If(master.aw.valid & master.w.valid,
                NextState("CONVERT")
            )
        )
        fsm.act("CONVERT",
            skip.eq(slave.w.strb == 0),
            slave.aw.valid.eq(~skip & ~aw_ready),
            slave.w.valid.eq(~skip & ~w_ready),
            If(slave.aw.ready,
                NextValue(aw_ready, 1)
            ),
            If(slave.w.ready,
                NextValue(w_ready, 1)
            ),
            # When skipping, we just increment the counter.
            If(skip,
                NextValue(counter, counter + 1),
                # Corner-case: when the last word is being skipped, we must send the response.
                If(counter == (ratio - 1),
                    master.aw.ready.eq(1),
                    master.w.ready.eq(1),
                    NextState("RESPOND-MASTER")
                )
            # Write current word and wait for write response.
            ).Elif((slave.aw.ready | aw_ready) & (slave.w.ready | w_ready),
                NextState("RESPOND-SLAVE")
            )
        )
        fsm.act("RESPOND-SLAVE",
            NextValue(aw_ready, 0),
            NextValue(w_ready, 0),
            If(slave.b.valid,
                slave.b.ready.eq(1),
                # Errors are sticky, so the first one is always sent.
                If((resp == RESP_OKAY) & (slave.b.resp != RESP_OKAY),
                    NextValue(resp, slave.b.resp)
                ),
                If(counter == (ratio - 1),
                    master.aw.ready.eq(1),
                    master.w.ready.eq(1),
                    NextState("RESPOND-MASTER")
                ).Else(
                    NextValue(counter, counter + 1),
                    NextState("CONVERT")
                )
            )
        )
        fsm.act("RESPOND-MASTER",
            NextValue(aw_ready, 0),
            NextValue(w_ready, 0),
            master.b.valid.eq(1),
            If(master.b.ready,
                NextState("IDLE")
            )
        )

class _AXILiteDownConverterRead(LiteXModule):
    def __init__(self, master, slave):
        assert isinstance(master, AXILiteInterface) and isinstance(slave, AXILiteInterface)
        dw_from      = len(master.r.data)
        dw_to        = len(slave.r.data)
        ratio        = dw_from//dw_to

        skip         = Signal()
        counter      = Signal(max=ratio)
        resp         = Signal.like(master.r.resp)

        # # #

        # Data path
        # Shift the data word
        r_data = Signal(dw_from, reset_less=True)
        self.sync += If(slave.r.ready, r_data.eq(master.r.data))
        self.comb += master.r.data.eq(Cat(r_data[dw_to:], slave.r.data))
        # Connect address, resp
        self.comb += [
            slave.ar.addr.eq(master.ar.addr + counter*(dw_to//8)),
            master.r.resp.eq(resp),
        ]

        # Control Path
        self.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))
        # Reset the converter state if master breaks a request, we can do that as
        # ar.valid is high in CONVERT and RESPOND-SLAVE, and r.valid in RESPOND-MASTER.
        self.comb += fsm.reset.eq(~(master.ar.valid | master.r.valid))

        fsm.act("IDLE",
            NextValue(counter, 0),
            NextValue(resp, RESP_OKAY),
            If(master.ar.valid,
                NextState("CONVERT")
            )
        )
        fsm.act("CONVERT",
            slave.ar.valid.eq(1),
            If(slave.ar.ready,
                NextState("RESPOND-SLAVE")
            )
        )
        fsm.act("RESPOND-SLAVE",
            If(slave.r.valid,
                # Errors are sticky, so the first one is always sent.
                If((resp == RESP_OKAY) & (slave.r.resp != RESP_OKAY),
                    NextValue(resp, slave.r.resp)
                ),
                # On last word acknowledge ar and hold slave.r.valid until we get master.r.ready.
                If(counter == (ratio - 1),
                    master.ar.ready.eq(1),
                    NextState("RESPOND-MASTER")
                # Acknowledge the response and continue conversion.
                ).Else(
                    slave.r.ready.eq(1),
                    NextValue(counter, counter + 1),
                    NextState("CONVERT")
                )
            )
        )
        fsm.act("RESPOND-MASTER",
            master.r.valid.eq(1),
            If(master.r.ready,
                slave.r.ready.eq(1),
                NextState("IDLE")
            )
        )

class AXILiteDownConverter(LiteXModule):
    def __init__(self, master, slave):
        self.write = _AXILiteDownConverterWrite(master, slave)
        self.read  = _AXILiteDownConverterRead(master, slave)

class AXILiteUpConverter(LiteXModule):
    # TODO: we could try joining multiple master accesses into single slave access would require
    # checking if address changes and a way to flush on single access
    def __init__(self, master, slave):
        assert isinstance(master, AXILiteInterface) and isinstance(slave, AXILiteInterface)
        dw_from      = len(master.r.data)
        dw_to        = len(slave.r.data)
        ratio        = dw_to//dw_from
        master_align = log2_int(master.data_width//8)
        slave_align  = log2_int(slave.data_width//8)

        wr_word   = Signal(log2_int(ratio))
        rd_word   = Signal(log2_int(ratio))
        wr_word_r = Signal(log2_int(ratio))
        rd_word_r = Signal(log2_int(ratio))

        # # #

        self.comb += master.connect(slave, omit={"addr", "strb", "data"})

        # Address
        self.comb += [
            slave.aw.addr[slave_align:].eq(master.aw.addr[slave_align:]),
            slave.ar.addr[slave_align:].eq(master.ar.addr[slave_align:]),
        ]

        # Data path
        wr_cases, rd_cases = {}, {}
        for i in range(ratio):
            strb_from = i     * dw_from//8
            strb_to   = (i+1) * dw_from//8
            data_from = i     * dw_from
            data_to   = (i+1) * dw_from
            wr_cases[i] = [
                slave.w.strb[strb_from:strb_to].eq(master.w.strb),
                slave.w.data[data_from:data_to].eq(master.w.data),
            ]
            rd_cases[i] = [
                master.r.data.eq(slave.r.data[data_from:data_to]),
            ]

        # Switch current word based on the last valid master address.
        self.sync += If(master.aw.valid, wr_word_r.eq(wr_word))
        self.sync += If(master.ar.valid, rd_word_r.eq(rd_word))
        self.comb += [
            Case(master.aw.valid, {
                0: wr_word.eq(wr_word_r),
                1: wr_word.eq(master.aw.addr[master_align:slave_align]),
            }),
            Case(master.ar.valid, {
                0: rd_word.eq(rd_word_r),
                1: rd_word.eq(master.ar.addr[master_align:slave_align]),
            }),
        ]

        self.comb += Case(wr_word, wr_cases)
        self.comb += Case(rd_word, rd_cases)

class AXILiteConverter(LiteXModule):
    """AXILite data width converter"""
    def __init__(self, master, slave):
        self.master = master
        self.slave = slave

        # # #

        dw_from = len(master.r.data)
        dw_to   = len(slave.r.data)
        ratio   = dw_from/dw_to

        if ratio > 1:
            self.submodules += AXILiteDownConverter(master, slave)
        elif ratio < 1:
            self.submodules += AXILiteUpConverter(master, slave)
        else:
            self.comb += master.connect(slave)

# AXI-Lite Clock Domain Crossing -------------------------------------------------------------------

class AXILiteClockDomainCrossing(LiteXModule):
    """AXILite Clock Domain Crossing"""
    def __init__(self, master, slave, cd_from="sys", cd_to="sys"):
        # Same Clock Domain, direct connection.
        if cd_from == cd_to:
            self.comb += [
                # Write.
                master.aw.connect(slave.aw),
                master.w.connect(slave.w),
                slave.b.connect(master.b),
                # Read.
                master.ar.connect(slave.ar),
                slave.r.connect(master.r),
            ]
        # Clock Domain Crossing.
        else:
            # Write.
            aw_cdc = stream.ClockDomainCrossing(master.aw.description, cd_from,   cd_to)
            w_cdc  = stream.ClockDomainCrossing(master.w.description,  cd_from,   cd_to)
            b_cdc  = stream.ClockDomainCrossing(master.b.description,    cd_to, cd_from)
            self.submodules += aw_cdc, w_cdc, b_cdc
            self.comb += [
                master.aw.connect(aw_cdc.sink),
                aw_cdc.source.connect(slave.aw),
                master.w.connect(w_cdc.sink),
                w_cdc.source.connect(slave.w),
                slave.b.connect(b_cdc.sink),
                b_cdc.source.connect(master.b),
            ]
            # Read.
            ar_cdc = stream.ClockDomainCrossing(master.ar.description, cd_from,   cd_to)
            r_cdc  = stream.ClockDomainCrossing(master.r.description,    cd_to, cd_from)
            self.submodules += ar_cdc, r_cdc
            self.comb += [
                master.ar.connect(ar_cdc.sink),
                ar_cdc.source.connect(slave.ar),
                slave.r.connect(r_cdc.sink),
                r_cdc.source.connect(master.r),
            ]

# AXI-Lite Timeout ---------------------------------------------------------------------------------

class AXILiteTimeout(LiteXModule):
    """Protect master against slave timeouts (master _has_ to respond correctly)"""
    def __init__(self, master, cycles):
        self.error = Signal()
        wr_error   = Signal()
        rd_error   = Signal()

        # # #

        self.comb += self.error.eq(wr_error | rd_error)

        wr_timer = WaitTimer(cycles)
        rd_timer = WaitTimer(cycles)
        self.submodules += wr_timer, rd_timer

        def channel_fsm(timer, wait_cond, error, response):
            fsm = FSM(reset_state="WAIT")
            fsm.act("WAIT",
                timer.wait.eq(wait_cond),
                # done is updated in `sync`, so we must make sure that `ready` has not been issued
                # by slave during that single cycle, by checking `timer.wait`.
                If(timer.done & timer.wait,
                    error.eq(1),
                    NextState("RESPOND")
                )
            )
            fsm.act("RESPOND", *response)
            return fsm

        self.wr_fsm = channel_fsm(
            timer     = wr_timer,
            wait_cond = (master.aw.valid & ~master.aw.ready) | (master.w.valid & ~master.w.ready),
            error     = wr_error,
            response  = [
                master.aw.ready.eq(master.aw.valid),
                master.w.ready.eq(master.w.valid),
                master.b.valid.eq(~master.aw.valid & ~master.w.valid),
                master.b.resp.eq(RESP_SLVERR),
                If(master.b.valid & master.b.ready,
                    NextState("WAIT")
                )
            ])

        self.rd_fsm = channel_fsm(
            timer     = rd_timer,
            wait_cond = master.ar.valid & ~master.ar.ready,
            error     = rd_error,
            response  = [
                master.ar.ready.eq(master.ar.valid),
                master.r.valid.eq(~master.ar.valid),
                master.r.resp.eq(RESP_SLVERR),
                master.r.data.eq(2**len(master.r.data) - 1),
                If(master.r.valid & master.r.ready,
                    NextState("WAIT")
                )
            ])

# AXI-Lite Interconnect Components -----------------------------------------------------------------

class _AXILiteRequestCounter(LiteXModule):
    def __init__(self, request, response, max_requests=256):
        self.counter = counter = Signal(max=max_requests)
        self.full = full = Signal()
        self.empty = empty = Signal()
        self.stall = stall = Signal()
        self.ready = self.empty

        self.comb += [
            full.eq(counter == max_requests - 1),
            empty.eq(counter == 0),
            stall.eq(request & full),
        ]

        self.sync += [
            If(request & response,
                counter.eq(counter)
            ).Elif(request & ~full,
                counter.eq(counter + 1)
            ).Elif(response & ~empty,
                counter.eq(counter - 1)
            ),
        ]

class AXILiteArbiter(LiteXModule):
    """AXI Lite arbiter

    Arbitrate between master interfaces and connect one to the target. New master will not be
    selected until all requests have been responded to. Arbitration for write and read channels is
    done separately.
    """
    def __init__(self, masters, target):
        self.rr_write = roundrobin.RoundRobin(len(masters), roundrobin.SP_CE)
        self.rr_read  = roundrobin.RoundRobin(len(masters), roundrobin.SP_CE)

        def get_sig(interface, channel, name):
            return getattr(getattr(interface, channel), name)

        # Mux master->slave signals
        for channel, name, direction in target.layout_flat():
            rr = self.rr_write if channel in ["aw", "w", "b"] else self.rr_read
            if direction == DIR_M_TO_S:
                choices = Array(get_sig(m, channel, name) for m in masters)
                self.comb += get_sig(target, channel, name).eq(choices[rr.grant])

        # Connect slave->master signals
        for channel, name, direction in target.layout_flat():
            rr = self.rr_write if channel in ["aw", "w", "b"] else self.rr_read
            if direction == DIR_S_TO_M:
                source = get_sig(target, channel, name)
                for i, m in enumerate(masters):
                    dest = get_sig(m, channel, name)
                    if name in ["valid", "ready"]:
                        self.comb += If(rr.grant == i, dest.eq(source))
                    else:
                        self.comb += dest.eq(source)

        # Allow to change rr.grant only after all requests from a master have been responded to.
        self.wr_lock = wr_lock = _AXILiteRequestCounter(
            request  = target.aw.valid & target.aw.ready,
            response = target.b.valid  & target.b.ready
        )
        self.rd_lock = rd_lock = _AXILiteRequestCounter(
            request  = target.ar.valid & target.ar.ready,
            response = target.r.valid  & target.r.ready
        )

        # Switch to next request only if there are no responses pending.
        self.comb += [
            self.rr_write.ce.eq(~(target.aw.valid | target.w.valid | target.b.valid) & wr_lock.ready),
            self.rr_read.ce.eq(~(target.ar.valid | target.r.valid) & rd_lock.ready),
        ]

        # Connect bus requests to round-robin selectors.
        self.comb += [
            self.rr_write.request.eq(Cat(*[m.aw.valid | m.w.valid | m.b.valid for m in masters])),
            self.rr_read.request.eq(Cat(*[m.ar.valid | m.r.valid for m in masters])),
        ]

class AXILiteDecoder(LiteXModule):
    """AXI Lite decoder

    Decode master access to particular slave based on its decoder function.

    slaves: [(decoder, slave), ...]
        List of slaves with address decoders, where `decoder` is a function:
            decoder(Signal(address_width - log2(data_width//8))) -> Signal(1)
        that returns 1 when the slave is selected and 0 otherwise.
    """
    def __init__(self, master, slaves, register=False):
        # TODO: unused register argument
        addr_shift = log2_int(master.data_width//8)

        channels = {
            "write": {"aw", "w", "b"},
            "read":  {"ar", "r"},
        }
        # Reverse mapping: directions[channel] -> "write"/"read".
        directions = {ch: d for d, chs in channels.items() for ch in chs}

        def new_slave_sel():
            return {"write": Signal(len(slaves)), "read":  Signal(len(slaves))}

        slave_sel_dec = new_slave_sel()
        slave_sel_reg = new_slave_sel()
        slave_sel     = new_slave_sel()

        # We need to hold the slave selected until all responses come back.
        # TODO: we could reuse arbiter counters
        locks = {
            "write": _AXILiteRequestCounter(
                request  = master.aw.valid & master.aw.ready,
                response = master.b.valid & master.b.ready,
            ),
            "read": _AXILiteRequestCounter(
                request  = master.ar.valid & master.ar.ready,
                response = master.r.valid & master.r.ready
            ),
        }
        self.submodules += locks.values()

        def get_sig(interface, channel, name):
            return getattr(getattr(interface, channel), name)

        # # #

        # Decode slave addresses.
        for i, (decoder, bus) in enumerate(slaves):
            self.comb += [
                slave_sel_dec["write"][i].eq(decoder(master.aw.addr[addr_shift:])),
                slave_sel_dec["read"][i].eq(decoder(master.ar.addr[addr_shift:])),
            ]

        # Change the current selection only when we've got all responses.
        for channel in locks.keys():
            self.sync += If(locks[channel].ready, slave_sel_reg[channel].eq(slave_sel_dec[channel]))
        # We have to cut the delaying select.
        for ch, final in slave_sel.items():
            self.comb += [
                If(locks[ch].ready,
                    final.eq(slave_sel_dec[ch])
                ).Else(
                    final.eq(slave_sel_reg[ch])
                )
            ]

        # Connect master->slaves signals except valid/ready.
        for i, (_, slave) in enumerate(slaves):
            for channel, name, direction in master.layout_flat():
                if direction == DIR_M_TO_S:
                    src = get_sig(master, channel, name)
                    dst = get_sig(slave, channel, name)
                    # Mask master control signals depending on slave selection.
                    if name in ["valid", "ready"]:
                        src = src & slave_sel[directions[channel]][i]
                    self.comb += dst.eq(src)

        # Connect slave->master signals masking not selected slaves.
        for channel, name, direction in master.layout_flat():
            if direction == DIR_S_TO_M:
                dst = get_sig(master, channel, name)
                masked = []
                for i, (_, slave) in enumerate(slaves):
                    src = get_sig(slave, channel, name)
                    # Mask depending on channel.
                    mask = Replicate(slave_sel[directions[channel]][i], len(dst))
                    masked.append(src & mask)
                self.comb += dst.eq(reduce(or_, masked))

# AXI-Lite Interconnect ----------------------------------------------------------------------------

def get_check_parameters(ports):
    # FIXME: Add adr_width check.

    # Data-Width.
    data_width = ports[0].data_width
    if len(ports) > 1:
        for port in ports[1:]:
            assert port.data_width == data_width

    return data_width

class AXILiteInterconnectPointToPoint(LiteXModule):
    """AXI Lite point to point interconnect"""
    def __init__(self, master, slave):
        self.comb += master.connect(slave)

class AXILiteInterconnectShared(LiteXModule):
    """AXI Lite shared interconnect"""
    def __init__(self, masters, slaves, register=False, timeout_cycles=1e6):
        data_width = get_check_parameters(ports=masters + [s for _, s in slaves])
        shared = AXILiteInterface(data_width=data_width)
        self.arbiter = AXILiteArbiter(masters, shared)
        self.decoder = AXILiteDecoder(shared, slaves)
        if timeout_cycles is not None:
            self.timeout = AXILiteTimeout(shared, timeout_cycles)

class AXILiteCrossbar(LiteXModule):
    """AXI Lite crossbar

    MxN crossbar for M masters and N slaves.
    """
    def __init__(self, masters, slaves, register=False, timeout_cycles=1e6):
        data_width = get_check_parameters(ports=masters + [s for _, s in slaves])
        matches, busses = zip(*slaves)
        access_m_s = [[AXILiteInterface(data_width=data_width) for j in slaves] for i in masters]  # a[master][slave]
        access_s_m = list(zip(*access_m_s))  # a[slave][master]
        # Decode each master into its access row.
        for slaves, master in zip(access_m_s, masters):
            slaves = list(zip(matches, slaves))
            self.submodules += AXILiteDecoder(master, slaves, register)
        # Arbitrate each access column onto its slave.
        for masters, bus in zip(access_s_m, busses):
            self.submodules += AXILiteArbiter(masters, bus)
