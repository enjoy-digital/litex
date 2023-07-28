#
# This file is part of LiteX.
#
# Copyright (c) 2018-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""AXI4-Full/Lite support for LiteX"""

from migen import *

from litex.gen import *

from litex.soc.interconnect.axi.axi_lite import *

# AXI-Lite to Wishbone -----------------------------------------------------------------------------

class AXILite2Wishbone(LiteXModule):
    def __init__(self, axi_lite, wishbone, base_address=0x00000000):
        wishbone_adr_shift = log2_int(axi_lite.data_width//8)
        assert axi_lite.data_width    == len(wishbone.dat_r)
        assert axi_lite.address_width == len(wishbone.adr) + wishbone_adr_shift

        _data         = Signal(axi_lite.data_width)
        _r_addr       = Signal(axi_lite.address_width)
        _w_addr       = Signal(axi_lite.address_width)
        _last_ar_aw_n = Signal()
        self.comb += _r_addr.eq(axi_lite.ar.addr - base_address)
        self.comb += _w_addr.eq(axi_lite.aw.addr - base_address)

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(axi_lite.ar.valid & axi_lite.aw.valid,
                # If last access was a read, do a write
                If(_last_ar_aw_n,
                    NextValue(_last_ar_aw_n, 0),
                    NextState("DO-WRITE")
                # If last access was a write, do a read
                ).Else(
                    NextValue(_last_ar_aw_n, 1),
                    NextState("DO-READ")
                )
            ).Elif(axi_lite.ar.valid,
                NextValue(_last_ar_aw_n, 1),
                NextState("DO-READ")
            ).Elif(axi_lite.aw.valid,
                NextValue(_last_ar_aw_n, 0),
                NextState("DO-WRITE")
            )
        )
        fsm.act("DO-READ",
            wishbone.stb.eq(1),
            wishbone.cyc.eq(1),
            wishbone.adr.eq(_r_addr[wishbone_adr_shift:]),
            wishbone.sel.eq(2**len(wishbone.sel) - 1),
            If(wishbone.ack,
                axi_lite.ar.ready.eq(1),
                NextValue(_data, wishbone.dat_r),
                NextState("SEND-READ-RESPONSE")
            )
        )
        fsm.act("SEND-READ-RESPONSE",
            axi_lite.r.valid.eq(1),
            axi_lite.r.resp.eq(RESP_OKAY),
            axi_lite.r.data.eq(_data),
            If(axi_lite.r.ready,
                NextState("IDLE")
            )
        )
        fsm.act("DO-WRITE",
            wishbone.stb.eq(axi_lite.w.valid),
            wishbone.cyc.eq(axi_lite.w.valid),
            wishbone.we.eq(1),
            wishbone.adr.eq(_w_addr[wishbone_adr_shift:]),
            wishbone.sel.eq(axi_lite.w.strb),
            wishbone.dat_w.eq(axi_lite.w.data),
            If(wishbone.ack,
                axi_lite.aw.ready.eq(1),
                axi_lite.w.ready.eq(1),
                NextState("SEND-WRITE-RESPONSE")
            )
        )
        fsm.act("SEND-WRITE-RESPONSE",
            axi_lite.b.valid.eq(1),
            axi_lite.b.resp.eq(RESP_OKAY),
            If(axi_lite.b.ready,
                NextState("IDLE")
            )
        )

# Wishbone to AXI-Lite -----------------------------------------------------------------------------

class Wishbone2AXILite(LiteXModule):
    def __init__(self, wishbone, axi_lite, base_address=0x00000000):
        wishbone_adr_shift = log2_int(axi_lite.data_width//8)
        assert axi_lite.data_width    == len(wishbone.dat_r)
        assert axi_lite.address_width == len(wishbone.adr) + wishbone_adr_shift

        _cmd_done  = Signal()
        _data_done = Signal()
        _addr      = Signal(len(wishbone.adr))
        self.comb += _addr.eq(wishbone.adr - base_address//4)

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            NextValue(_cmd_done,  0),
            NextValue(_data_done, 0),
            If(wishbone.stb & wishbone.cyc,
                If(wishbone.we,
                    NextState("WRITE")
                ).Else(
                    NextState("READ")
                )
            )
        )
        fsm.act("WRITE",
            # aw (write command)
            axi_lite.aw.valid.eq(~_cmd_done),
            axi_lite.aw.addr[wishbone_adr_shift:].eq(_addr),
            If(axi_lite.aw.valid & axi_lite.aw.ready,
                NextValue(_cmd_done, 1)
            ),
            # w (write data)
            axi_lite.w.valid.eq(~_data_done),
            axi_lite.w.data.eq(wishbone.dat_w),
            axi_lite.w.strb.eq(wishbone.sel),
            If(axi_lite.w.valid & axi_lite.w.ready,
                NextValue(_data_done, 1),
            ),
            # b (write response)
            axi_lite.b.ready.eq(_cmd_done & _data_done),
            If(axi_lite.b.valid & axi_lite.b.ready,
                If(axi_lite.b.resp == RESP_OKAY,
                    wishbone.ack.eq(1),
                    NextState("IDLE")
                ).Else(
                    NextState("ERROR")
                )
            )
        )
        fsm.act("READ",
            # ar (read command)
            axi_lite.ar.valid.eq(~_cmd_done),
            axi_lite.ar.addr[wishbone_adr_shift:].eq(_addr),
            If(axi_lite.ar.valid & axi_lite.ar.ready,
                NextValue(_cmd_done, 1)
            ),
            # r (read data & response)
            axi_lite.r.ready.eq(_cmd_done),
            If(axi_lite.r.valid & axi_lite.r.ready,
                If(axi_lite.r.resp == RESP_OKAY,
                    wishbone.dat_r.eq(axi_lite.r.data),
                    wishbone.ack.eq(1),
                    NextState("IDLE"),
                ).Else(
                    NextState("ERROR")
                )
            )
        )
        fsm.act("ERROR",
            wishbone.ack.eq(1),
            wishbone.err.eq(1),
            NextState("IDLE")
        )
