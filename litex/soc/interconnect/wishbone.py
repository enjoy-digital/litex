# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 Tim 'mithro' Ansell <me@mith.ro>
# License: BSD

from functools import reduce
from operator import or_

from migen import *
from migen.genlib import roundrobin
from migen.genlib.record import *
from migen.genlib.misc import split, displacer, chooser, WaitTimer
from migen.genlib.fsm import FSM, NextState

from litex.soc.interconnect import csr

# TODO: rewrite without FlipFlop


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


class Interface(Record):
    def __init__(self, data_width=32, adr_width=30):
        self.data_width = data_width
        self.adr_width  = adr_width
        Record.__init__(self, set_layout_parameters(_layout,
            adr_width=adr_width,
            data_width=data_width,
            sel_width=data_width//8))

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

    def write(self, adr, dat, sel=None):
        if sel is None:
            sel = 2**len(self.sel) - 1
        yield self.adr.eq(adr)
        yield self.dat_w.eq(dat)
        yield self.sel.eq(sel)
        yield self.we.eq(1)
        yield from self._do_transaction()

    def read(self, adr):
        yield self.adr.eq(adr)
        yield self.we.eq(0)
        yield from self._do_transaction()
        return (yield self.dat_r)


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


class InterconnectShared(Module):
    def __init__(self, masters, slaves, register=False, timeout_cycles=1e6):
        shared = Interface()
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


class DownConverter(Module):
    """DownConverter

    This module splits Wishbone accesses from a master interface to a smaller
    slave interface.

    Writes:
        Writes from master are splitted N writes to the slave. Access is acked when the last
        access is acked by the slave.

    Reads:
        Read from master are splitted in N reads to the the slave. Read datas from
        the slave are cached before being presented concatenated on the last access.

    """
    def __init__(self, master, slave):
        dw_from = len(master.dat_r)
        dw_to = len(slave.dat_w)
        ratio = dw_from//dw_to

        # # #

        read = Signal()
        write = Signal()

        counter = Signal(max=ratio)
        counter_reset = Signal()
        counter_ce = Signal()
        self.sync += \
            If(counter_reset,
                counter.eq(0)
            ).Elif(counter_ce,
                counter.eq(counter + 1)
            )
        counter_done = Signal()
        self.comb += counter_done.eq(counter == ratio-1)

        # Main FSM
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            counter_reset.eq(1),
            If(master.stb & master.cyc,
                If(master.we,
                    NextState("WRITE")
                ).Else(
                    NextState("READ")
                )
            )
        )
        fsm.act("WRITE",
            write.eq(1),
            slave.we.eq(1),
            slave.cyc.eq(1),
            If(master.stb & master.cyc,
                slave.stb.eq(1),
                If(slave.ack,
                    counter_ce.eq(1),
                    If(counter_done,
                        master.ack.eq(1),
                        NextState("IDLE")
                    )
                )
            ).Elif(~master.cyc,
                NextState("IDLE")
            )
        )
        fsm.act("READ",
            read.eq(1),
            slave.cyc.eq(1),
            If(master.stb & master.cyc,
                slave.stb.eq(1),
                If(slave.ack,
                    counter_ce.eq(1),
                    If(counter_done,
                        master.ack.eq(1),
                        NextState("IDLE")
                    )
                )
            ).Elif(~master.cyc,
                NextState("IDLE")
            )
        )

        # Address
        self.comb += [
            If(counter_done,
                slave.cti.eq(7) # indicate end of burst
            ).Else(
                slave.cti.eq(2)
            ),
            slave.adr.eq(Cat(counter, master.adr))
        ]

        # Datapath
        cases = {}
        for i in range(ratio):
            cases[i] = [
                slave.sel.eq(master.sel[i*dw_to//8:(i+1)*dw_to]),
                slave.dat_w.eq(master.dat_w[i*dw_to:(i+1)*dw_to])
            ]
        self.comb += Case(counter, cases)


        cached_data = Signal(dw_from)
        self.comb += master.dat_r.eq(Cat(cached_data[dw_to:], slave.dat_r))
        self.sync += \
            If(read & counter_ce,
                cached_data.eq(master.dat_r)
            )


@ResetInserter()
@CEInserter()
class FlipFlop(Module):
    def __init__(self, *args, **kwargs):
        self.d = Signal(*args, **kwargs)
        self.q = Signal(*args, **kwargs)
        self.sync += self.q.eq(self.d)


class UpConverter(Module):
    """UpConverter

    This module up-converts wishbone accesses and bursts from a master interface
    to a wider slave interface. This allows efficient use wishbone bursts.

    Writes:
        Wishbone writes are cached before being written to the slave. Access to
        the slave is done at the end of a burst or when address reach end of burst
        addressing.

    Reads:
        Cache is refilled only at the beginning of each burst, the subsequent
        reads of a burst use the cached data.

    """
    def __init__(self, master, slave):
        dw_from = len(master.dat_r)
        dw_to = len(slave.dat_w)
        ratio = dw_to//dw_from
        ratiobits = log2_int(ratio)

        # # #

        write = Signal()
        evict = Signal()
        refill = Signal()
        read = Signal()

        address = FlipFlop(30)
        self.submodules += address
        self.comb += address.d.eq(master.adr)

        counter = Signal(max=ratio)
        counter_ce = Signal()
        counter_reset = Signal()
        self.sync += \
            If(counter_reset,
                counter.eq(0)
            ).Elif(counter_ce,
                counter.eq(counter + 1)
            )
        counter_offset = Signal(max=ratio)
        counter_done = Signal()
        self.comb += [
            counter_offset.eq(address.q),
            counter_done.eq((counter + counter_offset) == ratio-1)
        ]

        cached_data = Signal(dw_to)
        cached_sel = Signal(dw_to//8)

        end_of_burst = Signal()
        self.comb += end_of_burst.eq(~master.cyc |
                                     (master.stb & master.cyc & master.ack & ((master.cti == 7) | counter_done)))


        need_refill = FlipFlop(reset=1)
        self.submodules += need_refill
        self.comb += [
            need_refill.reset.eq(end_of_burst),
            need_refill.d.eq(0)
        ]

        # Main FSM
        self.submodules.fsm = fsm = FSM()
        fsm.act("IDLE",
            counter_reset.eq(1),
            If(master.stb & master.cyc,
                address.ce.eq(1),
                If(master.we,
                    NextState("WRITE")
                ).Else(
                    If(need_refill.q,
                        NextState("REFILL")
                    ).Else(
                        NextState("READ")
                    )
                )
            )
        )
        fsm.act("WRITE",
            If(master.stb & master.cyc,
                write.eq(1),
                counter_ce.eq(1),
                master.ack.eq(1),
                If(counter_done,
                    NextState("EVICT")
                )
            ).Elif(~master.cyc,
                NextState("EVICT")
            )
        )
        fsm.act("EVICT",
            evict.eq(1),
            slave.stb.eq(1),
            slave.we.eq(1),
            slave.cyc.eq(1),
            slave.dat_w.eq(cached_data),
            slave.sel.eq(cached_sel),
            If(slave.ack,
                NextState("IDLE")
            )
        )
        fsm.act("REFILL",
            refill.eq(1),
            slave.stb.eq(1),
            slave.cyc.eq(1),
            If(slave.ack,
                need_refill.ce.eq(1),
                NextState("READ")
            )
        )
        fsm.act("READ",
            read.eq(1),
            If(master.stb & master.cyc,
                master.ack.eq(1)
            ),
            NextState("IDLE")
        )

        # Address
        self.comb += [
            slave.cti.eq(7), # we are not able to generate bursts since up-converting
            slave.adr.eq(address.q[ratiobits:])
        ]

        # Datapath
        cached_datas = [FlipFlop(dw_from) for i in range(ratio)]
        cached_sels = [FlipFlop(dw_from//8) for i in range(ratio)]
        self.submodules += cached_datas, cached_sels

        cases = {}
        for i in range(ratio):
            write_sel = Signal()
            cases[i] = write_sel.eq(1)
            self.comb += [
                cached_sels[i].reset.eq(counter_reset),
                If(write,
                    cached_datas[i].d.eq(master.dat_w),
                ).Else(
                    cached_datas[i].d.eq(slave.dat_r[dw_from*i:dw_from*(i+1)])
                ),
                cached_sels[i].d.eq(master.sel),
                If((write & write_sel) | refill,
                    cached_datas[i].ce.eq(1),
                    cached_sels[i].ce.eq(1)
                )
            ]
        self.comb += Case(counter + counter_offset, cases)

        cases = {}
        for i in range(ratio):
            cases[i] = master.dat_r.eq(cached_datas[i].q)
        self.comb += Case(address.q[:ratiobits], cases)

        self.comb += [
            cached_data.eq(Cat([cached_data.q for cached_data in cached_datas])),
            cached_sel.eq(Cat([cached_sel.q for cached_sel in cached_sels]))
        ]


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


class Cache(Module):
    """Cache

    This module is a write-back wishbone cache that can be used as a L2 cache.
    Cachesize (in 32-bit words) is the size of the data store and must be a power of 2
    """
    def __init__(self, cachesize, master, slave):
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
            adr_offset_r = Signal(offsetbits)
            self.sync += adr_offset_r.eq(adr_offset)

        self.comb += [
            data_port.adr.eq(adr_line),
            If(write_from_slave,
                displacer(slave.dat_r, word, data_port.dat_w),
                displacer(Replicate(1, dw_to//8), word, data_port.we)
            ).Else(
                data_port.dat_w.eq(Replicate(master.dat_w, max(dw_to//dw_from, 1))),
                If(master.cyc & master.stb & master.we & master.ack,
                    displacer(master.sel, adr_offset, data_port.we, 2**offsetbits, reverse=True)
                )
            ),
            chooser(data_port.dat_r, word, slave.dat_w),
            slave.sel.eq(2**(dw_to//8)-1),
            chooser(data_port.dat_r, adr_offset_r, master.dat_r, reverse=True)
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
                    NextState("REFILL_WRTAG")
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
                    NextState("REFILL_WRTAG")
                )
            )
        )
        fsm.act("REFILL_WRTAG",
            # Write the tag first to set the slave address
            tag_port.we.eq(1),
            word_clr.eq(1),
            NextState("REFILL")
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


class SRAM(Module):
    def __init__(self, mem_or_size, read_only=None, init=None, bus=None):
        if bus is None:
            bus = Interface()
        self.bus = bus
        bus_data_width = len(self.bus.dat_r)
        if isinstance(mem_or_size, Memory):
            assert(mem_or_size.width <= bus_data_width)
            self.mem = mem_or_size
        else:
            self.mem = Memory(bus_data_width, mem_or_size//(bus_data_width//8), init=init)
        if read_only is None:
            if hasattr(self.mem, "bus_read_only"):
                read_only = self.mem.bus_read_only
            else:
                read_only = False

        ###

        # memory
        port = self.mem.get_port(write_capable=not read_only, we_granularity=8,
            mode=READ_FIRST if read_only else WRITE_FIRST)
        self.specials += self.mem, port
        # generate write enable signal
        if not read_only:
            self.comb += [port.we[i].eq(self.bus.cyc & self.bus.stb & self.bus.we & self.bus.sel[i])
                for i in range(bus_data_width//8)]
        # address and data
        self.comb += [
            port.adr.eq(self.bus.adr[:len(port.adr)]),
            self.bus.dat_r.eq(port.dat_r)
        ]
        if not read_only:
            self.comb += port.dat_w.eq(self.bus.dat_w),
        # generate ack
        self.sync += [
            self.bus.ack.eq(0),
            If(self.bus.cyc & self.bus.stb & ~self.bus.ack,    self.bus.ack.eq(1))
        ]


class CSRBank(csr.GenericBank):
    def __init__(self, description, bus=None):
        if bus is None:
            bus = Interface()
        self.bus = bus

        ###

        csr.GenericBank.__init__(self, description, len(self.bus.dat_w))

        for i, c in enumerate(self.simple_csrs):
            self.comb += [
                c.r.eq(self.bus.dat_w[:c.size]),
                c.re.eq(self.bus.cyc & self.bus.stb & ~self.bus.ack & self.bus.we & \
                    (self.bus.adr[:self.decode_bits] == i))
            ]

        brcases = dict((i, self.bus.dat_r.eq(c.w)) for i, c in enumerate(self.simple_csrs))
        self.sync += [
            Case(self.bus.adr[:self.decode_bits], brcases),
            If(bus.ack, bus.ack.eq(0)).Elif(bus.cyc & bus.stb, bus.ack.eq(1))
        ]
