"""AXI4Lite support for LiteX"""

# Copyright (C) 2018 by Sergiusz Bazanski
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted.

import math

from migen import *
from migen.genlib.record import *

from litex.soc.interconnect import csr_bus

# Layout of AXI4 Lite Bus
_layout = [
    # Write Address
    ("aw", [
        ("addr", "address_width", DIR_M_TO_S),
        ("prot", 3, DIR_M_TO_S),
        ("valid", 1, DIR_M_TO_S),
        ("ready", 1, DIR_S_TO_M),
    ]),

    # Write Data
    ("w", [
        ("data", "data_width", DIR_M_TO_S),
        ("strb", "strb_width", DIR_M_TO_S),
        ("valid", 1, DIR_M_TO_S),
        ("ready", 1, DIR_S_TO_M),
    ]),

    # Write Response
    ("b", [
        ("resp", 2, DIR_S_TO_M),
        ("valid", 1, DIR_S_TO_M),
        ("ready", 1, DIR_M_TO_S),
    ]),

    # Read Address
    ("ar", [
        ("addr", "address_width", DIR_M_TO_S),
        ("prot", 3, DIR_M_TO_S),
        ("valid", 1, DIR_M_TO_S),
        ("ready", 1, DIR_S_TO_M),
    ]),

    # Read Data
    ("r", [
        ("data", "data_width", DIR_S_TO_M),
        ("resp", 2, DIR_S_TO_M),
        ("valid", 1, DIR_S_TO_M),
        ("ready", 1, DIR_M_TO_S),
    ]),
]

class Interface(Record):
    """AXI4Lite Bus Interface"""
    def __init__(self, data_width=32, address_width=6):
        super().__init__(set_layout_parameters(_layout,
            data_width=data_width,
            address_width=address_width,
            strb_width=data_width//8))


class AXILite2CSR(Module):
    """
    A bridge between AXI4Lite and a CSR bus.

    This bridge will let you connect an CSR bus to an AXI4 Lite master. Please
    bear in mind that CSR is word-addressed but AXI4 is byte-addressed. This
    bridge performs translation, so your AXI bus should be at least two bits
    wider then your CSR bus.

    The bridge does not support unaligned reads/writes - it will round down
    every access to the nearest word. If it tries to access unmapped memory,
    it will return whaterver word is currently active on the CSR bus -
    including writes.
    """

    def __init__(self, bus_axi, bus_csr):
        self.axi = axi = bus_axi
        self.csr = csr = bus_csr

        ###

        ar, r, aw, w, b = axi.ar, axi.r, axi.aw, axi.w, axi.b

        # Machine is currently busy talking to CSR, hold your horses.
        busy = Signal()

        # A write transaction is happening on the bus.
        write_transaction = Signal()
        # A read transaction is happening on the bus.
        read_transaction = Signal()
        self.comb += [
            write_transaction.eq(aw.valid & aw.ready & w.valid & w.ready),
            read_transaction.eq(ar.valid & ar.ready),
        ]

        # Write transaction generation.
        self.sync += [
            aw.ready.eq(0),
            w.ready.eq(0),
            If(aw.valid & w.valid,
                If(~aw.ready & ~busy & ~ar.valid,
                    aw.ready.eq(1),
                    w.ready.eq(1)
                )
            )
        ]
        # Write response generation.
        self.sync += [
            b.valid.eq(0),
            If(write_transaction,
                If(b.ready & ~b.valid,
                    b.valid.eq(1),
                    # Response 0 -> OKAY
                    b.resp.eq(0),
                )
            )
        ]
        # Read transaction generation.
        self.sync += [
            ar.ready.eq(0),
            If(ar.valid & ~ar.ready & ~busy,
                ar.ready.eq(1),
            )
        ]


        # Registered data to be written to CSR, set by FSM.
        wdata = Signal(csr.dat_w.nbits)
        # Combinatorial byte address to assert on CSR bus, driven by FSM.
        addr = Signal(ar.addr.nbits)
        # Drive AXI & CSR combinatorial signals.
        self.comb += [
            csr.adr.eq(addr >> int(math.log(r.data.nbits//8, 2.0))),
            csr.dat_w.eq(wdata),

            r.data.eq(csr.dat_r),
            r.resp.eq(0),
        ]

        # CSR interaction FSM.
        self.submodules.fsm = fsm = FSM(reset_state='IDLE')
        self.comb += [
            busy.eq(~fsm.ongoing('IDLE')),
            r.valid.eq(fsm.ongoing('READING')),
            csr.we.eq(fsm.ongoing('WRITING')),
        ]

        # Idle state - wait for a transaction to happen on AXI. Immediately
        # assert read/write address on CSR if such an transaction is occuring.
        fsm.act('IDLE',
            If(read_transaction,
                addr.eq(ar.addr),
                NextState('READING'),
            ).Elif(write_transaction,
                addr.eq(aw.addr),
                # Register data from AXI.
                NextValue(wdata, w.data),
                NextState('WRITING'),
            )
        )

        # Perform write to CSR.
        fsm.act('WRITING',
            addr.eq(aw.addr),
            # CSR writes are single cycle, go back to IDLE.
            NextState('IDLE'),
        )

        # Respond to read to AXI.
        fsm.act('READING',
            addr.eq(ar.addr),
            # If AXI master is ready to receive data, go back to IDLE.
            If(r.ready,
                NextState('IDLE'),
            )
        )


from migen.sim import run_simulation
from litex.soc.interconnect import csr, csr_bus

def test_axilite2csr():
    class CSRHolder(Module, csr.AutoCSR):
        def __init__(self):
            self.foo = csr.CSRStorage(32, reset=1)
            self.bar = csr.CSRStorage(32, reset=1)

    class Fixture(Module):
        def __init__(self):
            self.csr = csr_bus.Interface(data_width=32, address_width=12)
            self.axi = Interface(data_width=32, address_width=14)
            self.submodules.holder = CSRHolder()
            self.submodules.dut = AXILite2CSR(self.axi, self.csr)
            self.submodules.csrbankarray = csr_bus.CSRBankArray(
                    self, self.map_csr, data_width=32, address_width=12)
            self.submodules.csrcon = csr_bus.Interconnect(
                    self.csr, self.csrbankarray.get_buses())

        def map_csr(self, name, memory):
            return {
                'holder': 0,
            }[name]

    def testbench_write_read(dut):
        axi = dut.axi

        for _ in range(8):
            yield

        # Write test
        yield axi.aw.valid.eq(1)
        yield axi.aw.addr.eq(4)
        yield axi.w.valid.eq(1)
        yield axi.b.ready.eq(1)
        yield axi.w.data.eq(0x2137)

        while (yield axi.aw.ready) != 1:
            yield
        while (yield axi.w.ready) != 1:
            yield
        yield axi.aw.valid.eq(0)
        yield axi.w.valid.eq(0)

        for _ in range(8):
            yield

        # Read test
        yield axi.ar.valid.eq(1)
        yield axi.r.ready.eq(1)
        yield axi.ar.addr.eq(4)

        while (yield axi.ar.ready != 1):
            yield
        yield axi.ar.valid.eq(0)
        while (yield axi.r.valid != 1):
            yield
        yield axi.r.ready.eq(0)

        read = yield axi.r.data
        assert read == 0x2137

        for _ in range(8):
            yield

    def testbench_simultaneous(dut):
        axi = dut.axi

        for _ in range(8):
            yield

        # Write
        yield axi.aw.valid.eq(1)
        yield axi.aw.addr.eq(2)
        yield axi.w.valid.eq(1)
        yield axi.b.ready.eq(1)
        yield axi.w.data.eq(0x2137)
        # Read
        yield axi.ar.valid.eq(1)
        yield axi.r.ready.eq(1)
        yield axi.ar.addr.eq(2)

        yield
        yield

        is_reading = yield axi.ar.ready
        is_writing = yield axi.aw.ready

        assert is_reading
        assert not is_writing

    fixture = Fixture()
    run_simulation(fixture, testbench_write_read(fixture.dut), vcd_name='axi-write-read.vcd')
    fixture = Fixture()
    run_simulation(fixture, testbench_simultaneous(fixture.dut), vcd_name='axi-simultaneous.vcd')
