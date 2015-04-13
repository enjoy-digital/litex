from migen.fhdl.std import *
from migen.genlib import roundrobin
from migen.genlib.record import *
from migen.genlib.misc import optree, chooser
from migen.genlib.fsm import FSM, NextState
from migen.bus.transactions import *

_layout = [
    ("adr",        30,                DIR_M_TO_S),
    ("dat_w",    "data_width",     DIR_M_TO_S),
    ("dat_r",    "data_width",     DIR_S_TO_M),
    ("sel",        "sel_width",    DIR_M_TO_S),
    ("cyc",        1,                DIR_M_TO_S),
    ("stb",        1,                DIR_M_TO_S),
    ("ack",        1,                DIR_S_TO_M),
    ("we",        1,                DIR_M_TO_S),
    ("cti",        3,                DIR_M_TO_S),
    ("bte",        2,                DIR_M_TO_S),
    ("err",        1,                DIR_S_TO_M)
]

class Interface(Record):
    def __init__(self, data_width=32):
        Record.__init__(self, set_layout_parameters(_layout,
            data_width=data_width,
            sel_width=data_width//8))

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
            master.ack.eq(optree("|", [slave[1].ack for slave in slaves])),
            master.err.eq(optree("|", [slave[1].err for slave in slaves]))
        ]

        # mux (1-hot) slave data return
        masked = [Replicate(slave_sel_r[i], flen(master.dat_r)) & slaves[i][1].dat_r for i in range(ns)]
        self.comb += master.dat_r.eq(optree("|", masked))

class InterconnectShared(Module):
    def __init__(self, masters, slaves, register=False):
        shared = Interface()
        self.submodules += Arbiter(masters, shared)
        self.submodules += Decoder(shared, slaves, register)

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
    # DownConverter splits Wishbone accesses of N bits in M accesses of L bits where:
    # N is the original data-width
    # L is the target data-width
    # M = N/L
    def __init__(self, dw_i, dw_o):
        self.wishbone_i = Interface(dw_i)
        self.wishbone_o = Interface(dw_o)
        self.ratio = dw_i//dw_o

        ###

        rst = Signal()

        # generate internal write and read ack
        write_ack = Signal()
        read_ack = Signal()
        ack = Signal()
        self.comb += [
            ack.eq(self.wishbone_o.cyc & self.wishbone_o.stb & self.wishbone_o.ack),
            write_ack.eq(ack & self.wishbone_o.we),
            read_ack.eq(ack & ~self.wishbone_o.we)
        ]

        # accesses counter logic
        cnt = Signal(max=self.ratio)
        self.sync += If(rst, cnt.eq(0)).Elif(ack, cnt.eq(cnt + 1))

        # read data path
        dat_r = Signal(dw_i)
        self.sync += If(ack, dat_r.eq(Cat(self.wishbone_o.dat_r, dat_r[:dw_i-dw_o])))

        # write data path
        dat_w = Signal(dw_i)
        self.comb += dat_w.eq(self.wishbone_i.dat_w)

        # errors generation
        err = Signal()
        self.sync += If(ack, err.eq(self.wishbone_o.err))

        # direct connection of wishbone_i --> wishbone_o signals
        for name, size, direction in self.wishbone_i.layout:
            if direction == DIR_M_TO_S and name not in ["adr", "dat_w", "sel"]:
                self.comb += getattr(self.wishbone_o, name).eq(getattr(self.wishbone_i, name))

        # adaptation of adr & dat signals
        self.comb += [
            self.wishbone_o.adr[0:flen(cnt)].eq(cnt),
            self.wishbone_o.adr[flen(cnt):].eq(self.wishbone_i.adr)
        ]

        self.comb += chooser(dat_w, cnt, self.wishbone_o.dat_w, reverse=True)
        self.comb += chooser(self.wishbone_i.sel, cnt, self.wishbone_o.sel, reverse=True)

        # fsm
        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            If(write_ack, NextState("WRITE_ADAPT")),
            If(read_ack, NextState("READ_ADAPT"))
        )

        fsm.act("WRITE_ADAPT",
            If(write_ack & (cnt == self.ratio-1),
                NextState("IDLE"),
                rst.eq(1),
                self.wishbone_i.err.eq(err | self.wishbone_o.err),
                self.wishbone_i.ack.eq(1),
            )
        )

        master_i_dat_r = Signal(dw_i)
        self.comb += master_i_dat_r.eq(Cat(self.wishbone_o.dat_r, dat_r[:dw_i-dw_o]))

        fsm.act("READ_ADAPT",
            If(read_ack & (cnt == self.ratio-1),
                NextState("IDLE"),
                rst.eq(1),
                self.wishbone_i.err.eq(err | self.wishbone_o.err),
                self.wishbone_i.ack.eq(1),
                self.wishbone_i.dat_r.eq(master_i_dat_r)
            )
        )

class Tap(Module):
    def __init__(self, bus, handler=print):
        self.bus = bus
        self.handler = handler

    def do_simulation(self, selfp):
        if selfp.bus.ack:
            assert(selfp.bus.cyc and selfp.bus.stb)
            if selfp.bus.we:
                transaction = TWrite(selfp.bus.adr,
                    selfp.bus.dat_w,
                    selfp.bus.sel)
            else:
                transaction = TRead(selfp.bus.adr,
                    selfp.bus.dat_r)
            self.handler(transaction)
    do_simulation.passive = True

class Initiator(Module):
    def __init__(self, generator, bus=None):
        self.generator = generator
        if bus is None:
            bus = Interface()
        self.bus = bus
        self.transaction_start = 0
        self.transaction = None

    def do_simulation(self, selfp):
        if self.transaction is None or selfp.bus.ack:
            if self.transaction is not None:
                self.transaction.latency = selfp.simulator.cycle_counter - self.transaction_start - 1
                if isinstance(self.transaction, TRead):
                    self.transaction.data = selfp.bus.dat_r
            try:
                self.transaction = next(self.generator)
            except StopIteration:
                selfp.bus.cyc = 0
                selfp.bus.stb = 0
                raise StopSimulation
            if self.transaction is not None:
                self.transaction_start = selfp.simulator.cycle_counter
                selfp.bus.cyc = 1
                selfp.bus.stb = 1
                selfp.bus.adr = self.transaction.address
                if isinstance(self.transaction, TWrite):
                    selfp.bus.we = 1
                    selfp.bus.sel = self.transaction.sel
                    selfp.bus.dat_w = self.transaction.data
                else:
                    selfp.bus.we = 0
            else:
                selfp.bus.cyc = 0
                selfp.bus.stb = 0

class TargetModel:
    def read(self, address):
        return 0

    def write(self, address, data, sel):
        pass

    def can_ack(self, bus):
        return True

class Target(Module):
    def __init__(self, model, bus=None):
        if bus is None:
            bus = Interface()
        self.bus = bus
        self.model = model

    def do_simulation(self, selfp):
        bus = selfp.bus
        if not bus.ack:
            if self.model.can_ack(bus) and bus.cyc and bus.stb:
                if bus.we:
                    self.model.write(bus.adr, bus.dat_w, bus.sel)
                else:
                    bus.dat_r = self.model.read(bus.adr)
                bus.ack = 1
        else:
            bus.ack = 0
    do_simulation.passive = True

class SRAM(Module):
    def __init__(self, mem_or_size, read_only=None, init=None, bus=None):
        if bus is None:
            bus = Interface()
        self.bus = bus
        bus_data_width = flen(self.bus.dat_r)
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
        port = self.mem.get_port(write_capable=not read_only, we_granularity=8)
        self.specials += self.mem, port
        # generate write enable signal
        if not read_only:
            self.comb += [port.we[i].eq(self.bus.cyc & self.bus.stb & self.bus.we & self.bus.sel[i])
                for i in range(4)]
        # address and data
        self.comb += [
            port.adr.eq(self.bus.adr[:flen(port.adr)]),
            self.bus.dat_r.eq(port.dat_r)
        ]
        if not read_only:
            self.comb += port.dat_w.eq(self.bus.dat_w),
        # generate ack
        self.sync += [
            self.bus.ack.eq(0),
            If(self.bus.cyc & self.bus.stb & ~self.bus.ack,    self.bus.ack.eq(1))
        ]
