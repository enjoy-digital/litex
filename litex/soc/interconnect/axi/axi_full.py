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
from litex.soc.interconnect.axi.axi_stream import AXIStreamInterface

# AXI Definition -----------------------------------------------------------------------------------

def ax_description(address_width, version="axi4"):
    len_width  = {"axi3":4, "axi4":8}[version]
    size_width = {"axi3":4, "axi4":3}[version]
    lock_width = {"axi3":2, "axi4":1}[version]
    # * present for interconnect with others cores but not used by LiteX.
    return [
        ("addr",   address_width),   # Address Width.
        ("burst",  2),               # Burst type.
        ("len",    len_width),       # Number of data (-1) transfers (up to 16 (AXI3) or 256 (AXI4)).
        ("size",   size_width),      # Number of bytes (-1) of each data transfer (up to 1024-bit).
        ("lock",   lock_width),      # *
        ("prot",   3),               # *
        ("cache",  4),               # *
        ("qos",    4),               # *
        ("region", 4),               # *
    ]

def w_description(data_width):
    return [
        ("data", data_width),
        ("strb", data_width//8),
    ]

def b_description():
    return [("resp", 2)]

def r_description(data_width):
    return [
        ("resp", 2),
        ("data", data_width),
    ]

class AXIInterface:
    def __init__(self, data_width=32, address_width=32, id_width=1, version="axi4", clock_domain="sys",
        name          = None,
        bursting      = False,
        aw_user_width = 0,
        w_user_width  = 0,
        b_user_width  = 0,
        ar_user_width = 0,
        r_user_width  = 0
    ):
        # Parameters checks.
        # ------------------
        assert data_width in [8, 16, 32, 64, 128, 256, 512, 1024]
        assert version    in ["axi3", "axi4"]

        # Parameters.
        # -----------
        self.data_width    = data_width
        self.address_width = address_width
        self.id_width      = id_width
        self.version       = version
        self.clock_domain  = clock_domain
        self.bursting      = bursting # FIXME: Use or add check.

        # Write Channels.
        # ---------------
        self.aw = AXIStreamInterface(name=name,
            layout     = ax_description(address_width=address_width, version=version),
            id_width   = id_width,
            user_width = aw_user_width
        )
        self.w = AXIStreamInterface(name=name,
            layout     = w_description(data_width),
            id_width   = {"axi4":0,"axi3":id_width}[version], # No WID on AXI4.
            user_width = w_user_width
        )
        self.b = AXIStreamInterface(name=name,
            layout     = b_description(),
            id_width   = id_width,
            user_width = b_user_width
        )

        # Read Channels.
        # --------------
        self.ar = AXIStreamInterface(name=name,
            layout     = ax_description(address_width=address_width, version=version),
            id_width   = id_width,
            user_width = ar_user_width
        )
        self.r = AXIStreamInterface(name=name,
            layout     = r_description(data_width),
            id_width   = id_width,
            user_width = r_user_width
        )

    def connect_to_pads(self, pads, mode="master"):
        return connect_to_pads(self, pads, mode, axi_full=True)

    def get_ios(self, bus_name="wb"):
        subsignals = []
        for channel in ["aw", "w", "b", "ar", "r"]:
            # Control Signals.
            for name in ["valid", "ready"] + (["last"] if channel in ["w", "r"] else []):
                subsignals.append(Subsignal(channel + name, Pins(1)))

            # Payload/Params Signals.
            channel_layout = (getattr(self, channel).description.payload_layout +
                              getattr(self, channel).description.param_layout)
            for name, width in channel_layout:
                if (name == "dest"):
                    continue # No DEST.
                if (channel == "w") and (name == "id") and (self.version == "axi4"):
                    continue # No WID on AXI4.
                subsignals.append(Subsignal(channel + name, Pins(width)))
        ios = [(bus_name , 0) + tuple(subsignals)]
        return ios

    def connect(self, slave, **kwargs):
        return connect_axi(self, slave, **kwargs)

    def layout_flat(self):
        return list(axi_layout_flat(self))

# AXI Bursts to Beats ------------------------------------------------------------------------------

class AXIBurst2Beat(LiteXModule):
    def __init__(self, ax_burst, ax_beat, capabilities={BURST_FIXED, BURST_INCR, BURST_WRAP}):
        assert BURST_FIXED in capabilities

        # # #

        beat_count  = Signal(8)
        beat_size   = Signal(8 + 4)
        beat_offset = Signal((8 + 4 + 1, True))
        beat_wrap   = Signal(8 + 4)

        # Compute parameters
        self.comb += beat_size.eq(1 << ax_burst.size)
        self.comb += beat_wrap.eq(ax_burst.len << ax_burst.size)

        # Combinatorial logic
        self.comb += [
            ax_beat.valid.eq(ax_burst.valid | ~ax_beat.first),
            ax_beat.first.eq(beat_count == 0),
            ax_beat.last.eq(beat_count == ax_burst.len),
            ax_beat.addr.eq(ax_burst.addr + beat_offset),
            ax_beat.id.eq(ax_burst.id),
            If(ax_beat.ready,
                If(ax_beat.last,
                    ax_burst.ready.eq(1)
                )
            )
        ]

        # Synchronous logic
        self.sync += [
            If(ax_beat.valid & ax_beat.ready,
                If(ax_beat.last,
                    beat_count.eq(0),
                    beat_offset.eq(0)
                ).Else(
                    beat_count.eq(beat_count + 1),
                    If(((ax_burst.burst == BURST_INCR) & (BURST_INCR in capabilities)) |
                       ((ax_burst.burst == BURST_WRAP) & (BURST_WRAP in capabilities)),
                        beat_offset.eq(beat_offset + beat_size)
                    )
                ),
                If((ax_burst.burst == BURST_WRAP) & (BURST_WRAP in capabilities),
                    If((ax_beat.addr & beat_wrap) == beat_wrap,
                        beat_offset.eq(beat_offset - beat_wrap)
                    )
                )
            )
        ]

# AXI Data-Width Converter -------------------------------------------------------------------------

class AXIUpConverter(LiteXModule):
    def __init__(self, axi_from, axi_to):
        dw_from  = len(axi_from.r.data)
        dw_to    = len(axi_to.r.data)
        ratio    = int(dw_to//dw_from)
        assert dw_from*ratio == dw_to

        # # #

        # Note: Assuming size of "axi_from" burst >= "axi_to" data_width.

        # Write path -------------------------------------------------------------------------------

        # AW Channel.
        self.comb += [
            axi_from.aw.connect(axi_to.aw, omit={"len", "size"}),
            axi_to.aw.len.eq( axi_from.aw.len >> log2_int(ratio)),
            axi_to.aw.size.eq(axi_from.aw.size + log2_int(ratio)),
        ]

        # W Channel.
        w_converter = stream.StrideConverter(
            description_from = [("data", dw_from), ("strb", dw_from//8)],
            description_to   = [("data",   dw_to), ("strb",   dw_to//8)],
        )
        self.submodules += w_converter
        self.comb += axi_from.w.connect(w_converter.sink, omit={"id", "dest", "user"})
        self.comb += w_converter.source.connect(axi_to.w)
        self.comb += axi_to.w.id.eq(axi_from.w.id)
        self.comb += axi_to.w.dest.eq(axi_from.w.dest)
        self.comb += axi_to.w.user.eq(axi_from.w.user)

        # B Channel.
        self.comb += axi_to.b.connect(axi_from.b)

        # Read path --------------------------------------------------------------------------------

        # AR Channel.
        self.comb += [
            axi_from.ar.connect(axi_to.ar, omit={"len", "size"}),
            axi_to.ar.len.eq( axi_from.ar.len >> log2_int(ratio)),
            axi_to.ar.size.eq(axi_from.ar.size + log2_int(ratio)),
        ]

        # R Channel.
        r_converter = stream.StrideConverter(
            description_from = [("data",   dw_to)],
            description_to   = [("data", dw_from)],
        )
        self.submodules += r_converter
        self.comb += axi_to.r.connect(r_converter.sink, omit={"id", "dest", "user", "resp"})
        self.comb += r_converter.source.connect(axi_from.r)
        self.comb += axi_from.r.resp.eq(axi_to.r.resp)
        self.comb += axi_from.r.id.eq(axi_to.r.id)
        self.comb += axi_from.r.user.eq(axi_to.r.user)
        self.comb += axi_from.r.dest.eq(axi_to.r.dest)

class AXIDownConverter(LiteXModule):
    def __init__(self, axi_from, axi_to):
        dw_from  = len(axi_from.r.data)
        dw_to    = len(axi_to.r.data)
        ratio    = int(dw_from//dw_to)
        assert dw_from == dw_to*ratio

        # # #

        # Helpers ----------------------------------------------------------------------------------


        # Addr Conversion: Clear MSBs to align accesses.
        def convert_addr(ax_from, ax_to):
            return [
                ax_to.addr.eq(ax_from.addr),
                ax_to.addr[:log2_int(dw_from//8)].eq(0)
            ]

        # Burst Conversion: Convert FIXED burst to Incr.
        def convert_burst(ax_from, ax_to):
            return Case(ax_from.burst, {
                BURST_FIXED     : ax_to.burst.eq(BURST_INCR),
                BURST_INCR      : ax_to.burst.eq(BURST_INCR),
                BURST_WRAP      : ax_to.burst.eq(BURST_WRAP),
                BURST_RESERVED  : ax_to.burst.eq(BURST_RESERVED),
            })

        # Len Conversion: X ratio.
        def convert_len(ax_from, ax_to):
            return ax_to.len.eq(((ax_from.len + 1) << log2_int(ratio)) - 1)

        # Size Conversion: max(ax_from.size, log2_int(dw_to//8)).
        def convert_size(ax_from, ax_to):
            return If(ax_from.size <= log2_int(dw_to//8),
                ax_to.size.eq(ax_from.size)
            ).Else(
                ax_to.size.eq(log2_int(dw_to//8))
            )

        # Write path -------------------------------------------------------------------------------

        # AW Channel.
        self.comb += [
            axi_from.aw.connect(axi_to.aw, omit={"addr", "len", "size", "burst"}),
            *convert_addr( axi_from.aw, axi_to.aw),
            convert_len(   axi_from.aw, axi_to.aw),
            convert_size(  axi_from.aw, axi_to.aw),
            convert_burst( axi_from.aw, axi_to.aw),
        ]

        # W Channel.
        w_converter = stream.StrideConverter(
            description_from = [("data", dw_from), ("strb", dw_from//8)],
            description_to   = [("data",   dw_to), ("strb",   dw_to//8)],
        )
        self.submodules += w_converter
        self.comb += axi_from.w.connect(w_converter.sink, omit={"id", "dest", "user"})
        self.comb += w_converter.source.connect(axi_to.w)
        # ID/Dest/User (self.comb since no latency in StrideConverter).
        self.comb += axi_to.w.id.eq(axi_from.w.id)
        self.comb += axi_to.w.dest.eq(axi_from.w.dest)
        self.comb += axi_to.w.user.eq(axi_from.w.user)

        # B Channel.
        self.comb += axi_to.b.connect(axi_from.b)

        # Read path --------------------------------------------------------------------------------

        # AR Channel.
        self.comb += [
            axi_from.ar.connect(axi_to.ar, omit={"addr", "len", "size", "burst"}),
            *convert_addr( axi_from.ar, axi_to.ar),
            convert_len(   axi_from.ar, axi_to.ar),
            convert_size(  axi_from.ar, axi_to.ar),
            convert_burst( axi_from.ar, axi_to.ar),
        ]

        # R Channel.
        r_converter = stream.StrideConverter(
            description_from = [("data",   dw_to)],
            description_to   = [("data", dw_from)],
        )
        self.submodules += r_converter
        self.comb += axi_to.r.connect(r_converter.sink, omit={"id", "dest", "user", "resp"})
        self.comb += r_converter.source.connect(axi_from.r)
        # ID/Dest/User (self.sync since +1 cycle latency in StrideConverter).
        self.sync += axi_from.r.resp.eq(axi_to.r.resp)
        self.sync += axi_from.r.user.eq(axi_to.r.user)
        self.sync += axi_from.r.dest.eq(axi_to.r.dest)
        self.sync += axi_from.r.id.eq(axi_to.r.id)

class AXIConverter(LiteXModule):
    """AXI data width converter"""
    def __init__(self, master, slave):
        self.master = master
        self.slave  = slave

        # # #

        dw_from = len(master.r.data)
        dw_to   = len(slave.r.data)
        ratio   = dw_from/dw_to

        if ratio > 1:
            self.submodules += AXIDownConverter(master, slave)
        elif ratio < 1:
            self.submodules += AXIUpConverter(master, slave)
        else:
            self.comb += master.connect(slave)

# AXI Timeout --------------------------------------------------------------------------------------

class AXITimeout(LiteXModule):
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
                master.r.last.eq(1),
                master.r.resp.eq(RESP_SLVERR),
                master.r.data.eq(2**len(master.r.data) - 1),
                If(master.r.valid & master.r.ready,
                    NextState("WAIT")
                )
            ])

# AXI Interconnect Components ----------------------------------------------------------------------

class _AXIRequestCounter(LiteXModule):
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

class AXIArbiter(LiteXModule):
    """AXI arbiter

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
        self.wr_lock = wr_lock = _AXIRequestCounter(
            request  = target.aw.valid & target.aw.ready,
            response = target.b.valid  & target.b.ready
        )
        self.rd_lock = rd_lock = _AXIRequestCounter(
            request  = target.ar.valid & target.ar.ready,
            response = target.r.valid  & target.r.ready & target.r.last
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

class AXIDecoder(LiteXModule):
    """AXI decoder

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
            "write": _AXIRequestCounter(
                request  = master.aw.valid & master.aw.ready,
                response = master.b.valid  & master.b.ready
            ),
            "read": _AXIRequestCounter(
                request  = master.ar.valid & master.ar.ready,
                response = master.r.valid  & master.r.ready & master.r.last,
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

# AXI Interconnect ---------------------------------------------------------------------------------

def get_check_parameters(ports):
    # FIXME: Add adr_width check.

    # Data-Width.
    data_width = ports[0].data_width
    if len(ports) > 1:
        for port in ports[1:]:
            assert port.data_width == data_width

    return data_width

class AXIInterconnectPointToPoint(LiteXModule):
    """AXI point to point interconnect"""
    def __init__(self, master, slave):
        self.comb += master.connect(slave)

class AXIInterconnectShared(LiteXModule):
    """AXI shared interconnect"""
    def __init__(self, masters, slaves, register=False, timeout_cycles=1e6):
        data_width = get_check_parameters(ports=masters + [s for _, s in slaves])
        shared = AXIInterface(data_width=data_width)
        self.arbiter = AXIArbiter(masters, shared)
        self.decoder = AXIDecoder(shared, slaves)
        if timeout_cycles is not None:
            self.timeout = AXITimeout(shared, timeout_cycles)

class AXICrossbar(LiteXModule):
    """AXI crossbar

    MxN crossbar for M masters and N slaves.
    """
    def __init__(self, masters, slaves, register=False, timeout_cycles=1e6):
        data_width = get_check_parameters(ports=masters + [s for _, s in slaves])
        matches, busses = zip(*slaves)
        access_m_s = [[AXIInterface(data_width=data_width) for j in slaves] for i in masters]  # a[master][slave]
        access_s_m = list(zip(*access_m_s))  # a[slave][master]
        # Decode each master into its access row.
        for slaves, master in zip(access_m_s, masters):
            slaves = list(zip(matches, slaves))
            self.submodules += AXIDecoder(master, slaves, register)
        # Arbitrate each access column onto its slave.
        for masters, bus in zip(access_s_m, busses):
            self.submodules += AXIArbiter(masters, bus)
