from itertools import product

from migen import *

from litex.soc.interconnect.csr import *


class SPIClockGen(Module):
    def __init__(self, width):
        self.load = Signal(width)
        self.bias = Signal()  # bias this clock phase to longer times
        self.edge = Signal()
        self.clk = Signal(reset=1)

        cnt = Signal.like(self.load)
        bias = Signal()
        zero = Signal()
        self.comb += [
            zero.eq(cnt == 0),
            self.edge.eq(zero & ~bias),
        ]
        self.sync += [
            If(zero,
                bias.eq(0),
            ).Else(
                cnt.eq(cnt - 1),
            ),
            If(self.edge,
                cnt.eq(self.load[1:]),
                bias.eq(self.load[0] & (self.clk ^ self.bias)),
                self.clk.eq(~self.clk),
            )
        ]


class SPIRegister(Module):
    def __init__(self, width):
        self.data = Signal(width)
        self.o = Signal()
        self.i = Signal()
        self.lsb = Signal()
        self.shift = Signal()
        self.sample = Signal()

        self.comb += [
            self.o.eq(Mux(self.lsb, self.data[0], self.data[-1])),
        ]
        self.sync += [
            If(self.lsb,
                If(self.shift,
                    self.data[:-1].eq(self.data[1:])
                ),
                If(self.sample,
                    self.data[0].eq(self.i)
                )
            ).Else(
                If(self.shift,
                    self.data[1:].eq(self.data[:-1]),
                ),
                If(self.sample,
                    self.data[0].eq(self.i)
                )
            )
        ]


class SPIBitCounter(Module):
    def __init__(self, width):
        self.n_read = Signal(width)
        self.n_write = Signal(width)
        self.read = Signal()
        self.write = Signal()
        self.done = Signal()

        self.comb += [
            self.write.eq(self.n_write != 0),
            self.read.eq(self.n_read != 0),
            self.done.eq(~(self.write | self.read)),
        ]
        self.sync += [
            If(self.write,
                self.n_write.eq(self.n_write - 1),
            ).Elif(self.read,
                self.n_read.eq(self.n_read - 1),
            )
        ]


class SPIMachine(Module):
    def __init__(self, data_width, clock_width, bits_width):
        ce = CEInserter()
        self.submodules.cg = ce(SPIClockGen(clock_width))
        self.submodules.reg = ce(SPIRegister(data_width))
        self.submodules.bits = ce(SPIBitCounter(bits_width))
        self.div_write = Signal.like(self.cg.load)
        self.div_read = Signal.like(self.cg.load)
        self.clk_phase = Signal()
        self.start = Signal()
        self.cs = Signal()
        self.oe = Signal()
        self.done = Signal()

        # # #

        fsm = CEInserter()(FSM("IDLE"))
        self.submodules += fsm

        fsm.act("IDLE",
            If(self.start,
                If(self.clk_phase,
                    NextState("WAIT"),
                ).Else(
                    NextState("SETUP"),
                )
            )
        )
        fsm.act("SETUP",
            self.reg.sample.eq(1),
            NextState("HOLD"),
        )
        fsm.act("HOLD",
            If(self.bits.done & ~self.start,
                If(self.clk_phase,
                    NextState("IDLE"),
                ).Else(
                    NextState("WAIT"),
                )
            ).Else(
                self.reg.shift.eq(~self.start),
                NextState("SETUP"),
            )
        )
        fsm.act("WAIT",
            If(self.bits.done,
                NextState("IDLE"),
            ).Else(
                NextState("SETUP"),
            )
        )

        write0 = Signal()
        self.sync += [
            If(self.cg.edge & self.reg.shift,
                write0.eq(self.bits.write),
            )
        ]
        self.comb += [
            self.cg.ce.eq(self.start | self.cs | ~self.cg.edge),
            If(self.bits.write | ~self.bits.read,
                self.cg.load.eq(self.div_write),
            ).Else(
                self.cg.load.eq(self.div_read),
            ),
            self.cg.bias.eq(self.clk_phase),
            fsm.ce.eq(self.cg.edge),
            self.cs.eq(~fsm.ongoing("IDLE")),
            self.reg.ce.eq(self.cg.edge),
            self.bits.ce.eq(self.cg.edge & self.reg.sample),
            self.done.eq(self.cg.edge & self.bits.done & fsm.ongoing("HOLD")),
            self.oe.eq(write0 | self.bits.write),
        ]


class SPIMasterCore(Module):
    """SPI Master Core.

    Notes:
        * M = 32 is the data width (maximum write bits, maximum read bits)
        * Every transfer consists of a write_length 0-M bit write followed
          by a read_length 0-M bit read.
        * cs_n is asserted at the beginning and deasserted at the end of the
          transfer if there is no other transfer pending.
        * cs_n handling is agnostic to whether it is one-hot or decoded
          somewhere downstream. If it is decoded, "cs_n all deasserted"
          should be handled accordingly (no slave selected).
          If it is one-hot, asserting multiple slaves should only be attempted
          if miso is either not connected between slaves, or open collector,
          or correctly multiplexed externally.
        * If config.cs_polarity == 0 (cs active low, the default),
          "cs_n all deasserted" means "all cs_n bits high".
        * cs is not mandatory in pads. Framing and chip selection can also
          be handled independently through other means.
        * If there is a miso wire in pads, the input and output can be done
          with two signals (a.k.a. 4-wire SPI), else mosi must be used for
          both output and input (a.k.a. 3-wire SPI) and config.half_duplex
          must to be set when reading data is desired.
        * For 4-wire SPI only the sum of read_length and write_length matters.
          The behavior is the same no matter how the total transfer length is
          divided between the two. For 3-wire SPI, the direction of mosi/miso
          is switched from output to input after write_len cycles, at the
          "shift_out" clk edge corresponding to bit write_length + 1 of the
          transfer.
        * The first bit output on mosi is always the MSB/LSB (depending on
          config.lsb_first) of the miso_data signal, independent of
          xfer.write_len. The last bit input from miso always ends up in
          the LSB/MSB (respectively) of the misoc_data signal, independent of
          read_len.
        * Data output on mosi in 4-wire SPI during the read cycles is what
          is found in the data register at the time.
          Data in the data register outside the least/most (depending
          on config.lsb_first) significant read_length bits is what is
          seen on miso during the write cycles.
        * The SPI data register is double-buffered: Once a transfer has
          started, new write data can be written, queuing a new transfer.
          Transfers submitted this way are chained and executed without
          deasserting cs. Once a transfer completes, the previous transfer's
          read data is available in the data register.
        * Changes to config signal take effect immediately. Changes
          to xfer_* signals are synchronized to the start of a transfer.

    Transaction Sequence:
        * If desired, set the config signal to set up the core.
        * If designed, set the xfer signal to set up lengths and cs_n.
        * Set the miso_data signal (not required for zero-length writes),
        * Set start signal to 1
        * Wait for active and pending signals to be 0.
        * If desired, use the misoc_data signal corresponding to the last
          completed transfer.

    Core IOs:

    config signal:
        1 offline: all pins high-z (reset=1)
        1 active: cs/transfer active (read-only)
        1 pending: transfer pending in intermediate buffer (read-only)
        1 cs_polarity: active level of chip select (reset=0)
        1 clk_polarity: idle level of clk (reset=0)
        1 clk_phase: first edge after cs assertion to sample data on (reset=0)
            (clk_polarity, clk_phase) == (CPOL, CPHA) in Freescale language.
            (0, 0): idle low, output on falling, input on rising
            (0, 1): idle low, output on rising, input on falling
            (1, 0): idle high, output on rising, input on falling
            (1, 1): idle high, output on falling, input on rising
            There is never a clk edge during a cs edge.
        1 lsb_first: LSB is the first bit on the wire (reset=0)
        1 half_duplex: 3-wire SPI, in/out on mosi (reset=0)
        8 undefined
        8 div_write: counter load value to divide this module's clock
            to generate the SPI write clk (reset=0)
            f_clk/f_spi_write == div_write + 2
        8 div_read: ditto for the read clock

    xfer_config signal:
        16 cs: active high bit mask of chip selects to assert (reset=0)
        6 write_len: 0-M bits (reset=0)
        2 undefined
        6 read_len: 0-M bits (reset=0)
        2 undefined

    xfer_mosi/miso_data signal:
        M write/read data (reset=0)
    """
    def __init__(self, pads):
        self.config = Record([
            ("offline", 1),
            ("padding0", 2),
            ("cs_polarity", 1),
            ("clk_polarity", 1),
            ("clk_phase", 1),
            ("lsb_first", 1),
            ("half_duplex", 1),
            ("padding1", 8),
            ("div_write", 8),
            ("div_read", 8),
        ])
        self.config.offline.reset = 1

        self.xfer = Record([
            ("cs", 16),
            ("write_length", 6),
            ("padding0", 2),
            ("read_length", 6),
            ("padding1", 2),
        ])

        self.start = Signal()
        self.active = Signal()
        self.pending = Signal()
        self.mosi_data = Signal(32)
        self.miso_data = Signal(32)

        # # #

        self.submodules.machine = machine = SPIMachine(
            data_width=32,
            clock_width=len(self.config.div_read),
            bits_width=len(self.xfer.read_length))

        pending = Signal()
        cs = Signal.like(self.xfer.cs)
        data_read = Signal.like(machine.reg.data)
        data_write = Signal.like(machine.reg.data)

        self.comb += [
            self.miso_data.eq(data_read),
            machine.start.eq(pending & (~machine.cs | machine.done)),
            machine.clk_phase.eq(self.config.clk_phase),
            machine.reg.lsb.eq(self.config.lsb_first),
            machine.div_write.eq(self.config.div_write),
            machine.div_read.eq(self.config.div_read),
        ]
        self.sync += [
            If(machine.done,
                data_read.eq(machine.reg.data),
            ),
            If(machine.start,
                cs.eq(self.xfer.cs),
                machine.bits.n_write.eq(self.xfer.write_length),
                machine.bits.n_read.eq(self.xfer.read_length),
                machine.reg.data.eq(data_write),
                pending.eq(0),
            ),
            If(self.start,
                data_write.eq(self.mosi_data),
                pending.eq(1)
            ),
            self.active.eq(machine.cs),
            self.pending.eq(pending),
        ]

        # I/O
        if not hasattr(pads, "cs_n"):
            self.cs_n = Signal()
        else:
            self.cs_n = pads.cs_n
        cs_n_t = TSTriple(len(self.cs_n))
        self.specials += cs_n_t.get_tristate(self.cs_n)
        self.comb += [
            cs_n_t.oe.eq(~self.config.offline),
            cs_n_t.o.eq((cs & Replicate(machine.cs, len(cs))) ^
                        Replicate(~self.config.cs_polarity, len(cs))),
        ]

        clk_t = TSTriple()
        self.specials += clk_t.get_tristate(pads.clk)
        self.comb += [
            clk_t.oe.eq(~self.config.offline),
            clk_t.o.eq((machine.cg.clk & machine.cs) ^ self.config.clk_polarity),
        ]

        mosi_t = TSTriple()
        self.specials += mosi_t.get_tristate(pads.mosi)
        self.comb += [
            mosi_t.oe.eq(~self.config.offline & machine.cs &
                         (machine.oe | ~self.config.half_duplex)),
            mosi_t.o.eq(machine.reg.o),
            machine.reg.i.eq(Mux(self.config.half_duplex, mosi_t.i,
                             getattr(pads, "miso", mosi_t.i))),
        ]
        self.mosi_t = mosi_t


class SPIMaster(Module, AutoCSR):
    """SPI Master."""
    def __init__(self, pads, interface="csr"):
        self.submodules.core = core = SPIMasterCore(pads)

        # # #

        if interface == "csr":
            self.config = CSRStorage(32)
            self.xfer = CSRStorage(32)
            self.start = CSR()
            self.active = CSRStatus()
            self.pending = CSRStatus()
            self.mosi_data = CSRStorage(32)
            self.miso_data = CSRStatus(32)

            self.comb += [
                core.config.raw_bits().eq(self.config.storage),
                core.xfer.raw_bits().eq(self.xfer.storage),
                core.start.eq(self.start.re & self.start.r),
                self.active.status.eq(core.active),
                self.pending.status.eq(core.pending),
                core.mosi_data.eq(self.mosi_data.storage),
                self.miso_data.status.eq(core.miso_data)
            ]
        else:
            raise NotImplementedError
