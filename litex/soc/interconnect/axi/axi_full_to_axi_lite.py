#
# This file is part of LiteX.
#
# Copyright (c) 2018-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""AXI4-Full/Lite support for LiteX"""

from migen import *

from litex.soc.interconnect import stream

from litex.soc.interconnect.axi.axi_common import *
from litex.soc.interconnect.axi.axi_lite import *
from litex.soc.interconnect.axi.axi_full import *

# AXI to AXI-Lite ----------------------------------------------------------------------------------

class AXI2AXILite(Module):
    # Note: Since this AXI bridge will mostly be used to target buses that are not supporting
    # simultaneous writes/reads, to reduce ressource usage the AXIBurst2Beat module is shared
    # between writes/reads.
    def __init__(self, axi, axi_lite):
        assert axi.data_width    == axi_lite.data_width
        assert axi.address_width == axi_lite.address_width

        ax_burst = AXIStreamInterface(layout=ax_description(axi.address_width), id_width=axi.id_width)
        ax_beat  = AXIStreamInterface(layout=ax_description(axi.address_width), id_width=axi.id_width)
        ax_buffer = stream.Buffer(ax_burst.description)

        self.comb += ax_burst.connect(ax_buffer.sink)
        ax_burst2beat = AXIBurst2Beat(ax_buffer.source, ax_beat)
        self.submodules += ax_buffer, ax_burst2beat

        _data         = Signal(axi.data_width)
        _cmd_done     = Signal()
        _last_ar_aw_n = Signal()

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            NextValue(_cmd_done, 0),
            If(axi.ar.valid & axi.aw.valid,
                # If last access was a read, do a write
                If(_last_ar_aw_n,
                    axi.aw.connect(ax_burst),
                    NextValue(_last_ar_aw_n, 0),
                    NextState("WRITE")
                # If last access was a write, do a read
                ).Else(
                    axi.ar.connect(ax_burst),
                    NextValue(_last_ar_aw_n, 1),
                    NextState("READ"),
                )
            ).Elif(axi.ar.valid,
                axi.ar.connect(ax_burst),
                NextValue(_last_ar_aw_n, 1),
                NextState("READ"),
            ).Elif(axi.aw.valid,
                axi.aw.connect(ax_burst),
                NextValue(_last_ar_aw_n, 0),
                NextState("WRITE")
            )
        )
        fsm.act("READ",
            # ar (read command)
            axi_lite.ar.valid.eq(ax_beat.valid & ~_cmd_done),
            axi_lite.ar.addr.eq(ax_beat.addr),
            ax_beat.ready.eq(axi_lite.ar.ready & ~_cmd_done),
            If(ax_beat.valid & ax_beat.last,
                If(axi_lite.ar.ready,
                    ax_beat.ready.eq(0),
                    NextValue(_cmd_done, 1)
                )
            ),
            # r (read data & response)
            axi.r.valid.eq(axi_lite.r.valid),
            axi.r.last.eq(_cmd_done),
            axi.r.resp.eq(RESP_OKAY),
            axi.r.id.eq(ax_beat.id),
            axi.r.data.eq(axi_lite.r.data),
            axi_lite.r.ready.eq(axi.r.ready),
            # Exit
            If(axi.r.valid & axi.r.last & axi.r.ready,
                ax_beat.ready.eq(1),
                NextState("IDLE")
            )
        )
        # Always accept write responses.
        self.comb += axi_lite.b.ready.eq(1)
        fsm.act("WRITE",
            # aw (write command)
            axi_lite.aw.valid.eq(ax_beat.valid & ~_cmd_done),
            axi_lite.aw.addr.eq(ax_beat.addr),
            ax_beat.ready.eq(axi_lite.aw.ready & ~_cmd_done),
            If(ax_beat.valid & ax_beat.last,
                If(axi_lite.aw.ready,
                    ax_beat.ready.eq(0),
                    NextValue(_cmd_done, 1)
                )
            ),
            # w (write data)
            axi_lite.w.valid.eq(axi.w.valid),
            axi_lite.w.data.eq(axi.w.data),
            axi_lite.w.strb.eq(axi.w.strb),
            axi.w.ready.eq(axi_lite.w.ready),
            # Exit
            If(axi.w.valid & axi.w.last & axi.w.ready,
                NextState("WRITE-RESP")
            )
        )
        fsm.act("WRITE-RESP",
            axi.b.valid.eq(1),
            axi.b.resp.eq(RESP_OKAY),
            axi.b.id.eq(ax_beat.id),
            If(axi.b.ready,
                ax_beat.ready.eq(1),
                NextState("IDLE")
            )
        )

# AXI-Lite to AXI ----------------------------------------------------------------------------------

class AXILite2AXI(Module):
    def __init__(self, axi_lite, axi, write_id=0, read_id=0, prot=0, burst_type="INCR"):
        assert isinstance(axi_lite, AXILiteInterface)
        assert isinstance(axi, AXIInterface)
        assert axi_lite.data_width == axi.data_width
        assert axi_lite.address_width == axi.address_width

        # n bytes, encoded as log2(n)
        burst_size = log2_int(axi.data_width // 8)
        # Burst type has no meaning as we use burst length of 1, but AXI slaves may require certain
        # type of bursts, so it is probably safest to use INCR in general.
        burst_type = {
            "FIXED": 0b00,
            "INCR":  0b01,
            "WRAP":  0b10,
        }[burst_type]

        self.comb += [
            # aw (write command)
            axi.aw.valid.eq(axi_lite.aw.valid),
            axi_lite.aw.ready.eq(axi.aw.ready),
            axi.aw.addr.eq(axi_lite.aw.addr),
            axi.aw.burst.eq(burst_type),
            axi.aw.len.eq(0),  # 1 transfer per burst
            axi.aw.size.eq(burst_size),
            axi.aw.lock.eq(0),  # Normal access
            axi.aw.prot.eq(prot),
            axi.aw.cache.eq(0b0011),  # Normal Non-cacheable Bufferable
            axi.aw.qos.eq(0),
            axi.aw.id.eq(write_id),

            # w (write data)
            axi.w.valid.eq(axi_lite.w.valid),
            axi_lite.w.ready.eq(axi.w.ready),
            axi.w.data.eq(axi_lite.w.data),
            axi.w.strb.eq(axi_lite.w.strb),
            axi.w.last.eq(1),

            # b (write response)
            axi_lite.b.valid.eq(axi.b.valid),
            axi_lite.b.resp.eq(axi.b.resp),
            axi.b.ready.eq(axi_lite.b.ready),

            # ar (read command)
            axi.ar.valid.eq(axi_lite.ar.valid),
            axi_lite.ar.ready.eq(axi.ar.ready),
            axi.ar.addr.eq(axi_lite.ar.addr),
            axi.ar.burst.eq(burst_type),
            axi.ar.len.eq(0),
            axi.ar.size.eq(burst_size),
            axi.ar.lock.eq(0),
            axi.ar.prot.eq(prot),
            axi.ar.cache.eq(0b0011),
            axi.ar.qos.eq(0),
            axi.ar.id.eq(read_id),

            # r (read response & data)
            axi_lite.r.valid.eq(axi.r.valid),
            axi_lite.r.resp.eq(axi.r.resp),
            axi_lite.r.data.eq(axi.r.data),
            axi.r.ready.eq(axi_lite.r.ready),
        ]
