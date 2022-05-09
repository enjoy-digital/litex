#
# This file is part of LiteX.
#
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2018 Tim 'mithro' Ansell <me@mith.ro>
# Copytight (c) 2022 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""Wishbone Classic support for LiteX (Standard HandShaking/Synchronous Feedback)"""

from math import log2

from functools import reduce
from operator import or_

from migen import *
from migen.genlib import roundrobin
from migen.genlib.record import *
from migen.genlib.misc import split, displacer, chooser, WaitTimer

from litex.build.generic_platform import *

from litex.soc.interconnect import csr, csr_bus

# Wishbone Definition ------------------------------------------------------------------------------

_layout = [
    ("adr",    "adr_width", DIR_M_TO_S),
    ("dat_w", "data_width", DIR_M_TO_S),
    ("dat_r", "data_width", DIR_S_TO_M),
    ("sel",    "sel_width", DIR_M_TO_S),
    ("cyc",              1, DIR_M_TO_S),
    ("stb",              1, DIR_M_TO_S),
    ("ack",              1, DIR_S_TO_M),
    ("we",               1, DIR_M_TO_S),
    ("cti",              3, DIR_M_TO_S),
    ("bte",              2, DIR_M_TO_S),
    ("err",              1, DIR_S_TO_M)
]

CTI_BURST_NONE         = 0b000
CTI_BURST_CONSTANT     = 0b001
CTI_BURST_INCREMENTING = 0b010
CTI_BURST_END          = 0b111


class Interface(Record):
    def __init__(self, data_width=32, adr_width=30, bursting=False):
        self.data_width = data_width
        self.adr_width  = adr_width
        self.bursting   = bursting
        Record.__init__(self, set_layout_parameters(_layout,
            adr_width  = adr_width,
            data_width = data_width,
            sel_width  = data_width//8))
        self.adr.reset_less   = True
        self.dat_w.reset_less = True
        self.dat_r.reset_less = True
        self.sel.reset_less   = True

    @staticmethod
    def like(other):
        return Interface(len(other.dat_w))

    def _do_transaction(self):
        yield self.cyc.eq(1)
        yield self.stb.eq(1)
        yield
        while not (yield self.ack):
            yield
        yield self.cyc.eq(0)
        yield self.stb.eq(0)

    def write(self, adr, dat, sel=None, cti=None, bte=None):
        if sel is None:
            sel = 2**len(self.sel) - 1
        yield self.adr.eq(adr)
        yield self.dat_w.eq(dat)
        yield self.sel.eq(sel)
        if cti is not None:
            yield self.cti.eq(cti)
        if bte is not None:
            yield self.bte.eq(bte)
        yield self.we.eq(1)
        yield from self._do_transaction()

    def read(self, adr, cti=None, bte=None):
        yield self.adr.eq(adr)
        yield self.we.eq(0)
        if cti is not None:
            yield self.cti.eq(cti)
        if bte is not None:
            yield self.bte.eq(bte)
        yield from self._do_transaction()
        return (yield self.dat_r)

    def get_ios(self, bus_name="wb"):
        subsignals = []
        for name, width, direction in self.layout:
            subsignals.append(Subsignal(name, Pins(width)))
        ios = [(bus_name , 0) + tuple(subsignals)]
        return ios

    def connect_to_pads(self, pads, mode="master"):
        assert mode in ["slave", "master"]
        r = []
        for name, width, direction in self.layout:
            sig  = getattr(self, name)
            pad  = getattr(pads, name)
            if mode == "master":
                if direction == DIR_M_TO_S:
                    r.append(pad.eq(sig))
                else:
                    r.append(sig.eq(pad))
            else:
                if direction == DIR_S_TO_M:
                    r.append(pad.eq(sig))
                else:
                    r.append(sig.eq(pad))
        return r

# Wishbone Timeout ---------------------------------------------------------------------------------

class Timeout(Module):
    def __init__(self, master, cycles):
        self.error = Signal()

        # # #

        timer = WaitTimer(int(cycles))
        self.submodules += timer
        self.comb += [
            timer.wait.eq(master.stb & master.cyc & ~master.ack),
            If(timer.done,
                master.dat_r.eq((2**len(master.dat_w))-1),
                master.ack.eq(1),
                self.error.eq(1)
            )
        ]

# Wishbone Interconnect ----------------------------------------------------------------------------

class InterconnectPointToPoint(Module):
    def __init__(self, master, slave):
        self.comb += master.connect(slave)


class Arbiter(Module):
    def __init__(self, masters, target):
        self.submodules.rr = roundrobin.RoundRobin(len(masters))

        # mux master->slave signals
        for name, size, direction in _layout:
            if direction == DIR_M_TO_S:
                choices = Array(getattr(m, name) for m in masters)
                self.comb += getattr(target, name).eq(choices[self.rr.grant])

        # connect slave->master signals
        for name, size, direction in _layout:
            if direction == DIR_S_TO_M:
                source = getattr(target, name)
                for i, m in enumerate(masters):
                    dest = getattr(m, name)
                    if name == "ack" or name == "err":
                        self.comb += dest.eq(source & (self.rr.grant == i))
                    else:
                        self.comb += dest.eq(source)

        # connect bus requests to round-robin selector
        reqs = [m.cyc for m in masters]
        self.comb += self.rr.request.eq(Cat(*reqs))


class Decoder(Module):
    # slaves is a list of pairs:
    # 0) function that takes the address signal and returns a FHDL expression
    #    that evaluates to 1 when the slave is selected and 0 otherwise.
    # 1) wishbone.Slave reference.
    # register adds flip-flops after the address comparators. Improves timing,
    # but breaks Wishbone combinatorial feedback.
    def __init__(self, master, slaves, register=False):
        ns = len(slaves)
        slave_sel = Signal(ns)
        slave_sel_r = Signal(ns)

        # decode slave addresses
        self.comb += [slave_sel[i].eq(fun(master.adr))
            for i, (fun, bus) in enumerate(slaves)]
        if register:
            self.sync += slave_sel_r.eq(slave_sel)
        else:
            self.comb += slave_sel_r.eq(slave_sel)

        # connect master->slaves signals except cyc
        for slave in slaves:
            for name, size, direction in _layout:
                if direction == DIR_M_TO_S and name != "cyc":
                    self.comb += getattr(slave[1], name).eq(getattr(master, name))

        # combine cyc with slave selection signals
        self.comb += [slave[1].cyc.eq(master.cyc & slave_sel[i])
            for i, slave in enumerate(slaves)]

        # generate master ack (resp. err) by ORing all slave acks (resp. errs)
        self.comb += [
            master.ack.eq(reduce(or_, [slave[1].ack for slave in slaves])),
            master.err.eq(reduce(or_, [slave[1].err for slave in slaves]))
        ]

        # mux (1-hot) slave data return
        masked = [Replicate(slave_sel_r[i], len(master.dat_r)) & slaves[i][1].dat_r for i in range(ns)]
        self.comb += master.dat_r.eq(reduce(or_, masked))


class InterconnectShared(Module):
    def __init__(self, masters, slaves, register=False, timeout_cycles=1e6):
        shared = Interface(data_width=masters[0].data_width)
        self.submodules.arbiter = Arbiter(masters, shared)
        self.submodules.decoder = Decoder(shared, slaves, register)
        if timeout_cycles is not None:
            self.submodules.timeout = Timeout(shared, timeout_cycles)


class Crossbar(Module):
    def __init__(self, masters, slaves, register=False):
        matches, busses = zip(*slaves)
        access = [[Interface() for j in slaves] for i in masters]
        # decode each master into its access row
        for row, master in zip(access, masters):
            row = list(zip(matches, row))
            self.submodules += Decoder(master, row, register)
        # arbitrate each access column onto its slave
        for column, bus in zip(zip(*access), busses):
            self.submodules += Arbiter(column, bus)

# Wishbone Data Width Converter --------------------------------------------------------------------

class DownConverter(Module):
    """DownConverter

    This module splits Wishbone accesses from a master interface to a smaller slave interface.

    Writes:
        Writes from master are splitted N writes to the slave. Access is acked when the last
        access is acked by the slave.

    Reads:
        Read from master are splitted in N reads to the the slave. Read datas from
        the slave are cached before being presented concatenated on the last access.

    """
    def __init__(self, master, slave):
        dw_from = len(master.dat_w)
        dw_to   = len(slave.dat_w)
        ratio   = dw_from//dw_to

        # # #

        skip    = Signal()
        counter = Signal(max=ratio)

        # Control Path
        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.submodules.fsm = fsm
        self.comb += fsm.reset.eq(~master.cyc)
        fsm.act("IDLE",
            NextValue(counter, 0),
            If(master.stb & master.cyc,
                NextState("CONVERT"),
            )
        )
        fsm.act("CONVERT",
            slave.adr.eq(Cat(counter, master.adr)),
            Case(counter, {i: slave.sel.eq(master.sel[i*dw_to//8:]) for i in range(ratio)}),
            If(master.stb & master.cyc,
                skip.eq(slave.sel == 0),
                slave.we.eq(master.we),
                slave.cyc.eq(~skip),
                slave.stb.eq(~skip),
                If(slave.ack | skip,
                    NextValue(counter, counter + 1),
                    If(counter == (ratio - 1),
                        master.ack.eq(1),
                        NextState("IDLE")
                    )
                )
            )
        )

        # Write Datapath
        self.comb += Case(counter, {i: slave.dat_w.eq(master.dat_w[i*dw_to:]) for i in range(ratio)})

        # Read Datapath
        dat_r = Signal(dw_from, reset_less=True)
        self.comb += master.dat_r.eq(Cat(dat_r[dw_to:], slave.dat_r))
        self.sync += If(slave.ack | skip, dat_r.eq(master.dat_r))

class UpConverter(Module):
    """UpConverter"""
    def __init__(self, master, slave):
        dw_from = len(master.dat_w)
        dw_to   = len(slave.dat_w)
        ratio   = dw_to//dw_from

        # # #

        self.comb += master.connect(slave, omit={"adr", "sel", "dat_w", "dat_r"})
        cases = {}
        for i in range(ratio):
            cases[i] = [
                slave.adr.eq(master.adr[int(log2(ratio)):]),
                slave.sel[i*dw_from//8:(i+1)*dw_from//8].eq(master.sel),
                slave.dat_w[i*dw_from:(i+1)*dw_from].eq(master.dat_w),
                master.dat_r.eq(slave.dat_r[i*dw_from:(i+1)*dw_from]),
        ]
        self.comb += Case(master.adr[:int(log2(ratio))], cases)

class Converter(Module):
    """Converter

    This module is a wrapper for DownConverter and UpConverter.
    It should preferably be used rather than direct instantiations
    of specific converters.
    """
    def __init__(self, master, slave):
        self.master = master
        self.slave = slave

        # # #

        dw_from = len(master.dat_r)
        dw_to = len(slave.dat_r)
        if dw_from > dw_to:
            downconverter = DownConverter(master, slave)
            self.submodules += downconverter
        elif dw_from < dw_to:
            upconverter = UpConverter(master, slave)
            self.submodules += upconverter
        else:
            self.comb += master.connect(slave)

# Wishbone SRAM ------------------------------------------------------------------------------------

class SRAM(Module):
    def __init__(self, mem_or_size, read_only=None, init=None, bus=None, name=None):
        if bus is None:
            bus = Interface()
        self.bus = bus
        bus_data_width = len(self.bus.dat_r)
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

        adr_burst = Signal()

        # Burst support.
        # --------------

        if self.bus.bursting:
            adr_wrap_mask = Array((0b0000, 0b0011, 0b0111, 0b1111))
            adr_wrap_max  = adr_wrap_mask[-1].bit_length()

            adr_burst_wrap = Signal()
            adr_latched    = Signal()

            adr_counter        = Signal(len(self.bus.adr))
            adr_counter_base   = Signal(len(self.bus.adr))
            adr_counter_offset = Signal(adr_wrap_max)
            adr_offset_lsb     = Signal(adr_wrap_max)
            adr_offset_msb     = Signal(len(self.bus.adr))

            adr_next = Signal(len(self.bus.adr))

            # Only Incrementing Burts are supported.
            self.comb += [
                Case(self.bus.cti, {
                    # incrementing address burst cycle
                    CTI_BURST_INCREMENTING: adr_burst.eq(1),
                    # end current burst cycle
                    CTI_BURST_END: adr_burst.eq(0),
                    # unsupported burst cycle
                    "default": adr_burst.eq(0)
                }),
                adr_burst_wrap.eq(self.bus.bte[0] | self.bus.bte[1]),
                adr_counter_base.eq(
                    Cat(self.bus.adr & ~adr_wrap_mask[self.bus.bte],
                       self.bus.adr[adr_wrap_max:]
                    )
                )
            ]

            # Latch initial address (without wrapping bits and wrap offset).
            self.sync += [
                If(self.bus.cyc & self.bus.stb & adr_burst,
                    adr_latched.eq(1),
                    # Latch initial address, then increment it every clock cycle
                    If(adr_latched,
                        adr_counter.eq(adr_counter + 1)
                    ).Else(
                        adr_counter_offset.eq(self.bus.adr & adr_wrap_mask[self.bus.bte]),
                        adr_counter.eq(adr_counter_base +
                            Cat(~self.bus.we, Replicate(0, len(adr_counter)-1))
                        )
                    ),
                    If(self.bus.cti == CTI_BURST_END,
                        adr_latched.eq(0),
                        adr_counter.eq(0),
                        adr_counter_offset.eq(0)
                    )
                ).Else(
                    adr_latched.eq(0),
                    adr_counter.eq(0),
                    adr_counter_offset.eq(0)
                ),
            ]

            # Next Address = counter value without wrapped bits + wrapped counter bits with offset.
            self.comb += [
                adr_offset_lsb.eq((adr_counter + adr_counter_offset) & adr_wrap_mask[self.bus.bte]),
                adr_offset_msb.eq(adr_counter & ~adr_wrap_mask[self.bus.bte]),
                adr_next.eq(adr_offset_msb + adr_offset_lsb)
            ]

        # # #

        # Memory.
        # -------
        port = self.mem.get_port(write_capable=not read_only, we_granularity=8,
            mode=READ_FIRST if read_only else WRITE_FIRST)
        self.specials += self.mem, port
        # Generate write enable signal
        if not read_only:
            self.comb += [port.we[i].eq(self.bus.cyc & self.bus.stb & self.bus.we & self.bus.sel[i])
                for i in range(bus_data_width//8)]
        # Address and data
        self.comb += port.adr.eq(self.bus.adr[:len(port.adr)])
        if self.bus.bursting:
            self.comb += If(adr_burst & adr_latched,
                port.adr.eq(adr_next[:len(port.adr)]),
            )
        self.comb += [
            self.bus.dat_r.eq(port.dat_r)
        ]
        if not read_only:
            self.comb += port.dat_w.eq(self.bus.dat_w),

        # Generate Ack.
        self.sync += [
            self.bus.ack.eq(0),
            If(self.bus.cyc & self.bus.stb & (~self.bus.ack | adr_burst), self.bus.ack.eq(1))
        ]

# Wishbone To CSR ----------------------------------------------------------------------------------

class Wishbone2CSR(Module):
    def __init__(self, bus_wishbone=None, bus_csr=None, register=True):
        self.csr = bus_csr
        if self.csr is None:
            # If no CSR bus provided, create it with default parameters.
            self.csr = csr_bus.Interface()
        self.wishbone = bus_wishbone
        if self.wishbone is None:
            # If no Wishbone bus provided, create it with default parameters.
            self.wishbone = Interface()

        # # #

        if register:
            fsm = FSM(reset_state="IDLE")
            self.submodules += fsm
            fsm.act("IDLE",
                NextValue(self.csr.dat_w, self.wishbone.dat_w),
                If(self.wishbone.cyc & self.wishbone.stb,
                    NextValue(self.csr.adr, self.wishbone.adr),
                    NextValue(self.csr.we, self.wishbone.we & (self.wishbone.sel != 0)),
                    NextState("WRITE-READ")
                )
            )
            fsm.act("WRITE-READ",
                NextValue(self.csr.adr, 0),
                NextValue(self.csr.we, 0),
                NextState("ACK")
            )
            fsm.act("ACK",
                self.wishbone.ack.eq(1),
                self.wishbone.dat_r.eq(self.csr.dat_r),
                NextState("IDLE")
            )
        else:
            fsm = FSM(reset_state="WRITE-READ")
            self.submodules += fsm
            fsm.act("WRITE-READ",
                self.csr.dat_w.eq(self.wishbone.dat_w),
                If(self.wishbone.cyc & self.wishbone.stb,
                    self.csr.adr.eq(self.wishbone.adr),
                    self.csr.we.eq(self.wishbone.we & (self.wishbone.sel != 0)),
                    NextState("ACK")
                )
            )
            fsm.act("ACK",
                self.wishbone.ack.eq(1),
                self.wishbone.dat_r.eq(self.csr.dat_r),
                NextState("WRITE-READ")
            )

# Wishbone Cache -----------------------------------------------------------------------------------

class Cache(Module):
    """Cache

    This module is a write-back wishbone cache that can be used as a L2 cache.
    Cachesize (in 32-bit words) is the size of the data store and must be a power of 2
    """
    def __init__(self, cachesize, master, slave, reverse=True):
        self.master = master
        self.slave = slave

        # # #

        dw_from = len(master.dat_r)
        dw_to = len(slave.dat_r)
        if dw_to > dw_from and (dw_to % dw_from) != 0:
            raise ValueError("Slave data width must be a multiple of {dw}".format(dw=dw_from))
        if dw_to < dw_from and (dw_from % dw_to) != 0:
            raise ValueError("Master data width must be a multiple of {dw}".format(dw=dw_to))

        # Split address:
        # TAG | LINE NUMBER | LINE OFFSET
        offsetbits = log2_int(max(dw_to//dw_from, 1))
        addressbits = len(slave.adr) + offsetbits
        linebits = log2_int(cachesize) - offsetbits
        tagbits = addressbits - linebits
        wordbits = log2_int(max(dw_from//dw_to, 1))
        adr_offset, adr_line, adr_tag = split(master.adr, offsetbits, linebits, tagbits)
        word = Signal(wordbits) if wordbits else None

        # Data memory
        data_mem = Memory(dw_to*2**wordbits, 2**linebits)
        data_port = data_mem.get_port(write_capable=True, we_granularity=8)
        self.specials += data_mem, data_port

        write_from_slave = Signal()
        if adr_offset is None:
            adr_offset_r = None
        else:
            adr_offset_r = Signal(offsetbits, reset_less=True)
            self.sync += adr_offset_r.eq(adr_offset)

        self.comb += [
            data_port.adr.eq(adr_line),
            If(write_from_slave,
                displacer(slave.dat_r, word, data_port.dat_w),
                displacer(Replicate(1, dw_to//8), word, data_port.we)
            ).Else(
                data_port.dat_w.eq(Replicate(master.dat_w, max(dw_to//dw_from, 1))),
                If(master.cyc & master.stb & master.we & master.ack,
                    displacer(master.sel, adr_offset, data_port.we, 2**offsetbits, reverse=reverse)
                )
            ),
            chooser(data_port.dat_r, word, slave.dat_w),
            slave.sel.eq(2**(dw_to//8)-1),
            chooser(data_port.dat_r, adr_offset_r, master.dat_r, reverse=reverse)
        ]


        # Tag memory
        tag_layout = [("tag", tagbits), ("dirty", 1)]
        tag_mem = Memory(layout_len(tag_layout), 2**linebits)
        tag_port = tag_mem.get_port(write_capable=True)
        self.specials += tag_mem, tag_port
        tag_do = Record(tag_layout)
        tag_di = Record(tag_layout)
        self.comb += [
            tag_do.raw_bits().eq(tag_port.dat_r),
            tag_port.dat_w.eq(tag_di.raw_bits())
        ]

        self.comb += [
            tag_port.adr.eq(adr_line),
            tag_di.tag.eq(adr_tag)
        ]
        if word is not None:
            self.comb += slave.adr.eq(Cat(word, adr_line, tag_do.tag))
        else:
            self.comb += slave.adr.eq(Cat(adr_line, tag_do.tag))

        # slave word computation, word_clr and word_inc will be simplified
        # at synthesis when wordbits=0
        word_clr = Signal()
        word_inc = Signal()
        if word is not None:
            self.sync += \
                If(word_clr,
                    word.eq(0),
                ).Elif(word_inc,
                    word.eq(word+1)
                )

        def word_is_last(word):
            if word is not None:
                return word == 2**wordbits-1
            else:
                return 1

        # Control FSM
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(master.cyc & master.stb,
                NextState("TEST_HIT")
            )
        )
        fsm.act("TEST_HIT",
            word_clr.eq(1),
            If(tag_do.tag == adr_tag,
                master.ack.eq(1),
                If(master.we,
                    tag_di.dirty.eq(1),
                    tag_port.we.eq(1)
                ),
                NextState("IDLE")
            ).Else(
                If(tag_do.dirty,
                    NextState("EVICT")
                ).Else(
                    # Write the tag first to set the slave address
                    tag_port.we.eq(1),
                    word_clr.eq(1),
                    NextState("REFILL")
                )
            )
        )

        fsm.act("EVICT",
            slave.stb.eq(1),
            slave.cyc.eq(1),
            slave.we.eq(1),
            If(slave.ack,
                word_inc.eq(1),
                 If(word_is_last(word),
                    # Write the tag first to set the slave address
                    tag_port.we.eq(1),
                    word_clr.eq(1),
                    NextState("REFILL")
                )
            )
        )
        fsm.act("REFILL",
            slave.stb.eq(1),
            slave.cyc.eq(1),
            slave.we.eq(0),
            If(slave.ack,
                write_from_slave.eq(1),
                word_inc.eq(1),
                If(word_is_last(word),
                    NextState("TEST_HIT"),
                ).Else(
                    NextState("REFILL")
                )
            )
        )
