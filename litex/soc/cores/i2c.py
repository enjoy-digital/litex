from migen import *
from misoc.interconnect import wishbone


__all__ = [
    "I2CMaster",
    "I2C_XFER_ADDR", "I2C_CONFIG_ADDR",
    "I2C_ACK", "I2C_READ", "I2C_WRITE", "I2C_STOP", "I2C_START", "I2C_IDLE",
]


class I2CClockGen(Module):
    def __init__(self, width):
        self.load  = Signal(width)
        self.clk2x = Signal()

        cnt = Signal.like(self.load)
        self.comb += [
            self.clk2x.eq(cnt == 0),
        ]
        self.sync += [
            If(self.clk2x,
                cnt.eq(self.load),
            ).Else(
                cnt.eq(cnt - 1),
            ),
        ]


class I2CMasterMachine(Module):
    def __init__(self, clock_width):
        self.scl_o = Signal(reset=1)
        self.sda_o = Signal(reset=1)
        self.sda_i = Signal()

        self.submodules.cg  = CEInserter()(I2CClockGen(clock_width))
        self.idle  = Signal()
        self.start = Signal()
        self.stop  = Signal()
        self.write = Signal()
        self.read  = Signal()
        self.ack   = Signal()
        self.data  = Signal(8)

        ###

        busy = Signal()
        bits = Signal(4)

        fsm = CEInserter()(FSM("IDLE"))
        self.submodules += fsm

        fsm.act("IDLE",
            If(self.start,
                NextState("START0"),
            ).Elif(self.stop & self.start,
                NextState("RESTART0"),
            ).Elif(self.stop,
                NextState("STOP0"),
            ).Elif(self.write,
                NextValue(bits, 8),
                NextState("WRITE0"),
            ).Elif(self.read,
                NextValue(bits, 8),
                NextState("READ0"),
            )
        )

        fsm.act("START0",
            NextValue(self.scl_o, 1),
            NextState("START1"))
        fsm.act("START1",
            NextValue(self.sda_o, 0),
            NextState("IDLE"))

        fsm.act("RESTART0",
            NextValue(self.scl_o, 0),
            NextState("RESTART1"))
        fsm.act("RESTART1",
            NextValue(self.sda_o, 1),
            NextState("START0"))

        fsm.act("STOP0",
            NextValue(self.scl_o, 0),
            NextState("STOP1"))
        fsm.act("STOP1",
            NextValue(self.scl_o, 1),
            NextValue(self.sda_o, 0),
            NextState("STOP2"))
        fsm.act("STOP2",
            NextValue(self.sda_o, 1),
            NextState("IDLE"))

        fsm.act("WRITE0",
            NextValue(self.scl_o, 0),
            If(bits == 0,
                NextValue(self.sda_o, 1),
                NextState("READACK0"),
            ).Else(
                NextValue(self.sda_o, self.data[7]),
                NextState("WRITE1"),
            )
        )
        fsm.act("WRITE1",
            NextValue(self.scl_o, 1),
            NextValue(self.data[1:], self.data[:-1]),
            NextValue(bits, bits - 1),
            NextState("WRITE0"),
        )
        fsm.act("READACK0",
            NextValue(self.scl_o, 1),
            NextState("READACK1"),
        )
        fsm.act("READACK1",
            NextValue(self.ack, ~self.sda_i),
            NextState("IDLE")
        )

        fsm.act("READ0",
            NextValue(self.scl_o, 0),
            NextValue(self.sda_o, 1),
            NextState("READ1"),
        )
        fsm.act("READ1",
            NextValue(self.data[0], self.sda_i),
            NextValue(self.scl_o, 0),
            If(bits == 0,
                NextValue(self.sda_o, ~self.ack),
                NextState("WRITEACK0"),
            ).Else(
                NextValue(self.sda_o, 1),
                NextState("READ2"),
            )
        )
        fsm.act("READ2",
            NextValue(self.scl_o, 1),
            NextValue(self.data[1:], self.data[:-1]),
            NextValue(bits, bits - 1),
            NextState("READ1"),
        )
        fsm.act("WRITEACK0",
            NextValue(self.scl_o, 1),
            NextState("IDLE"),
        )

        run = Signal()
        self.comb += [
            run.eq(self.start | self.stop | self.write | self.read),
            self.idle.eq(~run & fsm.ongoing("IDLE")),
            self.cg.ce.eq(~self.idle),
            fsm.ce.eq(run | self.cg.clk2x),
        ]

# Registers:
# config = Record([
#     ("div",   20),
# ])
# xfer = Record([
#     ("data",  8),
#     ("ack",   1),
#     ("read",  1),
#     ("write", 1),
#     ("start", 1),
#     ("stop",  1),
#     ("idle",  1),
# ])
class I2CMaster(Module):
    def __init__(self, pads, bus=None):
        if bus is None:
            bus = wishbone.Interface(data_width=32)
        self.bus = bus

        ###

        # Wishbone
        self.submodules.i2c = i2c = I2CMasterMachine(
            clock_width=20)

        self.sync += [
            # read
            If(bus.adr[0],
                bus.dat_r.eq(i2c.cg.load),
            ).Else(
                bus.dat_r.eq(Cat(i2c.data, i2c.ack, C(0, 4), i2c.idle)),
            ),

            # write
            i2c.read.eq(0),
            i2c.write.eq(0),
            i2c.start.eq(0),
            i2c.stop.eq(0),

            bus.ack.eq(0),
            If(bus.cyc & bus.stb & ~bus.ack,
                bus.ack.eq(1),
                If(bus.we,
                    If(bus.adr[0],
                        i2c.cg.load.eq(bus.dat_w),
                    ).Else(
                        i2c.data.eq(bus.dat_w[0:8]),
                        i2c.ack.eq(bus.dat_w[8]),
                        i2c.read.eq(bus.dat_w[9]),
                        i2c.write.eq(bus.dat_w[10]),
                        i2c.start.eq(bus.dat_w[11]),
                        i2c.stop.eq(bus.dat_w[12]),
                    )
                )
            )
        ]

        # I/O
        self.scl_t = TSTriple()
        self.specials += self.scl_t.get_tristate(pads.scl)
        self.comb += [
            self.scl_t.oe.eq(~i2c.scl_o),
            self.scl_t.o.eq(0),
        ]

        self.sda_t = TSTriple()
        self.specials += self.sda_t.get_tristate(pads.sda)
        self.comb += [
            self.sda_t.oe.eq(~i2c.sda_o),
            self.sda_t.o.eq(0),
            i2c.sda_i.eq(self.sda_t.i),
        ]

I2C_XFER_ADDR, I2C_CONFIG_ADDR = range(2)
(
    I2C_ACK,
    I2C_READ,
    I2C_WRITE,
    I2C_START,
    I2C_STOP,
    I2C_IDLE,
) = (1 << i for i in range(8, 14))
