#
# This file is part of LiteX.
#
# Copyright (c) 2018-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""AXI4-Full/Lite support for LiteX"""

from math import log2

from migen import *
from migen.genlib import roundrobin

from litex.gen import *
from litex.gen.genlib.misc import WaitTimer

from litex.build.generic_platform import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.axi.axi_common import *
from litex.soc.interconnect.axi.axi_stream import AXIStreamInterface

# AXI Definition -----------------------------------------------------------------------------------

def ax_description(address_width, version="axi4"):
    len_width  = {"axi3":4, "axi4":8}[version]
    lock_width = {"axi3":2, "axi4":1}[version]
    # * present for interconnect with others cores but not used by LiteX.
    return [
        ("addr",   address_width),   # Address Width.
        ("burst",  2),               # Burst type.
        ("len",    len_width),       # Number of data (-1) transfers (up to 16 (AXI3) or 256 (AXI4)).
        ("size",   3),               # Number of bytes (-1) of each data transfer (up to 1024-bit).
        ("lock",   lock_width),      # *
        ("prot",   3),               # *
        ("cache",  4),               # *
        ("qos",    4),               # *
        ("region", 4),               # *
    ]

def w_description(data_width):
    return [
        ("data", data_width),
        ("strb", data_width//8),
    ]

def b_description():
    return [("resp", 2)]

def r_description(data_width):
    return [
        ("resp", 2),
        ("data", data_width),
    ]

class AXIInterface:
    def __init__(self, data_width=32, address_width=32, addressing="byte", id_width=1, version="axi4", clock_domain="sys",
        name          = None,
        bursting      = False,
        aw_user_width = 0,
        w_user_width  = 0,
        b_user_width  = 0,
        ar_user_width = 0,
        r_user_width  = 0,
        mode          = "rw"
    ):
        # Parameters checks.
        # ------------------
        assert data_width in [8, 16, 32, 64, 128, 256, 512, 1024]
        assert addressing in ["byte"]
        assert version    in ["axi3", "axi4"]
        assert mode in ["rw", "r", "w"]

        # Parameters.
        # -----------
        self.data_width    = data_width
        self.address_width = address_width
        self.addressing    = addressing
        self.id_width      = id_width
        self.version       = version
        self.clock_domain  = clock_domain
        self.bursting      = bursting # FIXME: Use or add check.
        self.mode          = mode

        # Write Channels.
        # ---------------
        self.aw = AXIStreamInterface(name=name,
            layout     = ax_description(address_width=address_width, version=version),
            id_width   = id_width,
            user_width = aw_user_width
        )
        self.w = AXIStreamInterface(name=name,
            layout     = w_description(data_width),
            id_width   = {"axi4":0,"axi3":id_width}[version], # No WID on AXI4.
            user_width = w_user_width
        )
        self.b = AXIStreamInterface(name=name,
            layout     = b_description(),
            id_width   = id_width,
            user_width = b_user_width
        )

        # Read Channels.
        # --------------
        self.ar = AXIStreamInterface(name=name,
            layout     = ax_description(address_width=address_width, version=version),
            id_width   = id_width,
            user_width = ar_user_width
        )
        self.r = AXIStreamInterface(name=name,
            layout     = r_description(data_width),
            id_width   = id_width,
            user_width = r_user_width
        )

    def connect_to_pads(self, pads, mode="master"):
        return connect_to_pads(self, pads, mode, axi_full=True)

    def get_ios(self, bus_name="wb"):
        subsignals = []
        for channel in ["aw", "w", "b", "ar", "r"]:
            # Control Signals.
            for name in ["valid", "ready"] + (["last"] if channel in ["w", "r"] else []):
                subsignals.append(Subsignal(channel + name, Pins(1)))

            # Payload/Params Signals.
            channel_layout = (getattr(self, channel).description.payload_layout +
                              getattr(self, channel).description.param_layout)
            for name, width in channel_layout:
                if (name == "dest"):
                    continue # No DEST.
                if (channel == "w") and (name == "id") and (self.version == "axi4"):
                    continue # No WID on AXI4.
                subsignals.append(Subsignal(channel + name, Pins(width)))
        ios = [(bus_name , 0) + tuple(subsignals)]
        return ios

    def connect(self, slave, **kwargs):
        return connect_axi(self, slave, axi_full=True, **kwargs)

    def connect_mapped(self, slave, map_fct):
        comb = []
        comb += self.connect(slave, omit={"addr"})
        comb += [slave.ar.addr.eq(map_fct(self.ar.addr))]
        comb += [slave.aw.addr.eq(map_fct(self.aw.addr))]
        return comb

    def layout_flat(self):
        return list(axi_layout_flat(self, axi_full=True))

# AXI Remapper -------------------------------------------------------------------------------------

class AXIRemapper(LiteXModule):
    """Remaps AXI addresses by applying an origin offset and address mask."""
    def __init__(self, master, slave, origin=0, size=None):
        # Mask.
        if size is None:
            size = 2**master.address_width
        mask = 2**int(log2(size)) - 1

        # Address Mask and Shift.
        self.comb += master.connect(slave)
        self.comb += slave.aw.addr.eq(origin | master.aw.addr & mask)
        self.comb += slave.ar.addr.eq(origin | master.ar.addr & mask)

# AXI Offset ---------------------------------------------------------------------------------------

class AXIOffset(LiteXModule):
    """Removes offset from AXI addresses."""
    def __init__(self, master, slave, offset=0x00000000):

        # Address Mask and Shift.
        self.comb += master.connect(slave)
        self.comb += slave.aw.addr.eq(master.aw.addr - offset)
        self.comb += slave.ar.addr.eq(master.ar.addr - offset)

# AXI Bursts to Beats ------------------------------------------------------------------------------

class AXIBurst2Beat(LiteXModule):
    def __init__(self, ax_burst, ax_beat, capabilities={BURST_FIXED, BURST_INCR, BURST_WRAP}):
        assert BURST_FIXED in capabilities

        # # #

        beat_count  = Signal(8)
        beat_size   = Signal(8 + 4)
        beat_offset = Signal((8 + 4 + 1, True))
        beat_wrap   = Signal(8 + 4)

        # Compute parameters
        self.comb += beat_size.eq(1 << ax_burst.size)
        self.comb += beat_wrap.eq(ax_burst.len << ax_burst.size)

        # Combinatorial logic
        self.comb += [
            ax_beat.valid.eq(ax_burst.valid | ~ax_beat.first),
            ax_beat.first.eq(beat_count == 0),
            ax_beat.last.eq(beat_count == ax_burst.len),
            ax_beat.addr.eq(ax_burst.addr + beat_offset),
            ax_beat.id.eq(ax_burst.id),
            If(ax_beat.ready,
                If(ax_beat.last,
                    ax_burst.ready.eq(1)
                )
            )
        ]

        # Synchronous logic
        self.sync += [
            If(ax_beat.valid & ax_beat.ready,
                If(ax_beat.last,
                    beat_count.eq(0),
                    beat_offset.eq(0)
                ).Else(
                    beat_count.eq(beat_count + 1),
                    If(((ax_burst.burst == BURST_INCR) & (BURST_INCR in capabilities)) |
                       ((ax_burst.burst == BURST_WRAP) & (BURST_WRAP in capabilities)),
                        beat_offset.eq(beat_offset + beat_size)
                    )
                ),
                If((ax_burst.burst == BURST_WRAP) & (BURST_WRAP in capabilities),
                    If((ax_beat.addr & beat_wrap) == beat_wrap,
                        beat_offset.eq(beat_offset - beat_wrap)
                    )
                )
            )
        ]

# AXI Data-Width Converter -------------------------------------------------------------------------

class AXIUpConverter(LiteXModule):
    def __init__(self, axi_from, axi_to):
        dw_from  = len(axi_from.r.data)
        dw_to    = len(axi_to.r.data)
        ratio    = int(dw_to//dw_from)
        assert dw_from*ratio == dw_to

        # # #

        # Note: Assuming size of "axi_from" burst >= "axi_to" data_width.

        # Write path -------------------------------------------------------------------------------

        # AW Channel.
        self.comb += [
            axi_from.aw.connect(axi_to.aw, omit={"len", "size"}),
            axi_to.aw.len.eq( axi_from.aw.len >> log2_int(ratio)),
            axi_to.aw.size.eq(axi_from.aw.size + log2_int(ratio)),
        ]

        # W Channel.
        w_converter = stream.StrideConverter(
            description_from = [("data", dw_from), ("strb", dw_from//8)],
            description_to   = [("data",   dw_to), ("strb",   dw_to//8)],
        )
        self.submodules += w_converter
        self.comb += axi_from.w.connect(w_converter.sink, omit={"id", "dest", "user"})
        self.comb += w_converter.source.connect(axi_to.w)
        self.comb += axi_to.w.id.eq(axi_from.w.id)
        self.comb += axi_to.w.dest.eq(axi_from.w.dest)
        self.comb += axi_to.w.user.eq(axi_from.w.user)

        # B Channel.
        self.comb += axi_to.b.connect(axi_from.b)

        # Read path --------------------------------------------------------------------------------

        # AR Channel.
        self.comb += [
            axi_from.ar.connect(axi_to.ar, omit={"len", "size"}),
            axi_to.ar.len.eq( axi_from.ar.len >> log2_int(ratio)),
            axi_to.ar.size.eq(axi_from.ar.size + log2_int(ratio)),
        ]

        # R Channel.
        r_converter = stream.StrideConverter(
            description_from = [("data",   dw_to)],
            description_to   = [("data", dw_from)],
        )
        self.submodules += r_converter
        self.comb += axi_to.r.connect(r_converter.sink, omit={"id", "dest", "user", "resp"})
        self.comb += r_converter.source.connect(axi_from.r)
        self.comb += axi_from.r.resp.eq(axi_to.r.resp)
        self.comb += axi_from.r.id.eq(axi_to.r.id)
        self.comb += axi_from.r.user.eq(axi_to.r.user)
        self.comb += axi_from.r.dest.eq(axi_to.r.dest)

class AXIDownConverter(LiteXModule):
    """AXI4-Full data-width down-converter.

    Reduces the data width of an AXI4 master from `dw_from` to `dw_to` (with `dw_from > dw_to`,
    integer multiple). The master sees full AXI4 semantics including bursts of any type
    (FIXED, INCR, WRAP).

    INCR/WRAP/FIXED-1 take the cheap combinational fast path: 1 wide AW becomes 1 narrow AW with
    `len*ratio - 1`, and the W/R streams use a `StrideConverter` to split/merge data ratio:1.

    FIXED bursts of length > 1 (every wide beat targets the same address X) cannot be expressed
    as a single narrow AXI4 burst — neither narrow-INCR (marches forward) nor narrow-FIXED
    (would only write the bottom bytes) preserves the semantics. So they take a slower FSM path
    that issues `len + 1` separate narrow INCR-`ratio` bursts back-to-back, all at the captured
    wide address. The W stream's `last` is overridden to fire every ratio-th narrow beat, the
    R stream's `last` is overridden to fire only on the final wide beat, and the L narrow B
    responses are coalesced into a single wide B (worst-resp wins).
    """
    def __init__(self, axi_from, axi_to):
        dw_from  = len(axi_from.r.data)
        dw_to    = len(axi_to.r.data)
        ratio    = int(dw_from//dw_to)
        assert dw_from == dw_to*ratio

        wide_size_log2   = log2_int(dw_from // 8)
        narrow_size_log2 = log2_int(dw_to   // 8)

        # ==========================================================================================
        # Write path: AW / W / B
        # ==========================================================================================

        # Captures (FIXED-multi-beat path).
        cap_aw_addr   = Signal.like(axi_from.aw.addr)
        cap_aw_len    = Signal.like(axi_from.aw.len)
        cap_aw_size   = Signal.like(axi_from.aw.size)
        cap_aw_id     = Signal.like(axi_from.aw.id)
        cap_aw_lock   = Signal.like(axi_from.aw.lock)
        cap_aw_prot   = Signal.like(axi_from.aw.prot)
        cap_aw_cache  = Signal.like(axi_from.aw.cache)
        cap_aw_qos    = Signal.like(axi_from.aw.qos)
        cap_aw_region = Signal.like(axi_from.aw.region)

        aw_emit_count    = Signal.like(axi_from.aw.len)
        b_collect_count  = Signal.like(axi_from.aw.len)
        b_collected_resp = Signal(2)
        w_subbeat_count  = Signal(max=max(ratio, 2))

        fixed_aw_active = Signal()  # asserted while AW FSM is in any FIXED-* state.

        is_aw_fixed = (axi_from.aw.burst == BURST_FIXED) & (axi_from.aw.len != 0)

        aw_fsm = FSM(reset_state="IDLE")
        self.aw_fsm = aw_fsm

        aw_fsm.act("IDLE",
            If(~is_aw_fixed,
                # Fast path: combinational forward with len/size/burst conversion.
                axi_to.aw.valid.eq(axi_from.aw.valid),
                axi_to.aw.addr.eq(axi_from.aw.addr),
                axi_to.aw.addr[:wide_size_log2].eq(0),
                axi_to.aw.len.eq(((axi_from.aw.len + 1) << log2_int(ratio)) - 1),
                If(axi_from.aw.size <= narrow_size_log2,
                    axi_to.aw.size.eq(axi_from.aw.size),
                ).Else(
                    axi_to.aw.size.eq(narrow_size_log2),
                ),
                Case(axi_from.aw.burst, {
                    BURST_FIXED:    axi_to.aw.burst.eq(BURST_INCR),  # FIXED-1 = single beat = INCR.
                    BURST_INCR:     axi_to.aw.burst.eq(BURST_INCR),
                    BURST_WRAP:     axi_to.aw.burst.eq(BURST_WRAP),
                    BURST_RESERVED: axi_to.aw.burst.eq(BURST_RESERVED),
                }),
                axi_to.aw.id.eq(axi_from.aw.id),
                axi_to.aw.lock.eq(axi_from.aw.lock),
                axi_to.aw.prot.eq(axi_from.aw.prot),
                axi_to.aw.cache.eq(axi_from.aw.cache),
                axi_to.aw.qos.eq(axi_from.aw.qos),
                axi_to.aw.region.eq(axi_from.aw.region),
                axi_to.aw.dest.eq(axi_from.aw.dest),
                axi_to.aw.user.eq(axi_from.aw.user),
                axi_from.aw.ready.eq(axi_to.aw.ready),
            ).Else(
                # Slow path: capture wide AW and switch to FIXED handling.
                axi_from.aw.ready.eq(1),
                If(axi_from.aw.valid,
                    NextValue(cap_aw_addr,   axi_from.aw.addr),
                    NextValue(cap_aw_len,    axi_from.aw.len),
                    NextValue(cap_aw_size,   axi_from.aw.size),
                    NextValue(cap_aw_id,     axi_from.aw.id),
                    NextValue(cap_aw_lock,   axi_from.aw.lock),
                    NextValue(cap_aw_prot,   axi_from.aw.prot),
                    NextValue(cap_aw_cache,  axi_from.aw.cache),
                    NextValue(cap_aw_qos,    axi_from.aw.qos),
                    NextValue(cap_aw_region, axi_from.aw.region),
                    NextValue(aw_emit_count,    0),
                    NextValue(b_collect_count,  0),
                    NextValue(b_collected_resp, RESP_OKAY),
                    NextState("FIXED-EMIT-AW"),
                )
            )
        )
        aw_fsm.act("FIXED-EMIT-AW",
            fixed_aw_active.eq(1),
            axi_to.aw.valid.eq(1),
            axi_to.aw.addr.eq(cap_aw_addr),
            axi_to.aw.addr[:wide_size_log2].eq(0),
            axi_to.aw.len.eq(ratio - 1),
            axi_to.aw.burst.eq(BURST_INCR),
            If(cap_aw_size <= narrow_size_log2,
                axi_to.aw.size.eq(cap_aw_size),
            ).Else(
                axi_to.aw.size.eq(narrow_size_log2),
            ),
            axi_to.aw.id.eq(cap_aw_id),
            axi_to.aw.lock.eq(cap_aw_lock),
            axi_to.aw.prot.eq(cap_aw_prot),
            axi_to.aw.cache.eq(cap_aw_cache),
            axi_to.aw.qos.eq(cap_aw_qos),
            axi_to.aw.region.eq(cap_aw_region),
            # Drive b.ready so the previous burst's response is drained while we (re-)emit AW.
            If(axi_to.aw.ready,
                NextState("FIXED-WAIT-B"),
            )
        )
        aw_fsm.act("FIXED-WAIT-B",
            fixed_aw_active.eq(1),
            axi_to.b.ready.eq(1),
            If(axi_to.b.valid,
                If(axi_to.b.resp > b_collected_resp,
                    NextValue(b_collected_resp, axi_to.b.resp),
                ),
                If(aw_emit_count == cap_aw_len,
                    NextState("FIXED-EMIT-B"),
                ).Else(
                    NextValue(aw_emit_count, aw_emit_count + 1),
                    NextState("FIXED-EMIT-AW"),
                )
            )
        )
        aw_fsm.act("FIXED-EMIT-B",
            fixed_aw_active.eq(1),
            axi_from.b.valid.eq(1),
            axi_from.b.id.eq(cap_aw_id),
            axi_from.b.resp.eq(b_collected_resp),
            If(axi_from.b.ready,
                NextState("IDLE"),
            )
        )

        # W Channel: StrideConverter for data/strb, with `last` overridden in FIXED mode so each
        # ratio-block of narrow beats looks like an independent narrow burst.
        w_converter = stream.StrideConverter(
            description_from = [("data", dw_from), ("strb", dw_from // 8)],
            description_to   = [("data",   dw_to), ("strb",   dw_to // 8)],
        )
        self.submodules += w_converter
        self.comb += axi_from.w.connect(w_converter.sink, omit={"id", "dest", "user"})
        self.comb += [
            axi_to.w.valid.eq(w_converter.source.valid),
            axi_to.w.data.eq(w_converter.source.data),
            axi_to.w.strb.eq(w_converter.source.strb),
            w_converter.source.ready.eq(axi_to.w.ready),
            axi_to.w.id.eq(axi_from.w.id),
            axi_to.w.dest.eq(axi_from.w.dest),
            axi_to.w.user.eq(axi_from.w.user),
            If(fixed_aw_active,
                axi_to.w.last.eq(w_subbeat_count == ratio - 1),
            ).Else(
                axi_to.w.last.eq(w_converter.source.last),
            )
        ]
        self.sync += [
            If(axi_to.w.valid & axi_to.w.ready,
                If(w_subbeat_count == ratio - 1,
                    w_subbeat_count.eq(0),
                ).Else(
                    w_subbeat_count.eq(w_subbeat_count + 1),
                )
            )
        ]

        # B Channel: pass-through for non-FIXED. The FSM drives wide-side b.valid/id/resp and
        # narrow-side b.ready in FIXED mode.
        self.comb += If(~fixed_aw_active,
            axi_from.b.valid.eq(axi_to.b.valid),
            axi_to.b.ready.eq(axi_from.b.ready),
            axi_from.b.id.eq(axi_to.b.id),
            axi_from.b.resp.eq(axi_to.b.resp),
            axi_from.b.user.eq(axi_to.b.user),
            axi_from.b.dest.eq(axi_to.b.dest),
        )

        # ==========================================================================================
        # Read path: AR / R   (mirror of write path)
        # ==========================================================================================

        cap_ar_addr   = Signal.like(axi_from.ar.addr)
        cap_ar_len    = Signal.like(axi_from.ar.len)
        cap_ar_size   = Signal.like(axi_from.ar.size)
        cap_ar_id     = Signal.like(axi_from.ar.id)
        cap_ar_lock   = Signal.like(axi_from.ar.lock)
        cap_ar_prot   = Signal.like(axi_from.ar.prot)
        cap_ar_cache  = Signal.like(axi_from.ar.cache)
        cap_ar_qos    = Signal.like(axi_from.ar.qos)
        cap_ar_region = Signal.like(axi_from.ar.region)

        ar_emit_count = Signal.like(axi_from.ar.len)
        r_wide_count  = Signal.like(axi_from.ar.len)

        fixed_ar_active = Signal()

        is_ar_fixed = (axi_from.ar.burst == BURST_FIXED) & (axi_from.ar.len != 0)

        ar_fsm = FSM(reset_state="IDLE")
        self.ar_fsm = ar_fsm

        ar_fsm.act("IDLE",
            If(~is_ar_fixed,
                # Fast path.
                axi_to.ar.valid.eq(axi_from.ar.valid),
                axi_to.ar.addr.eq(axi_from.ar.addr),
                axi_to.ar.addr[:wide_size_log2].eq(0),
                axi_to.ar.len.eq(((axi_from.ar.len + 1) << log2_int(ratio)) - 1),
                If(axi_from.ar.size <= narrow_size_log2,
                    axi_to.ar.size.eq(axi_from.ar.size),
                ).Else(
                    axi_to.ar.size.eq(narrow_size_log2),
                ),
                Case(axi_from.ar.burst, {
                    BURST_FIXED:    axi_to.ar.burst.eq(BURST_INCR),
                    BURST_INCR:     axi_to.ar.burst.eq(BURST_INCR),
                    BURST_WRAP:     axi_to.ar.burst.eq(BURST_WRAP),
                    BURST_RESERVED: axi_to.ar.burst.eq(BURST_RESERVED),
                }),
                axi_to.ar.id.eq(axi_from.ar.id),
                axi_to.ar.lock.eq(axi_from.ar.lock),
                axi_to.ar.prot.eq(axi_from.ar.prot),
                axi_to.ar.cache.eq(axi_from.ar.cache),
                axi_to.ar.qos.eq(axi_from.ar.qos),
                axi_to.ar.region.eq(axi_from.ar.region),
                axi_to.ar.dest.eq(axi_from.ar.dest),
                axi_to.ar.user.eq(axi_from.ar.user),
                axi_from.ar.ready.eq(axi_to.ar.ready),
            ).Else(
                axi_from.ar.ready.eq(1),
                If(axi_from.ar.valid,
                    NextValue(cap_ar_addr,   axi_from.ar.addr),
                    NextValue(cap_ar_len,    axi_from.ar.len),
                    NextValue(cap_ar_size,   axi_from.ar.size),
                    NextValue(cap_ar_id,     axi_from.ar.id),
                    NextValue(cap_ar_lock,   axi_from.ar.lock),
                    NextValue(cap_ar_prot,   axi_from.ar.prot),
                    NextValue(cap_ar_cache,  axi_from.ar.cache),
                    NextValue(cap_ar_qos,    axi_from.ar.qos),
                    NextValue(cap_ar_region, axi_from.ar.region),
                    NextValue(ar_emit_count, 0),
                    NextValue(r_wide_count,  0),
                    NextState("FIXED-EMIT-AR"),
                )
            )
        )
        ar_fsm.act("FIXED-EMIT-AR",
            fixed_ar_active.eq(1),
            axi_to.ar.valid.eq(1),
            axi_to.ar.addr.eq(cap_ar_addr),
            axi_to.ar.addr[:wide_size_log2].eq(0),
            axi_to.ar.len.eq(ratio - 1),
            axi_to.ar.burst.eq(BURST_INCR),
            If(cap_ar_size <= narrow_size_log2,
                axi_to.ar.size.eq(cap_ar_size),
            ).Else(
                axi_to.ar.size.eq(narrow_size_log2),
            ),
            axi_to.ar.id.eq(cap_ar_id),
            axi_to.ar.lock.eq(cap_ar_lock),
            axi_to.ar.prot.eq(cap_ar_prot),
            axi_to.ar.cache.eq(cap_ar_cache),
            axi_to.ar.qos.eq(cap_ar_qos),
            axi_to.ar.region.eq(cap_ar_region),
            If(axi_to.ar.ready,
                NextState("FIXED-DRAIN-R"),
            )
        )
        ar_fsm.act("FIXED-DRAIN-R",
            # Wait for the wide master to consume the wide R beat that this narrow burst feeds
            # via the StrideConverter. Then issue next AR (or finish).
            fixed_ar_active.eq(1),
            If(axi_from.r.valid & axi_from.r.ready,
                If(ar_emit_count == cap_ar_len,
                    NextState("IDLE"),
                ).Else(
                    NextValue(ar_emit_count, ar_emit_count + 1),
                    NextState("FIXED-EMIT-AR"),
                )
            )
        )

        # R Channel: StrideConverter merges narrow:ratio -> 1 wide. last is overridden in FIXED
        # mode (we want exactly one wide last on the final wide beat).
        r_converter = stream.StrideConverter(
            description_from = [("data",   dw_to)],
            description_to   = [("data", dw_from)],
        )
        self.submodules += r_converter
        self.comb += axi_to.r.connect(r_converter.sink, omit={"id", "dest", "user", "resp", "last"})
        self.comb += r_converter.sink.last.eq(axi_to.r.last)
        self.comb += [
            axi_from.r.valid.eq(r_converter.source.valid),
            axi_from.r.data.eq(r_converter.source.data),
            r_converter.source.ready.eq(axi_from.r.ready),
            If(fixed_ar_active,
                axi_from.r.last.eq(r_wide_count == cap_ar_len),
            ).Else(
                axi_from.r.last.eq(r_converter.source.last),
            )
        ]
        self.sync += [
            If(axi_from.r.valid & axi_from.r.ready,
                If(fixed_ar_active,
                    If(r_wide_count == cap_ar_len,
                        r_wide_count.eq(0),
                    ).Else(
                        r_wide_count.eq(r_wide_count + 1),
                    )
                )
            )
        ]

        # ID/Resp/User from narrow side: clocked-through (matches the existing 1-cycle
        # StrideConverter latency). Tracks the most recent narrow beat — same id within a burst,
        # so the wide value is correct when r.valid fires.
        self.sync += axi_from.r.resp.eq(axi_to.r.resp)
        self.sync += axi_from.r.user.eq(axi_to.r.user)
        self.sync += axi_from.r.dest.eq(axi_to.r.dest)
        self.sync += axi_from.r.id.eq(axi_to.r.id)

class AXIConverter(LiteXModule):
    """AXI data width converter"""
    def __init__(self, master, slave):
        self.master = master
        self.slave  = slave

        # # #

        dw_from = len(master.r.data)
        dw_to   = len(slave.r.data)
        ratio   = dw_from/dw_to

        if ratio > 1:
            self.submodules += AXIDownConverter(master, slave)
        elif ratio < 1:
            self.submodules += AXIUpConverter(master, slave)
        else:
            self.comb += master.connect(slave)

# AXI Timeout --------------------------------------------------------------------------------------

class AXITimeout(LiteXModule):
    """Protect master against slave timeouts (master _has_ to respond correctly)"""
    def __init__(self, master, cycles):
        self.error = Signal()
        wr_error   = Signal()
        rd_error   = Signal()

        # # #

        self.comb += self.error.eq(wr_error | rd_error)

        wr_timer = WaitTimer(cycles)
        rd_timer = WaitTimer(cycles)
        self.submodules += wr_timer, rd_timer

        def channel_fsm(timer, wait_cond, error, response):
            fsm = FSM(reset_state="WAIT")
            fsm.act("WAIT",
                timer.wait.eq(wait_cond),
                # done is updated in `sync`, so we must make sure that `ready` has not been issued
                # by slave during that single cycle, by checking `timer.wait`.
                If(timer.done & timer.wait,
                    error.eq(1),
                    NextState("RESPOND")
                )
            )
            fsm.act("RESPOND", *response)
            return fsm

        self.wr_fsm = channel_fsm(
            timer     = wr_timer,
            wait_cond = (master.aw.valid & ~master.aw.ready) | (master.w.valid & ~master.w.ready),
            error     = wr_error,
            response  = [
                master.aw.ready.eq(master.aw.valid),
                master.w.ready.eq(master.w.valid),
                master.b.valid.eq(~master.aw.valid & ~master.w.valid),
                master.b.resp.eq(RESP_SLVERR),
                If(master.b.valid & master.b.ready,
                    NextState("WAIT")
                )
            ])

        self.rd_fsm = channel_fsm(
            timer     = rd_timer,
            wait_cond = master.ar.valid & ~master.ar.ready,
            error     = rd_error,
            response  = [
                master.ar.ready.eq(master.ar.valid),
                master.r.valid.eq(~master.ar.valid),
                master.r.last.eq(1),
                master.r.resp.eq(RESP_SLVERR),
                master.r.data.eq(2**len(master.r.data) - 1),
                If(master.r.valid & master.r.ready,
                    NextState("WAIT")
                )
            ])

# AXI Interconnect Components ----------------------------------------------------------------------

class _AXIRequestCounter(LiteXModule):
    def __init__(self, request, response, max_requests=256):
        self.counter = counter = Signal(max=max_requests)
        self.full = full = Signal()
        self.empty = empty = Signal()
        self.stall = stall = Signal()
        self.ready = self.empty

        self.comb += [
            full.eq(counter == max_requests - 1),
            empty.eq(counter == 0),
            stall.eq(request & full),
        ]

        self.sync += [
            If(request & response,
                counter.eq(counter)
            ).Elif(request & ~full,
                counter.eq(counter + 1)
            ).Elif(response & ~empty,
                counter.eq(counter - 1)
            ),
        ]

class AXIArbiter(LiteXModule):
    """AXI arbiter

    Arbitrate between master interfaces and connect one to the target. New master will not be
    selected until all requests have been responded to. Arbitration for write and read channels is
    done separately.
    """
    def __init__(self, masters, target):
        write_masters = [m for m in masters if "w" in m.mode]
        read_masters  = [m for m in masters if "r" in m.mode]
        self.rr_write = roundrobin.RoundRobin(len(write_masters), roundrobin.SP_CE)
        self.rr_read  = roundrobin.RoundRobin(len(read_masters), roundrobin.SP_CE)

        def get_sig(interface, channel, name):
            return getattr(getattr(interface, channel), name)

        # Mux master->slave signals
        for channel, name, direction in target.layout_flat():
            write = channel in ["aw", "w", "b"]
            rr = self.rr_write if write else self.rr_read
            m_masters = write_masters if write else read_masters
            if len(m_masters) == 0:
                continue
            if direction == DIR_M_TO_S:
                choices = Array(get_sig(m, channel, name) for m in m_masters)
                self.comb += get_sig(target, channel, name).eq(choices[rr.grant])

        # Connect slave->master signals
        for channel, name, direction in target.layout_flat():
            write = channel in ["aw", "w", "b"]
            rr = self.rr_write if write else self.rr_read
            m_masters = write_masters if write else read_masters
            if direction == DIR_S_TO_M:
                source = get_sig(target, channel, name)
                for i, m in enumerate(m_masters):
                    dest = get_sig(m, channel, name)
                    if name in ["valid", "ready"]:
                        self.comb += If(rr.grant == i, dest.eq(source))
                    else:
                        self.comb += dest.eq(source)

        # Allow to change rr.grant only after all requests from a master have been responded to.
        if len(write_masters):
            self.wr_lock = wr_lock = _AXIRequestCounter(
                request  = target.aw.valid & target.aw.ready,
                response = target.b.valid  & target.b.ready
            )
        if len(read_masters):
            self.rd_lock = rd_lock = _AXIRequestCounter(
                request  = target.ar.valid & target.ar.ready,
                response = target.r.valid  & target.r.ready & target.r.last
            )

        # Switch to next request only if there are no responses pending.
        if len(write_masters):
            self.comb += self.rr_write.ce.eq(~(target.aw.valid | target.w.valid | target.b.valid) & wr_lock.ready),
        if len(read_masters):
            self.comb += self.rr_read.ce.eq(~(target.ar.valid | target.r.valid) & rd_lock.ready)
        

        # Connect bus requests to round-robin selectors.
        if len(write_masters):
            self.comb += self.rr_write.request.eq(Cat(*[m.aw.valid | m.w.valid | m.b.valid for m in write_masters]))
        if len(read_masters):
            self.comb += self.rr_read.request.eq(Cat(*[m.ar.valid | m.r.valid for m in read_masters]))

class AXIDecoder(LiteXModule):
    """AXI decoder

    Decode master access to particular slave based on its decoder function.

    slaves: [(decoder, slave), ...]
        List of slaves with address decoders, where `decoder` is a function:
            decoder(Signal(address_width - log2(data_width//8))) -> Signal(1)
        that returns 1 when the slave is selected and 0 otherwise.
    """
    def __init__(self, master, slaves, register=False):
        # TODO: unused register argument
        addr_shift = log2_int(master.data_width//8)

        channels = {
            "write": {"aw", "w", "b"},
            "read":  {"ar", "r"},
        }
        # Reverse mapping: directions[channel] -> "write"/"read".
        directions = {ch: d for d, chs in channels.items() for ch in chs}

        def new_slave_sel():
            return {"write": Signal(len(slaves)), "read":  Signal(len(slaves))}

        slave_sel_dec = new_slave_sel()
        slave_sel_reg = new_slave_sel()
        slave_sel     = new_slave_sel()

        # We need to hold the slave selected until all responses come back.
        # TODO: we could reuse arbiter counters
        locks = {
            "write": _AXIRequestCounter(
                request  = master.aw.valid & master.aw.ready,
                response = master.b.valid  & master.b.ready
            ),
            "read": _AXIRequestCounter(
                request  = master.ar.valid & master.ar.ready,
                response = master.r.valid  & master.r.ready & master.r.last,
            ),
        }
        self.submodules += locks.values()

        def get_sig(interface, channel, name):
            return getattr(getattr(interface, channel), name)

        # # #

        # Decode slave addresses.
        for i, (decoder, bus) in enumerate(slaves):
            if "w" in bus.mode:
                self.comb += slave_sel_dec["write"][i].eq(decoder(master.aw.addr[addr_shift:]))
            if "r" in bus.mode:
                self.comb += slave_sel_dec["read"][i].eq(decoder(master.ar.addr[addr_shift:]))

        # Change the current selection only when we've got all responses.
        for channel in locks.keys():
            self.sync += If(locks[channel].ready, slave_sel_reg[channel].eq(slave_sel_dec[channel]))
        # We have to cut the delaying select.
        for ch, final in slave_sel.items():
            self.comb += [
                If(locks[ch].ready,
                    final.eq(slave_sel_dec[ch])
                ).Else(
                    final.eq(slave_sel_reg[ch])
                )
            ]

        # Connect master->slaves signals except valid/ready.
        for i, (_, slave) in enumerate(slaves):
            for channel, name, direction in master.layout_flat():
                # directions[channel][0] will be "w" or "r".
                if directions[channel][0] not in slave.mode:
                    continue
                if direction == DIR_M_TO_S:
                    src = get_sig(master, channel, name)
                    dst = get_sig(slave, channel, name)
                    # Mask master control signals depending on slave selection.
                    if name in ["valid", "ready"]:
                        src = src & slave_sel[directions[channel]][i]
                    self.comb += dst.eq(src)

        # Connect slave->master signals masking not selected slaves.
        for channel, name, direction in master.layout_flat():
            if direction == DIR_S_TO_M:
                dst = get_sig(master, channel, name)
                masked = []
                for i, (_, slave) in enumerate(slaves):
                    if directions[channel][0] not in slave.mode:
                        continue
                    src = get_sig(slave, channel, name)
                    # Mask depending on channel.
                    mask = Replicate(slave_sel[directions[channel]][i], len(dst))
                    masked.append(src & mask)
                if len(masked) > 0:
                    self.comb += dst.eq(reduce(or_, masked))

# AXI Interconnect ---------------------------------------------------------------------------------

def get_check_parameters(ports):
    # FIXME: Add adr_width check.

    # Data-Width.
    data_width = ports[0].data_width
    if len(ports) > 1:
        for port in ports[1:]:
            assert port.data_width == data_width

    return data_width

class AXIInterconnectPointToPoint(LiteXModule):
    """AXI point to point interconnect"""
    def __init__(self, master, slave):
        self.comb += master.connect(slave)

class AXIInterconnectShared(LiteXModule):
    """AXI shared interconnect"""
    def __init__(self, masters, slaves, register=False, timeout_cycles=1e6):
        data_width = get_check_parameters(ports=masters + [s for _, s in slaves])
        adr_width = max([m.address_width for m in masters])
        id_width = max([m.id_width for m in masters])
        shared = AXIInterface(data_width=data_width, address_width=adr_width, id_width=id_width)
        self.arbiter = AXIArbiter(masters, shared)
        self.decoder = AXIDecoder(shared, slaves)
        if timeout_cycles is not None:
            self.timeout = AXITimeout(shared, timeout_cycles)

class AXICrossbar(LiteXModule):
    """AXI crossbar

    MxN crossbar for M masters and N slaves.
    """
    def __init__(self, masters, slaves, register=False, timeout_cycles=1e6):
        data_width = get_check_parameters(ports=masters + [s for _, s in slaves])
        adr_width = max([m.address_width for m in masters])
        id_width = max([m.id_width for m in masters])
        matches, busses = zip(*slaves)
        access_m_s = [[AXIInterface(data_width=data_width, address_width=adr_width, id_width=id_width) for j in slaves] for i in masters]  # a[master][slave]
        access_s_m = list(zip(*access_m_s))  # a[slave][master]
        # Decode each master into its access row.
        for slaves, master in zip(access_m_s, masters):
            slaves = list(zip(matches, slaves))
            self.submodules += AXIDecoder(master, slaves, register)
        # Arbitrate each access column onto its slave.
        for masters, bus in zip(access_s_m, busses):
            self.submodules += AXIArbiter(masters, bus)
