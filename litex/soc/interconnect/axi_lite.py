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
