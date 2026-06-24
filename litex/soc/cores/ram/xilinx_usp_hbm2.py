#
# This file is part of LiteX.
#
# Copyright (c) 2020-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex.soc.cores.clock import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.builder import *
from litex.soc.interconnect.axi import *
from litex.soc.interconnect.csr import *

# HBM2 Pseudo-Channel Helpers ----------------------------------------------------------------------

USPHBM2_NCHANNELS    = 32
USPHBM2_CHANNEL_SIZE = 0x1000_0000 # 256MB.
USPHBM2_DEFAULT_BASE = 0x4000_0000
USPHBM2_HIGH_BASE    = 0x1_0000_0000

def parse_usphbm2_channels(channels):
    if isinstance(channels, str):
        channels = channels.strip().lower()
        if channels == "all":
            parsed_channels = list(range(USPHBM2_NCHANNELS))
        else:
            parsed_channels = []
            for item in channels.split(","):
                item = item.strip()
                if not item:
                    raise ValueError("empty HBM2 channel entry")
                if "-" in item:
                    start, end = [int(v, 0) for v in item.split("-", 1)]
                    if end < start:
                        raise ValueError("HBM2 channel ranges must be increasing")
                    parsed_channels.extend(range(start, end + 1))
                else:
                    parsed_channels.append(int(item, 0))
    else:
        parsed_channels = list(channels)

    if not parsed_channels:
        raise ValueError("at least one HBM2 channel must be selected")
    if len(parsed_channels) != len(set(parsed_channels)):
        raise ValueError("HBM2 channels must be unique")
    for channel in parsed_channels:
        if not 0 <= channel < USPHBM2_NCHANNELS:
            raise ValueError(f"HBM2 channel {channel} outside 0-{USPHBM2_NCHANNELS - 1}")
    return tuple(parsed_channels)

def usphbm2_channel_origin(channel,
    hbm_base      = USPHBM2_DEFAULT_BASE,
    hbm_high_base = USPHBM2_HIGH_BASE):

    origin = hbm_base + USPHBM2_CHANNEL_SIZE*channel
    if hbm_base == USPHBM2_DEFAULT_BASE and origin >= 0x8000_0000:
        origin = hbm_high_base + USPHBM2_CHANNEL_SIZE*(channel - 4)
    return origin

def usphbm2_channel_origins(channels,
    hbm_base      = USPHBM2_DEFAULT_BASE,
    hbm_high_base = USPHBM2_HIGH_BASE):

    return {
        channel: usphbm2_channel_origin(channel, hbm_base, hbm_high_base)
        for channel in channels
    }

def usphbm2_window_end(origins):
    return max(origin + USPHBM2_CHANNEL_SIZE for origin in origins.values())

def add_usphbm2_pseudochannels(soc, hbm, channels, main_channel,
    origins          = None,
    hbm_base         = USPHBM2_DEFAULT_BASE,
    hbm_high_base    = USPHBM2_HIGH_BASE,
    hbm_strip_origin = False):

    channels = parse_usphbm2_channels(channels)
    if main_channel not in channels:
        raise ValueError("HBM2 main channel must be one of the mapped HBM2 channels")
    if origins is None:
        origins = usphbm2_channel_origins(channels, hbm_base, hbm_high_base)
    if usphbm2_window_end(origins) > 2**33:
        hbm_strip_origin = True

    hbm_regions = {}
    for channel in channels:
        axi_hbm      = hbm.axi[channel]
        axi_lite_bus = AXILiteInterface(data_width=256, address_width=soc.bus.address_width)
        axi_lite_hbm = AXILiteInterface(data_width=256, address_width=33)
        origin       = origins[channel]
        soc.submodules += AXILiteOffset(
            master = axi_lite_bus,
            slave  = axi_lite_hbm,
            offset = origin if hbm_strip_origin else 0)
        soc.submodules += AXILite2AXI(axi_lite_hbm, axi_hbm)
        hbm_regions[channel] = origin
        soc.bus.add_slave(
            f"hbm{channel}",
            axi_lite_bus,
            SoCRegion(
                origin = origin,
                size   = USPHBM2_CHANNEL_SIZE,
                cached = not (0x8000_0000 <= origin < 0x1_0000_0000)))

    soc.add_constant("HBM_CHANNELS", len(channels))
    soc.add_constant("HBM_MAIN_CHANNEL", main_channel)
    soc.add_constant("HBM_HIGH_BASE", hbm_high_base)
    soc.bus.add_region("main_ram", SoCRegion(
        origin = hbm_regions[main_channel],
        size   = USPHBM2_CHANNEL_SIZE,
        linker = True))
    return hbm_regions

# Ultrascale + HBM2 IP Wrapper ---------------------------------------------------------------------

class USPHBM2(LiteXModule):
    """Xilinx Virtex US+ High Bandwidth Memory 2 IP wrapper"""
    def __init__(self, platform, hbm_ip_name="hbm_0"):
        self.platform = platform
        self.hbm_name = hbm_ip_name

        self.axi = []
        self.apb = []

        self.hbm_params = {}

        self.init_done = CSRStatus(description="HBM2 initialization done.")

        # # #

        # Clocks -----------------------------------------------------------------------------------
        # Ref = 100 MHz (HBM: 900 (225-900) MHz), drives internal PLL (1 per stack).
        for i in range(2):
            self.hbm_params[f"i_HBM_REF_CLK_{i:1d}"] = ClockSignal("hbm_ref")

        # APB: 100 (50-100) MHz
        for i in range(2):
            self.hbm_params[f"i_APB_{i:1d}_PCLK"]     = ClockSignal("apb")
            self.hbm_params[f"i_APB_{i:1d}_PRESET_N"] = ~ResetSignal("apb")

        # AXI: 450 (225-450) MHz
        for i in range(32):
            self.hbm_params[f"i_AXI_{i:02d}_ACLK"]     = ClockSignal("axi")
            self.hbm_params[f"i_AXI_{i:02d}_ARESET_N"] = ~ResetSignal("apb")

        # AXI --------------------------------------------------------------------------------------
        for i in range(32):
            axi = AXIInterface(data_width=256, address_width=33, id_width=6)
            self.axi.append(axi)

            # AW Channel.
            self.hbm_params[f"i_AXI_{i :02d}_AWADDR"]      = axi.aw.addr
            self.hbm_params[f"i_AXI_{i :02d}_AWBURST"]     = axi.aw.burst
            self.hbm_params[f"i_AXI_{i :02d}_AWID"]        = axi.aw.id
            self.hbm_params[f"i_AXI_{i :02d}_AWLEN"]       = axi.aw.len
            self.hbm_params[f"i_AXI_{i :02d}_AWSIZE"]      = axi.aw.size
            self.hbm_params[f"i_AXI_{i :02d}_AWVALID"]     = axi.aw.valid
            self.hbm_params[f"o_AXI_{i :02d}_AWREADY"]     = axi.aw.ready

            # W Channel.
            self.hbm_params[f"i_AXI_{i:02d}_WDATA"]        = axi.w.data
            self.hbm_params[f"i_AXI_{i:02d}_WLAST"]        = axi.w.last
            self.hbm_params[f"i_AXI_{i:02d}_WSTRB"]        = axi.w.strb
            self.hbm_params[f"i_AXI_{i:02d}_WDATA_PARITY"] = 0 # FIXME: Manage parity?
            self.hbm_params[f"i_AXI_{i:02d}_WVALID"]       = axi.w.valid
            self.hbm_params[f"o_AXI_{i:02d}_WREADY"]       = axi.w.ready

            # B Channel.
            self.hbm_params[f"o_AXI_{i:02d}_BID"]          = axi.b.id
            self.hbm_params[f"o_AXI_{i:02d}_BRESP"]        = axi.b.resp
            self.hbm_params[f"o_AXI_{i:02d}_BVALID"]       = axi.b.valid
            self.hbm_params[f"i_AXI_{i:02d}_BREADY"]       = axi.b.ready

            # AR Channel.
            self.hbm_params[f"i_AXI_{i:02d}_ARADDR"]       = axi.ar.addr
            self.hbm_params[f"i_AXI_{i:02d}_ARBURST"]      = axi.ar.burst
            self.hbm_params[f"i_AXI_{i:02d}_ARID"]         = axi.ar.id
            self.hbm_params[f"i_AXI_{i:02d}_ARLEN"]        = axi.ar.len
            self.hbm_params[f"i_AXI_{i:02d}_ARSIZE"]       = axi.ar.size
            self.hbm_params[f"i_AXI_{i:02d}_ARVALID"]      = axi.ar.valid
            self.hbm_params[f"o_AXI_{i:02d}_ARREADY"]      = axi.ar.ready

            # R Channel.
            self.hbm_params[f"o_AXI_{i:02d}_RDATA_PARITY"] = Open() # FIXME: Manage parity?
            self.hbm_params[f"o_AXI_{i:02d}_RDATA"]        = axi.r.data
            self.hbm_params[f"o_AXI_{i:02d}_RID"]          = axi.r.id
            self.hbm_params[f"o_AXI_{i:02d}_RLAST"]        = axi.r.last
            self.hbm_params[f"o_AXI_{i:02d}_RRESP"]        = axi.r.resp
            self.hbm_params[f"o_AXI_{i:02d}_RVALID"]       = axi.r.valid
            self.hbm_params[f"i_AXI_{i:02d}_RREADY"]       = axi.r.ready

        # APB --------------------------------------------------------------------------------------
        # FIXME: Connect to CSR or Wishbone.
        apb_complete = Signal(2)
        for i in range(2):
            self.hbm_params[f"i_APB_{i:1d}_PWDATA"]  = 0
            self.hbm_params[f"i_APB_{i:1d}_PADDR"]   = 0
            self.hbm_params[f"i_APB_{i:1d}_PENABLE"] = 0
            self.hbm_params[f"i_APB_{i:1d}_PSEL"]    = 0
            self.hbm_params[f"i_APB_{i:1d}_PWRITE"]  = 0

            self.hbm_params[f"o_APB_{i:1d}_PRDATA"]  = Open()
            self.hbm_params[f"o_APB_{i:1d}_PREADY"]  = Open()
            self.hbm_params[f"o_APB_{i:1d}_PSLVERR"] = Open()

            self.hbm_params[f"o_apb_complete_{i:1d}"] = apb_complete[i]
        self.comb += self.init_done.status.eq(apb_complete == 0b11)

        # Temperature ------------------------------------------------------------------------------
        for i in range(2):
            self.hbm_params[f"o_DRAM_{i:1d}_STAT_CATTRIP"] = Open()
            self.hbm_params[f"o_DRAM_{i:1d}_STAT_TEMP"]    = Open()

    def add_sources(self, platform):
        platform.add_ip(os.path.join(os.getcwd(), "ip", "hbm", self.hbm_name + ".xci"))

    def do_finalize(self):
        self.add_sources(self.platform)
        self.specials += Instance(self.hbm_name, **self.hbm_params)
