#
# This file is part of LiteX.
#
# Copyright (c) 2019 Sean Cross <sean@xobs.io>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.specials import Tristate, TSTriple
from migen.genlib.cdc import MultiReg

from litex.soc.integration.doc import ModuleDoc, AutoDoc
from litex.soc.interconnect import wishbone, stream

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
        self.wishbone = wishbone.Interface()

        # # #
        self.__doc__ = self.__doc__.format(wires)
        if wires == 4:
            self.mod_doc = SPI4WireDocumentation()
        elif wires == 3:
            self.mod_doc = SPI3WireDocumentation()
        elif wires == 2:
            self.mod_doc = SPI2WireDocumentation()

        clk = Signal()
        cs_n = Signal()
        mosi = Signal()
        miso = Signal()
        miso_en = Signal()

        counter = Signal(8)
        write_offset = Signal(5)
        command = Signal(8)
        address = Signal(32)
        value   = Signal(32)
        wr      = Signal()
        sync_byte = Signal(8)

        self.specials += [
            MultiReg(pads.clk, clk),
        ]
        if wires == 2:
            io = TSTriple()
            self.specials += io.get_tristate(pads.mosi)
            self.specials += MultiReg(io.i, mosi)
            self.comb += io.o.eq(miso)
            self.comb += io.oe.eq(miso_en)
        elif wires == 3:
            self.specials += MultiReg(pads.cs_n, cs_n),
            io = TSTriple()
            self.specials += io.get_tristate(pads.mosi)
            self.specials += MultiReg(io.i, mosi)
            self.comb += io.o.eq(miso)
            self.comb += io.oe.eq(miso_en)
        elif wires == 4:
            self.specials += MultiReg(pads.cs_n, cs_n),
            self.specials += MultiReg(pads.mosi, mosi)
            if with_tristate:
                self.specials += Tristate(pads.miso, miso, ~cs_n)
            else:
                self.comb += pads.miso.eq(miso)
        else:
            raise ValueError("`wires` must be 2, 3, or 4")

        clk_last = Signal()
        clk_rising = Signal()
        clk_falling = Signal()
        self.sync += clk_last.eq(clk)
        self.comb += clk_rising.eq(clk & ~clk_last)
        self.comb += clk_falling.eq(~clk & clk_last)

        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.submodules += fsm
        self.comb += fsm.reset.eq(cs_n)

        # Connect the Wishbone bus up to our values
        self.comb += [
            self.wishbone.adr.eq(address[2:]),
            self.wishbone.dat_w.eq(value),
            self.wishbone.sel.eq(2**len(self.wishbone.sel) - 1)
        ]

        # Constantly have the counter increase, except when it's reset
        # in the IDLE state
        self.sync += If(cs_n, counter.eq(0)).Elif(clk_rising, counter.eq(counter + 1))

        if wires == 2:
            fsm.act("IDLE",
                miso_en.eq(0),
                NextValue(miso, 1),
                If(clk_rising,
                    NextValue(sync_byte, Cat(mosi, sync_byte))
                ),
                If(sync_byte[0:7] == 0b101011,
                    NextState("GET_TYPE_BYTE"),
                    NextValue(counter, 0),
                    NextValue(command, mosi),
                )
            )
        elif wires == 3 or wires == 4:
            fsm.act("IDLE",
                miso_en.eq(0),
                NextValue(miso, 1),
                If(clk_rising,
                    NextState("GET_TYPE_BYTE"),
                    NextValue(command, mosi),
                ),
            )
        else:
            raise ValueError("invalid `wires` count: {}".format(wires))

        # Determine if it's a read or a write
        fsm.act("GET_TYPE_BYTE",
            miso_en.eq(0),
            NextValue(miso, 1),
            If(counter == 8,
                # Write value
                If(command == 0,
                    NextValue(wr, 1),
                    NextState("READ_ADDRESS"),

                # Read value
                ).Elif(command == 1,
                    NextValue(wr, 0),
                    NextState("READ_ADDRESS"),
                ).Else(
                    NextState("END"),
                ),
            ),
            If(clk_rising,
                NextValue(command, Cat(mosi, command)),
            ),
        )

        fsm.act("READ_ADDRESS",
            miso_en.eq(0),
            If(counter == 32 + 8,
                If(wr,
                    NextState("READ_VALUE"),
                ).Else(
                    NextState("READ_WISHBONE"),
                )
            ),
            If(clk_rising,
                NextValue(address, Cat(mosi, address)),
            ),
        )

        fsm.act("READ_VALUE",
            miso_en.eq(0),
            If(counter == 32 + 32 + 8,
                NextState("WRITE_WISHBONE"),
            ),
            If(clk_rising,
                NextValue(value, Cat(mosi, value)),
            ),
        )

        fsm.act("WRITE_WISHBONE",
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(1),
            self.wishbone.cyc.eq(1),
            miso_en.eq(1),
            If(self.wishbone.ack | self.wishbone.err,
                NextState("WAIT_BYTE_BOUNDARY"),
            ),
        )

        fsm.act("READ_WISHBONE",
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(0),
            self.wishbone.cyc.eq(1),
            miso_en.eq(1),
            If(self.wishbone.ack | self.wishbone.err,
                NextState("WAIT_BYTE_BOUNDARY"),
                NextValue(value, self.wishbone.dat_r),
            ),
        )

        fsm.act("WAIT_BYTE_BOUNDARY",
            miso_en.eq(1),
            If(clk_falling,
                If(counter[0:3] == 0,
                    NextValue(miso, 0),
                    # For writes, fill in the 0 byte response
                    If(wr,
                        NextState("WRITE_WR_RESPONSE"),
                    ).Else(
                        NextState("WRITE_RESPONSE"),
                    ),
                ),
            ),
        )

        # Write the "01" byte that indicates a response
        fsm.act("WRITE_RESPONSE",
            miso_en.eq(1),
            If(clk_falling,
                If(counter[0:3] == 0b111,
                    NextValue(miso, 1),
                ).Elif(counter[0:3] == 0,
                    NextValue(write_offset, 31),
                    NextState("WRITE_VALUE")
                ),
            ),
        )

        # Write the actual value
        fsm.act("WRITE_VALUE",
            miso_en.eq(1),
            NextValue(miso, value >> write_offset),
            If(clk_falling,
                NextValue(write_offset, write_offset - 1),
                If(write_offset == 0,
                    NextValue(miso, 0),
                    NextState("END"),
                ),
            ),
        )

        fsm.act("WRITE_WR_RESPONSE",
            miso_en.eq(1),
            If(clk_falling,
                If(counter[0:3] == 0,
                    NextState("END"),
                ),
            ),
        )

        if wires == 3 or wires == 4:
            fsm.act("END",
                miso_en.eq(1),
            )
        elif wires == 2:
            fsm.act("END",
                miso_en.eq(0),
                NextValue(sync_byte, 0),
                NextState("IDLE")
            )
        else:
            raise ValueError("invalid `wires` count: {}".format(wires))
