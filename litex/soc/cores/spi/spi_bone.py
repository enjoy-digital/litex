#
# This file is part of LiteX.
#
# Copyright (c) 2019 Sean Cross <sean@xobs.io>
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.specials import Tristate, TSTriple
from migen.genlib.cdc import MultiReg

from litex.soc.integration.doc import ModuleDoc, AutoDoc
from litex.soc.interconnect import wishbone, stream

# SPIBone Doc for 4, 3 and 2 wires modes  ----------------------------------------------------------

class SPI4WireDocumentation(ModuleDoc):
    """4-Wire SPI Protocol

    The 4-wire SPI protocol does not require any pins to change direction, and
    is therefore suitable for designs with level-shifters or without GPIOs that
    can change direction.
    
    While waiting for the response, the ``MISO`` line remains high.  As soon as
    a response is available, the device pulls the `MISO` line low and clocks
    out either a ``0x00`` or `0x01` byte indicating whether it's a READ or a WRITE
    that is being answered.  Note that if the operation is fast enough, the
    device will not pull the `MISO` line high and will immediately respond
    with ``0x00`` or ``0x01``.

    You can abort the operation by driving ``CS`` high.  However, if a WRITE or
    READ has already been initiated then it will not be aborted.

    .. wavedrom::
        :caption: 4-Wire SPI Operation

        { "signal": [
            ["Read",
                {  "name": 'MOSI',        "wave": 'x23...x|xxxxxx', "data": '0x01 [ADDRESS]'},
                {  "name": 'MISO',        "wave": 'x.....x|25...x', "data": '0x01 [DATA]'   },
                {  "name": 'CS',          "wave": 'x0.....|.....x', "data": '1 2 3'},
                {  "name": 'data bits',   "wave": 'xx2222x|x2222x', "data": '31:24 23:16 15:8 7:0 31:24 23:16 15:8 7:0'}
            ],
            {},
            ["Write",
                {  "name": 'MOSI',        "wave": 'x23...3...x|xx', "data": '0x00 [ADDRESS] [DATA]'},
                {  "name": 'MISO',        "wave": 'x.........1|2x', "data": '0x00'   },
                {  "name": 'CS',          "wave": 'x0.........|.x', "data": '1 2 3'},
                {  "name": 'data bits',   "wave": 'xx22222222x|xx', "data": '31:24 23:16 15:8 7:0 31:24 23:16 15:8 7:0'}
            ]
        ]}
    """

class SPI3WireDocumentation(ModuleDoc):
    """3-Wire SPI Protocol

    The 3-wire SPI protocol repurposes the ``MOSI`` line for both data input and
    data output.  The direction of the line changes immediately after the
    address (for read) or the data (for write) and the device starts writing
    ``0xFF``.

    As soon as data is available (read) or the data has been written (write),
    the device drives the ``MOSI`` line low in order to clock out ``0x00``
    or ``0x01``.  This will always happen on a byte boundary.

    You can abort the operation by driving ``CS`` high.  However, if a WRITE or
    READ has already been initiated then it will not be aborted.

    .. wavedrom::
        :caption: 3-Wire SPI Operation

        { "signal": [
            ["Read",
                {  "name": 'MOSI',        "wave": 'x23...5|55...x', "data": '0x01 [ADDRESS] 0xFF 0x01 [DATA]'},
                {  "name": 'CS',          "wave": 'x0.....|.....x', "data": '1 2 3'},
                {  "name": 'data bits',   "wave": 'xx2222x|x2222x', "data": '31:24 23:16 15:8 7:0 31:24 23:16 15:8 7:0'}
            ],
            {},
            ["Write",
                {  "name": 'MOSI',        "wave": 'x23...3...5|50', "data": '0x00 [ADDRESS] [DATA] 0xFF 0x00'},
                {  "name": 'CS',          "wave": 'x0.........|.x', "data": '1 2 3'},
                {  "name": 'data bits',   "wave": 'xx22222222x|xx', "data": '31:24 23:16 15:8 7:0 31:24 23:16 15:8 7:0'}
            ]
        ]}
        """

class SPI2WireDocumentation(ModuleDoc):
    """2-Wire SPI Protocol

    The 2-wire SPI protocol removes the ``CS`` line in favor of a sync byte.
    Note that the 2-wire protocol has no way of interrupting communication,
    so if the bus locks up the device must be reset.  The direction of the
    data line changes immediately after the address (for read) or the data
    (for write) and the device starts writing ``0xFF``.

    As soon as data is available (read) or the data has been written (write),
    the device drives the ``MOSI`` line low in order to clock out ``0x00``
    or ``0x01``.  This will always happen on a byte boundary.

    All transactions begin with a sync byte of ``0xAB``.

    .. wavedrom::
        :caption: 2-Wire SPI Operation

        { "signal": [
            ["Write",
                {  "name": 'MOSI',        "wave": '223...5|55...', "data": '0xAB 0x01 [ADDRESS] 0xFF 0x01 [DATA]'},
                {  "name": 'data bits',   "wave": 'xx2222x|x2222', "data": '31:24 23:16 15:8 7:0 31:24 23:16 15:8 7:0'}
            ],
            {},
            ["Read",
                {  "name": 'MOSI',        "wave": '223...3...5|5', "data": '0xAB 0x00 [ADDRESS] [DATA] 0xFF 0x00'},
                {  "name": 'data bits',   "wave": 'xx22222222x|x', "data": '31:24 23:16 15:8 7:0 31:24 23:16 15:8 7:0'}
            ]
        ]}
        """

# SPIBone Core -------------------------------------------------------------------------------------

class SPIBone(Module, ModuleDoc, AutoDoc):
    """Wishbone Bridge over SPI

    This module allows for accessing a Wishbone bridge over a {}-wire protocol.
    All operations occur on byte boundaries, and are big-endian.

    The device can take a variable amount of time to respond, so the host should
    continue polling after the operation begins.  If the Wishbone bus is
    particularly busy, such as during periods of heavy processing when the
    CPU's icache is empty, responses can take many thousands of cycles.

    The bridge core is designed to run at 1/4 the system clock.
    """
    def __init__(self, pads, wires=4, with_tristate=True):
        self.bus = bus = wishbone.Interface(address_width=32, data_width=32)

        # # #

        # Parameters.
        # -----------
        if wires not in [2, 3, 4]:
            raise ValueError("`wires` must be 2, 3, or 4")

        # Doc.
        # ----
        self.__doc__ = self.__doc__.format(wires)
        self.mod_doc = {
            4 : SPI4WireDocumentation(),
            3 : SPI3WireDocumentation(),
            2 : SPI2WireDocumentation(),
        }[wires]

        # SPI IOs.
        # -------
        clk     = Signal()
        cs_n    = Signal()
        mosi    = Signal()
        miso    = Signal()
        miso_en = Signal()

        # Clk (Resynchronize).
        self.specials += MultiReg(pads.clk, clk)

        # CSn (Resynchronize).
        if wires in [3, 4]:
            self.specials += MultiReg(pads.cs_n, cs_n)

        # MOSI/MISO (Resynchronize + Tristate)
        if wires in [2, 3]:
            io = TSTriple()
            self.specials += io.get_tristate(pads.mosi)
            self.specials += MultiReg(io.i, mosi)
            self.comb += io.o.eq(miso)
            self.comb += io.oe.eq(miso_en)
        if wires in [4]:
            self.specials += MultiReg(pads.mosi, mosi)
            if with_tristate:
                self.specials += Tristate(pads.miso, miso, ~cs_n)
            else:
                self.comb += pads.miso.eq(miso)

        # Clk Edges Detection.
        # --------------------
        clk_d       = Signal()
        clk_negedge = Signal()
        clk_posedge = Signal()
        self.sync += clk_d.eq(clk)
        self.comb += clk_posedge.eq( clk & ~clk_d)
        self.comb += clk_negedge.eq(~clk &  clk_d)

        # Signals.
        # --------
        count   = Signal(8)
        offset  = Signal(5)
        synchro = Signal(8)
        command = Signal(8)
        address = Signal(32)
        data    = Signal(32)
        write   = Signal()

        # FSM.
        # ----
        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.submodules += fsm
        self.comb += fsm.reset.eq(cs_n)

        # Connect the Wishbone bus up to our datas.
        self.comb += [
            bus.adr.eq(address[2:]),
            bus.dat_w.eq(data),
            bus.sel.eq(2**len(bus.sel) - 1)
        ]

        # Constantly have the count increase, except when it's reset in the IDLE state.
        self.sync += [
            If(cs_n,
                count.eq(0)
            ).Elif(clk_posedge,
                count.eq(count + 1)
            )
        ]

        if wires in [2]:
            fsm.act("IDLE",
                miso_en.eq(0),
                NextValue(miso, 1),
                If(clk_posedge,
                    NextValue(synchro, Cat(mosi, synchro))
                ),
                If(synchro[0:7] == 0b101011,
                    NextState("GET-COMMAND"),
                    NextValue(count, 0),
                    NextValue(command, mosi)
                )
            )
        if wires in [3, 4]:
            fsm.act("IDLE",
                miso_en.eq(0),
                NextValue(miso, 1),
                If(clk_posedge,
                    NextState("GET-COMMAND"),
                    NextValue(command, mosi)
                )
            )

        # Determine if it's a read or a write
        fsm.act("GET-COMMAND",
            miso_en.eq(0),
            NextValue(miso, 1),
            If(count == 8,
                # Write data
                If(command == 0,
                    NextValue(write, 1),
                    NextState("GET-ADDRESS")

                # Read data
                ).Elif(command == 1,
                    NextValue(write, 0),
                    NextState("GET-ADDRESS")
                ).Else(
                    NextState("END")
                ),
            ),
            If(clk_posedge,
                NextValue(command, Cat(mosi, command))
            )
        )

        fsm.act("GET-ADDRESS",
            miso_en.eq(0),
            If(count == (32 + 8),
                If(write,
                    NextState("GET-DATA"),
                ).Else(
                    NextState("BUS-MMAP-READ"),
                )
            ),
            If(clk_posedge,
                NextValue(address, Cat(mosi, address))
            )
        )

        fsm.act("GET-DATA",
            miso_en.eq(0),
            If(count == (32 + 32 + 8),
                NextState("BUS-MMAP-WRITE"),
            ),
            If(clk_posedge,
                NextValue(data, Cat(mosi, data))
            )
        )

        fsm.act("BUS-MMAP-WRITE",
            bus.stb.eq(1),
            bus.we.eq(1),
            bus.cyc.eq(1),
            miso_en.eq(1),
            If(bus.ack | bus.err,
                NextState("WAIT-BYTE-BOUNDARY")
            )
        )

        fsm.act("BUS-MMAP-READ",
            bus.stb.eq(1),
            bus.we.eq(0),
            bus.cyc.eq(1),
            miso_en.eq(1),
            If(bus.ack | bus.err,
                NextState("WAIT-BYTE-BOUNDARY"),
                NextValue(data, bus.dat_r)
            )
        )

        fsm.act("WAIT-BYTE-BOUNDARY",
            miso_en.eq(1),
            If(clk_negedge,
                If(count[0:3] == 0,
                    NextValue(miso, 0),
                    # For writes, fill in the 0 byte response
                    If(write,
                        NextState("WRITE-WR-RESPONSE"),
                    ).Else(
                        NextState("WRITE-RESPONSE"),
                    )
                )
            )
        )

        # Write the "01" byte that indicates a response
        fsm.act("WRITE-RESPONSE",
            miso_en.eq(1),
            If(clk_negedge,
                If(count[0:3] == 0b111,
                    NextValue(miso, 1),
                ).Elif(count[0:3] == 0,
                    NextValue(offset, 31),
                    NextState("WRITE-DATA")
                )
            )
        )

        # Write the actual data
        fsm.act("WRITE-DATA",
            miso_en.eq(1),
            NextValue(miso, data >> offset),
            If(clk_negedge,
                NextValue(offset, offset - 1),
                If(offset == 0,
                    NextValue(miso, 0),
                    NextState("END")
                )
            )
        )

        fsm.act("WRITE-WR-RESPONSE",
            miso_en.eq(1),
            If(clk_negedge,
                If(count[0:3] == 0,
                    NextState("END")
                )
            )
        )

        if wires in [2]:
            fsm.act("END",
                miso_en.eq(0),
                NextValue(synchro, 0),
                NextState("IDLE")
            )
        if wires in [3, 4]:
            fsm.act("END",
                miso_en.eq(1)
            )
