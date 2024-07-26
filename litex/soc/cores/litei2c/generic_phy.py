#
# This file is part of LiteX.
#
# Copyright (c) 2024 Fin Maaß <f.maass@vogl-electronic.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.cores.litei2c.common import *
from litex.soc.cores.litei2c.clkgen import LiteI2CClkGen

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

from litex.build.io import SDRTristate

from litex.soc.integration.doc import AutoDoc

# LiteI2C PHY Core ---------------------------------------------------------------------------------

class LiteI2CPHYCore(Module, AutoCSR, AutoDoc):
    """LiteI2C PHY instantiator

    The ``LiteI2CPHYCore`` class provides a generic PHY that can be connected to the ``LiteI2C``.

    Parameters
    ----------
    pads : Object
        I2C pads description.

    clock_domain : str
        The clock domain for the ``LiteI2CPHYCore``.

    sys_clk_freq : int
        Frequency of the system clock.

    Attributes
    ----------
    source : Endpoint(i2c_phy2core_layout), out
        Data stream.

    sink : Endpoint(i2c_core2phy_layout), in
        Control stream.

    enable : Signal(), in
        Flash enable signal.

    speed_mode : CSRStorage
        Register which holds a clock divisor value applied to clkgen.
    """
    def __init__(self, pads, clock_domain, sys_clk_freq):
        self.source           = source = stream.Endpoint(i2c_phy2core_layout)
        self.sink             = sink   = stream.Endpoint(i2c_core2phy_layout)
        self.enable           = enable = Signal()
        self._i2c_speed_mode  = i2c_speed_mode = Signal(2)

        self.speed_mode      = speed_mode = CSRStorage(2, reset=0)

        # # #

        # Resynchronize CSR Clk Divisor to LiteI2C Clk Domain.
        self.submodules += ResyncReg(speed_mode.storage, i2c_speed_mode, clock_domain)

        # Clock Generator.
        self.submodules.clkgen = clkgen = LiteI2CClkGen(pads, i2c_speed_mode, sys_clk_freq)

        nack = Signal(reset_less=True)

        # SDA
        self.sda_o = sda_o  = Signal()
        self.sda_i = sda_i  = Signal()
        self.sda_oe = sda_oe = Signal()
        self.specials += SDRTristate(
            io = pads.sda,
            o  = Signal(),          # I2C uses Pull-ups, only drive low.
            oe = sda_oe & ~sda_o,   # Drive when oe and sda is low.
            i  = sda_i,
        )

        bytes_send = Signal(3, reset_less=True)
        bytes_recv = Signal(3, reset_less=True)

        tx_done = Signal(reset_less=True)

        # Data Shift Registers.

        sr_addr = Signal(7, reset_less=True)

        sr_cnt       = Signal(8, reset_less=True)
        sr_out_load  = Signal()
        sr_out_shift = Signal()
        sr_out       = Signal(len(sink.data), reset_less=True)
        sr_out_en    = Signal()
        sr_in_shift  = Signal()
        sr_in        = Signal(len(sink.data), reset_less=True)

        len_tx_capped = Signal(3)

        # Data Out Generation/Load/Shift.
        self.comb += [
            If(sr_out_en,
                sda_oe.eq(1),
                sda_o.eq(sr_out[-1:]),
            ),
            If(sink.len_tx > 4,
                len_tx_capped.eq(4),
            ).Else(
                len_tx_capped.eq(sink.len_tx),
            )
        ]
        self.sync += If(sr_out_load,
            sr_out.eq(sink.data << (len(sink.data) - len_tx_capped * 8)),
        )
        self.sync += If(sr_out_shift, sr_out.eq(Cat(Signal(1), sr_out)))

        # Data In Shift.
        self.sync += If(sr_in_shift, sr_in.eq(Cat(sda_i, sr_in)))

        # FSM.
        self.submodules.fsm = fsm = FSM(reset_state="WAIT-DATA")
        fsm.act("WAIT-DATA",
            NextValue(nack, 0),
            NextValue(tx_done, 0),
            # Wait for CS and a CMD from the Core.
            If(enable & sink.valid,
                # Start XFER.
                NextState("START"),
            ),
        )

        fsm.act("START",
            # Generate Clk.
            clkgen.en.eq(1),
            sda_oe.eq(1),
            sda_o.eq(0),
            NextValue(sr_addr, sink.addr),
            NextValue(sr_cnt, 0),
            If(clkgen.tx,
                If(sink.recover,
                    NextState("RECOVER-1"),
                ).Else(
                    NextState("ADDR"),
                ),
            ),
        )


        fsm.act("ADDR",
            # Generate Clk.
            clkgen.en.eq(1),
            sda_oe.eq(1),
            sda_o.eq(sr_addr[-1]),

            If(clkgen.tx,
               If(sr_cnt == 6,
                     NextState("ADDR-RW"),
                ).Else(
                     NextValue(sr_addr, sr_addr << 1),
                     NextValue(sr_cnt, sr_cnt + 1),
                ),
            ),
        )

        fsm.act("ADDR-RW",
            # Generate Clk.
            clkgen.en.eq(1),
            sda_oe.eq(1),

            If((sink.len_tx > 0) & ~tx_done,
                sda_o.eq(0),
            ).Elif(sink.len_rx > 0,
                sda_o.eq(1),
            ).Else(
                sda_o.eq(0),
            ),

            If(clkgen.tx,
                NextState("ADDR-ACK"),
            )
        )

        fsm.act("ADDR-ACK",
            # Generate Clk.
            clkgen.en.eq(1),
            sda_oe.eq(0),
            

            If(clkgen.rx,
               If(sda_i,
                     NextState("NACK-ERROR"),
                ).Else(
                    If((sink.len_tx > 0) & ~tx_done,
                        NextState("PRE-TX"),
                    ).Elif(sink.len_rx > 0,
                        NextState("PRE-RX"),
                    ).Else(
                        NextState("STOP-PRE"),
                    )
                ),
            )
        )



        fsm.act("PRE-TX",
            clkgen.en.eq(1),
            NextValue(sr_cnt, 0),
            NextValue(bytes_send, 0),
            sr_out_load.eq(1),
            If(clkgen.tx,
                NextState("TX"),
            ),
        )
                
        fsm.act("TX",
            # Generate Clk.
            clkgen.en.eq(1),
            sr_out_en.eq(1),

            # Data Out Shift.
            If(clkgen.tx,
               If(sr_cnt == 7,
                     NextValue(sr_cnt, 0),
                     NextState("TX-ACK"),
                     NextValue(bytes_send, bytes_send + 1),
                ).Else(
                     NextValue(sr_cnt, sr_cnt + 1),
                     sr_out_shift.eq(1),
                ),
            ),
        )

        fsm.act("TX-ACK",
            # Generate Clk.
            clkgen.en.eq(1),
            sr_out_en.eq(0),
            sda_oe.eq(0),
            

            If(clkgen.rx,
               If(sda_i,
                     NextState("NACK-ERROR"),
                ).Else(
                    If((bytes_send == 4) & (sink.len_tx > 4),
                        NextState("TX-PRE-WAIT"),
                    ).Elif(bytes_send < sink.len_tx,
                        NextState("TX-BEFORE-NEXT"),
                    ).Else(
                        NextValue(tx_done, 1),
                        If(sink.len_rx > 0,
                            NextState("REPEATED-START-1"),
                        ).Else(
                            NextState("STOP-PRE"),
                        ),
                    ),
                ),
            ),
        )

        fsm.act

        fsm.act("TX-BEFORE-NEXT",
            # Generate Clk.
            clkgen.en.eq(1),
            If(clkgen.tx,
               sr_out_shift.eq(1),
               NextState("TX"),
            ),
        )

        fsm.act("TX-PRE-WAIT",
            # Generate Clk.
            clkgen.en.eq(1),
            sink.ready.eq(1),
            If(clkgen.tx,
               NextState("TX-WAIT-SEND-STATUS"),
            ),
        )

        fsm.act("TX-WAIT-SEND-STATUS",
            # Generate Clk.
            clkgen.en.eq(0),
            clkgen.keep_low.eq(1),
            source.unfinished_tx.eq(1),
            source.valid.eq(1),
            source.last.eq(1),
            If(source.ready,
                NextState("TX-WAIT"),
            )
        )

        fsm.act("TX-WAIT",
            # Generate Clk.
            clkgen.en.eq(0),
            clkgen.keep_low.eq(1),
            NextValue(tx_done, 0),
            If(enable & sink.valid,
               NextState("PRE-TX"),
            ),
        )

        fsm.act("NACK-ERROR",
            clkgen.en.eq(1),
            NextValue(nack, 1),

            If(clkgen.tx,
                NextState("STOP"),
            ),       
        )

        fsm.act("REPEATED-START-1",
            # Generate Clk.
            clkgen.en.eq(1),
            
            If(clkgen.tx,
                NextState("REPEATED-START-2"),
            ),
        )

        fsm.act("REPEATED-START-2",
            # Generate Clk.
            clkgen.en.eq(1),
            sda_oe.eq(1),
            sda_o.eq(1),
            If(clkgen.rx,
                NextState("START"),
            ),
        )

        fsm.act("PRE-RX",
            clkgen.en.eq(1),
            NextValue(sr_cnt, 0),
            NextValue(bytes_recv, 0),
            NextValue(sr_in, 0),
            If(clkgen.tx,
                NextState("RX"),
            ),
        )

        fsm.act("RX",
            # Generate Clk.
            clkgen.en.eq(1),

            If(clkgen.rx,
                NextValue(sr_cnt, sr_cnt + 1),
                sr_in_shift.eq(1),
                If(sr_cnt == 7,
                     NextValue(sr_cnt, 0),
                     NextValue(bytes_recv, bytes_recv + 1),
                     NextState("RX-PRE-ACK"),
                ),
            ),

        )

        fsm.act("RX-PRE-ACK",
            # Generate Clk.
            clkgen.en.eq(1),

            If(clkgen.tx,
                If(bytes_recv < sink.len_rx,
                    NextState("RX-ACK"),
                ).Else(
                    NextState("RX-NACK"),
                ),
            ),
        )

        fsm.act("RX-ACK",
            # Generate Clk.
            clkgen.en.eq(1),
            sda_oe.eq(1),
            sda_o.eq(0),
            

            If(clkgen.tx,
                NextValue(sr_cnt, 0),
                If(bytes_recv == 4,
                   sink.ready.eq(1),
                   NextState("RX-WAIT-SEND-STATUS"),
                ).Else(
                    NextState("RX"),
                ),
            ),
        )

        fsm.act("RX-NACK",
            # Generate Clk.
            clkgen.en.eq(1),
            sda_oe.eq(1),
            sda_o.eq(1),
            

            If(clkgen.tx,
                NextState("STOP"),
            ),
        )

        fsm.act("RX-WAIT-SEND-STATUS",
            # Generate Clk.
            clkgen.en.eq(0),
            clkgen.keep_low.eq(1),
            source.data.eq(sr_in),
            source.unfinished_rx.eq(1),
            source.valid.eq(1),
            source.last.eq(1),
            If(source.ready,
                NextState("RX-WAIT"),
            )
        )

        fsm.act("RX-WAIT",
            # Generate Clk.
            clkgen.en.eq(0),
            clkgen.keep_low.eq(1),
            If(enable & sink.valid,
                NextState("PRE-RX"),
            ),
        )

        fsm.act("STOP-PRE",
            # Generate Clk.
            clkgen.en.eq(1),

            If(clkgen.tx,
                NextState("STOP"),
            ),
        )

        fsm.act("STOP",
            # Generate Clk.
            clkgen.en.eq(1),

            sda_oe.eq(1),
        
            If(clkgen.rx,
                sda_o.eq(1),
                NextState("XFER-END"),
            ).Else( 
                sda_o.eq(0),
            )
        )

        fsm.act("XFER-END",
            # Accept CMD.
            sink.ready.eq(1),
            sda_oe.eq(1),
            sda_o.eq(1),
            # Send Status/Data to Core.
            NextState("SEND-STATUS-DATA"),
        )
      
        fsm.act("SEND-STATUS-DATA",
            # Send Data In to Core and return to WAIT when accepted.
            sda_oe.eq(1),
            sda_o.eq(1),
            source.data.eq(sr_in),
            source.nack.eq(nack),
            source.valid.eq(1),
            source.last.eq(1),
            If(source.ready,
                NextState("WAIT-DATA"),
            )
        )

        fsm.act("RECOVER-1",
            # Generate Clk.
            clkgen.en.eq(1),
            sda_oe.eq(1),
            sda_o.eq(1),
            If(sr_cnt < 9,
                If(clkgen.tx,
                    NextValue(sr_cnt, sr_cnt + 1),
                ),
            ).Elif(clkgen.rx,
                NextState("RECOVER-2"),
            ),
        )

        fsm.act("RECOVER-2",
            # Generate Clk.
            clkgen.en.eq(1),
            sda_oe.eq(1),
            sda_o.eq(0),
            If(clkgen.tx,
                NextState("STOP"),
            ),
        )
