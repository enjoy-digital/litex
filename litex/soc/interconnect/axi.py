"""AXI4Lite support for LiteX"""

# Copyright (C) 2018 by Sergiusz Bazanski
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted.

import math

from litex.gen import *
from litex.gen.genlib.record import *
from litex.soc.interconnect import csr_bus

# Layout of AXI4 Lite Bus
_layout = [
    # Write Address
    ("awaddr", "address_width", DIR_M_TO_S),
    ("awprot", 3, DIR_M_TO_S),
    ("awvalid", 1, DIR_M_TO_S),
    ("awready", 1, DIR_S_TO_M),

    # Write Data
    ("wdata", "data_width", DIR_M_TO_S),
    ("wstrb", "strb_width", DIR_M_TO_S),
    ("wvalid", 1, DIR_M_TO_S),
    ("wready", 1, DIR_S_TO_M),

    # Write Response
    ("bresp", 2, DIR_S_TO_M),
    ("bvalid", 1, DIR_S_TO_M),
    ("bready", 1, DIR_M_TO_S),

    # Read Address
    ("araddr", "address_width", DIR_M_TO_S),
    ("arprot", 3, DIR_M_TO_S),
    ("arvalid", 1, DIR_M_TO_S),
    ("arready", 1, DIR_S_TO_M),

    # Read Data
    ("rdata", "data_width", DIR_S_TO_M),
    ("rresp", 2, DIR_S_TO_M),
    ("rvalid", 1, DIR_S_TO_M),
    ("rready", 1, DIR_M_TO_S),
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

    def __init__(self, bus_interface_axi, bus_interface_csr):
        self.axi = bus_interface_axi
        self.csr = bus_interface_csr

        ###

        # Machine is currently busy talking to CSR, hold your horses.
        busy = Signal()

        # A write transaction is happening on the bus.
        write_transaction = Signal()
        # A read transaction is happening on the bus.
        read_transaction = Signal()
        self.comb += [
            write_transaction.eq(self.axi.awvalid & self.axi.awready & self.axi.wvalid & self.axi.wready),
            read_transaction.eq(self.axi.arvalid & self.axi.arready),
        ]

        # Write transaction generation.
        self.sync += [
            self.axi.awready.eq(0),
            self.axi.wready.eq(0),
            If(self.axi.awvalid & self.axi.wvalid,
                If(~self.axi.awready & ~busy & ~self.axi.arvalid,
                    self.axi.awready.eq(1),
                    self.axi.wready.eq(1)
                )
            )
        ]
        # Write response generation.
        self.sync += [
            self.axi.bvalid.eq(0),
            If(write_transaction,
                If(self.axi.bready & ~self.axi.bvalid,
                    self.axi.bvalid.eq(1),
                    # Response 0 -> OKAY
                    self.axi.bresp.eq(0),
                )
            )
        ]
        # Read transaction generation.
        self.sync += [
            self.axi.arready.eq(0),
            If(self.axi.arvalid & ~self.axi.arready & ~busy,
                self.axi.arready.eq(1),
            )
        ]


        # Registered data to be written to CSR, set by FSM.
        wdata = Signal(self.csr.dat_w.nbits)
        # Combinatorial byte address to assert on CSR bus, driven by FSM.
        addr = Signal(self.axi.araddr.nbits)
        # Drive AXI & CSR combinatorial signals.
        self.comb += [
            self.csr.adr.eq(addr >> 
                int(math.log(self.axi.rdata.nbits//8, 2.0))),
            self.csr.dat_w.eq(wdata),

            self.axi.rdata.eq(self.csr.dat_r),
            self.axi.rresp.eq(0),
        ]

        # CSR interaction FSM.
        self.submodules.fsm = FSM(reset_state='IDLE')
        self.comb += [
            busy.eq(~self.fsm.ongoing('IDLE')),
            self.axi.rvalid.eq(self.fsm.ongoing('READING')),
            self.csr.we.eq(self.fsm.ongoing('WRITING')),
        ]

        # Idle state - wait for a transaction to happen on AXI. Immediately
        # assert read/write address on CSR if such an transaction is occuring.
        self.fsm.act('IDLE',
            If(read_transaction,
                addr.eq(self.axi.araddr),
                NextState('READING'),
            ).Elif(write_transaction,
                addr.eq(self.axi.awaddr),
                # Register data from AXI.
                NextValue(wdata, self.axi.wdata),
                NextState('WRITING'),
            )
        )

        # Perform write to CSR.
        self.fsm.act('WRITING',
            addr.eq(self.axi.awaddr),
            # CSR writes are single cycle, go back to IDLE.
            NextState('IDLE'),
        )

        # Respond to read to AXI.
        self.fsm.act('READING',
            addr.eq(self.axi.araddr),
            # If AXI master is ready to receive data, go back to IDLE.
            If(self.axi.rready,
                NextState('IDLE'),
            )
        )


from litex.gen.sim import run_simulation
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
            self.submodules.csrbankarray = csr_bus.CSRBankArray(self, self.map_csr, data_width=32, address_width=12)
            self.submodules.csrcon = csr_bus.Interconnect(self.csr, self.csrbankarray.get_buses())

        def map_csr(self, name, memory):
            return {
                'holder': 0,
            }[name]

    def testbench_write_read(dut):
        for _ in range(8):
            yield

        # Write test
        yield dut.axi.awvalid.eq(1)
        yield dut.axi.awaddr.eq(4)
        yield dut.axi.wvalid.eq(1)
        yield dut.axi.bready.eq(1)
        yield dut.axi.wdata.eq(0x2137)

        while (yield dut.axi.awready) != 1:
            yield
        while (yield dut.axi.wready) != 1:
            yield
        yield dut.axi.awvalid.eq(0)
        yield dut.axi.wvalid.eq(0)

        for _ in range(8):
            yield

        # Read test
        yield dut.axi.arvalid.eq(1)
        yield dut.axi.rready.eq(1)
        yield dut.axi.araddr.eq(4)

        while (yield dut.axi.arready != 1):
            yield
        yield dut.axi.arvalid.eq(0)
        while (yield dut.axi.rvalid != 1):
            yield
        yield dut.axi.rready.eq(0)

        read = yield dut.axi.rdata
        assert read == 0x2137

        for _ in range(8):
            yield

    def testbench_simultaneous(dut):
        for _ in range(8):
            yield

        # Write
        yield dut.axi.awvalid.eq(1)
        yield dut.axi.awaddr.eq(2)
        yield dut.axi.wvalid.eq(1)
        yield dut.axi.bready.eq(1)
        yield dut.axi.wdata.eq(0x2137)
        # Read
        yield dut.axi.arvalid.eq(1)
        yield dut.axi.rready.eq(1)
        yield dut.axi.araddr.eq(2)

        yield
        yield

        is_reading = yield dut.axi.arready
        is_writing = yield dut.axi.awready

        assert is_reading
        assert not is_writing

    fixture = Fixture()
    run_simulation(fixture, testbench_write_read(fixture.dut), vcd_name='axi-write-read.vcd')
    fixture = Fixture()
    run_simulation(fixture, testbench_simultaneous(fixture.dut), vcd_name='axi-simultaneous.vcd')
