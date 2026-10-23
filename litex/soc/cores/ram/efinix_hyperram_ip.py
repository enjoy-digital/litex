#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Efinix HyperRAM controller IP (efx_hyper_ram) on Titanium GPIOs.

Wraps the Efinix soft HyperRAM controller, generated at build time through the Efinity IP Manager
(the IP sources are encrypted, so this only builds with Efinity). The controller runs from its own
PLL (memory clock, 90° clock for CK and a dynamically phase-shifted clock for read capture,
auto-calibrated by the IP) and exposes a standard AXI4 slave interface in `clock_domain`.

The IP has a single shared read/write address channel: AXI AW/AR requests are arbitrated
round-robin onto it.

Tested on Efinix Ti60 F225 Dev Kit (W958D6NKY, 200MHz, 128-bit AXI at 100MHz): IP calibration
passes, ~756MB/s writes / ~750MB/s reads with 4KB bursts. Note: efx_map was observed to stall on
the encrypted IP with LiteX's default synthesis settings; building with Efinix's reference design
efx_map settings (efx_map_params: retiming/seq_opt off, ...) worked.
"""

from migen import *

from migen.genlib.cdc import MultiReg

from litex.gen import *

from litex.build.efinix.common import gpio_info, add_gpio_block

from litex.soc.interconnect import axi, stream
from litex.soc.interconnect.csr import *

from litex.soc.cores.clock.efinix import TITANIUMPLL

# Constants ----------------------------------------------------------------------------------------

EFINIX_HYPERRAM_IP_NAME    = "efx_hyper_ram"
EFINIX_HYPERRAM_IP_LIBRARY = "memory_controller"
EFINIX_HYPERRAM_IP_VENDOR  = "efinixinc.com"

EFINIX_HYPERRAM_IP_DATA_WIDTHS = [32, 64, 128]
EFINIX_HYPERRAM_IP_ID_WIDTH    = 8

# Helpers ------------------------------------------------------------------------------------------

def _latency_to_cr0_ilc(latency):
    # HyperRAM CR0 initial latency encoding: 0b0000=5, 0b0001=6, 0b0010=7, 0b1110=3, 0b1111=4.
    if latency not in [3, 4, 5, 6, 7]:
        raise ValueError(f"Unsupported HyperRAM latency: {latency}.")
    return (latency - 5) & 0xf

# Efinix HyperRAM IP -------------------------------------------------------------------------------

class EfinixHyperRAMIP(LiteXModule):
    """Efinix HyperRAM controller IP.

    Parameters:
    - platform       : Efinix Titanium platform.
    - pads           : HyperRAM pads (dq, rwds, cs_n, rst_n and clk_p/clk_n or clk).
    - sys_clk_freq   : Frequency of `clock_domain` (also the PLL reference).
    - ram_clk_freq   : HyperRAM clock frequency (CK).
    - latency        : HyperRAM initial latency (fixed 2x latency is used).
    - data_width     : AXI data width (32, 64 or 128).
    - size           : HyperRAM size in bytes.
    - clock_domain   : AXI clock domain.
    - name           : IP module/instance name.
    - with_csr       : Expose calibration status.
    """
    def __init__(self, platform, pads, sys_clk_freq,
        ram_clk_freq = 200e6,
        latency      = 7,
        data_width   = 128,
        size         = 32*1024*1024,
        clock_domain = "sys",
        name         = "efx_hbram",
        with_csr     = True):
        if platform.family != "Titanium":
            raise ValueError("Efinix HyperRAM IP is only supported on Titanium.")
        if data_width not in EFINIX_HYPERRAM_IP_DATA_WIDTHS:
            raise ValueError(f"Unsupported Efinix HyperRAM IP data width: {data_width}.")
        if size & (size - 1):
            raise ValueError("Efinix HyperRAM IP size must be a power of two.")
        ram_dbw = len(pads.dq)
        if ram_dbw not in [8, 16]:
            raise ValueError(f"Unsupported HyperRAM DQ width: {ram_dbw}.")
        ram_abw = log2_int(size)

        self.bus      = bus = axi.AXIInterface(
            data_width    = data_width,
            address_width = 32,
            id_width      = EFINIX_HYPERRAM_IP_ID_WIDTH,
            clock_domain  = clock_domain,
        )
        self.cal_pass  = Signal()
        self.cal_debug = Signal(27)

        # # #

        # Clocking.
        # ---------
        self.cd_hbram     = ClockDomain()
        self.cd_hbram90   = ClockDomain()
        self.cd_hbram_cal = ClockDomain()

        shift_ena = platform.add_iface_io(f"{name}_shift_ena")
        shift     = platform.add_iface_io(f"{name}_shift", 3)
        shift_sel = platform.add_iface_io(f"{name}_shift_sel", 5)

        self.pll = pll = TITANIUMPLL(platform, dyn_phase_shift_pads={
            "shift_ena" : shift_ena,
            "shift"     : shift,
            "shift_sel" : shift_sel,
        })
        clkin_name = platform.clks.get(clock_domain, f"{clock_domain}_pll0_clk")
        pll.register_clkin(None, sys_clk_freq, name=clkin_name)
        # Outputs 0/1/2: memory clock, 90° clock (CK outputs), calibrated capture clock. The IP's
        # CAL_CLK_CH is the one-hot index of the capture clock output.
        pll.create_clkout(self.cd_hbram,     ram_clk_freq,           nclkout=0)
        pll.create_clkout(self.cd_hbram90,   ram_clk_freq, phase=90, nclkout=1)
        pll.create_clkout(self.cd_hbram_cal, ram_clk_freq,           nclkout=2, dyn_phase=True)
        # Dynamic phase shift requires core feedback (as in Efinix's reference design).
        pll.create_clkout(None, sys_clk_freq, nclkout=3, is_feedback=True)
        cal_clk_ch = 1 << 2

        # The IP calibration sweeps 8 dynamic phase steps of half a PLL post-divider period and
        # expects 45° steps: force O=4 and /4 output dividers (VCO = 16 x ram_clk_freq, 3.2GHz at
        # 200MHz as in Efinix's reference design) instead of Efinity's auto-calculated settings.
        fb_div = 4*ram_clk_freq/sys_clk_freq
        if fb_div != int(fb_div):
            raise ValueError("Efinix HyperRAM IP requires 4 x ram_clk_freq to be a multiple of sys_clk_freq.")
        pll.extra("\n".join([
            f'design.set_property("{pll.name}","M","1","PLL")',
            f'design.set_property("{pll.name}","N","1","PLL")',
            f'design.set_property("{pll.name}","O","4","PLL")',
            *[f'design.set_property("{pll.name}","CLKOUT{n}_DIV","4","PLL")' for n in range(3)],
            # Phase settings (in half post-divider periods) must be re-applied: 2 = 90° with /4.
            *[f'design.set_property("{pll.name}","CLKOUT{n}_PHASE_SETTING","{p}","PLL")' for n, p in [(0, 0), (1, 2), (2, 0)]],
            f'design.set_property("{pll.name}","CLKOUT3_DIV","{int(fb_div)}","PLL")',
        ]))

        # IO Blocks.
        # ----------
        def iface(suffix, width):
            return platform.add_iface_io(f"{name}_{suffix}", width)

        def add_output(pad, clk, clk_inv, ddio):
            io_name, io_pad, io_prop = gpio_info(platform, pad)
            block = {
                "type"           : "GPIO",
                "mode"           : "OUTPUT",
                "name"           : io_name,
                "location"       : io_pad,
                "properties"     : io_prop,
                "size"           : len(pad),
                "out_reg"        : "DDIO" if ddio else "REG",
                "out_clk_pin"    : clk,
                "out_clk_inv"    : int(clk_inv),
                "drive_strength" : dict(io_prop).get("DRIVE_STRENGTH", "8"),
            }
            add_gpio_block(platform, block, pad)
            if ddio:
                return (platform.add_iface_io(io_name + "_HI", len(pad)),
                        platform.add_iface_io(io_name + "_LO", len(pad)))
            return platform.add_iface_io(io_name, len(pad))

        def add_inout(pad, out_clk_inv):
            io_name, io_pad, io_prop = gpio_info(platform, pad)
            io_prop = list(io_prop) + [("PULL_OPTION", "WEAK_PULLDOWN")]
            block = {
                "type"           : "GPIO",
                "mode"           : "INOUT",
                "name"           : io_name,
                "location"       : io_pad,
                "properties"     : io_prop,
                "size"           : len(pad),
                "in_reg"         : "DDIO_RESYNC",
                "in_clk_pin"     : ClockSignal("hbram_cal"),
                "in_clk_inv"     : 0,
                "out_reg"        : "DDIO",
                "out_clk_pin"    : ClockSignal("hbram"),
                "out_clk_inv"    : int(out_clk_inv),
                "oe_reg"         : "REG",
                "drive_strength" : dict(io_prop).get("DRIVE_STRENGTH", "8"),
            }
            add_gpio_block(platform, block, pad)
            return {s: platform.add_iface_io(f"{io_name}_{s}", len(pad))
                for s in ["OUT_HI", "OUT_LO", "OE", "IN_HI", "IN_LO"]}

        if hasattr(pads, "clk_p"):
            ck_p = add_output(pads.clk_p, ClockSignal("hbram90"), clk_inv=True, ddio=True)
            ck_n = add_output(pads.clk_n, ClockSignal("hbram90"), clk_inv=True, ddio=True)
        else:
            ck_p = add_output(pads.clk,   ClockSignal("hbram90"), clk_inv=True, ddio=True)
            ck_n = (Signal(), Signal())
        cs_n  = add_output(pads.cs_n,  ClockSignal("hbram"), clk_inv=False, ddio=False)
        rst_n = add_output(pads.rst_n, ClockSignal("hbram"), clk_inv=False, ddio=False)
        dq    = add_inout(pads.dq,   out_clk_inv=True)
        rwds  = add_inout(pads.rwds, out_clk_inv=False)

        # AXI: AW/AR -> shared ARW channel (round-robin, registered).
        # ------------------------------------------------------------
        addr_mask = 2**ram_abw - 1
        arw_layout = [("addr", 32), ("id", EFINIX_HYPERRAM_IP_ID_WIDTH), ("len", 8), ("size", 3),
            ("burst", 2), ("lock", 2), ("write", 1)]
        self.arw = arw = ClockDomainsRenamer(clock_domain)(stream.PipeValid(arw_layout))
        arw_last = Signal() # Last granted channel was write.
        arw_sel  = Signal() # 1: AW, 0: AR.
        self.comb += [
            If(bus.aw.valid & bus.ar.valid,
                arw_sel.eq(~arw_last),
            ).Else(
                arw_sel.eq(bus.aw.valid),
            ),
            arw.sink.valid.eq(bus.aw.valid | bus.ar.valid),
            bus.aw.ready.eq( arw_sel & arw.sink.ready),
            bus.ar.ready.eq(~arw_sel & arw.sink.ready),
            arw.sink.write.eq(arw_sel),
        ]
        for field in ["addr", "id", "len", "size", "burst", "lock"]:
            self.comb += getattr(arw.sink, field).eq(Mux(arw_sel, getattr(bus.aw, field), getattr(bus.ar, field)))
        sd = getattr(self.sync, clock_domain)
        sd += If(arw.sink.valid & arw.sink.ready, arw_last.eq(arw_sel))

        # Reset.
        # ------
        rst = Signal()
        self.comb += rst.eq(ResetSignal(clock_domain) | ~pll.locked)

        # IP Instance.
        # ------------
        self.specials += Instance(name,
            # Clks/Rst.
            i_io_axi_clk  = ClockSignal(clock_domain),
            i_ram_clk     = ClockSignal("hbram"),
            i_ram_clk_cal = ClockSignal("hbram_cal"),
            i_rst         = rst,

            # ARW.
            i_io_arw_valid         = arw.source.valid,
            o_io_arw_ready         = arw.source.ready,
            i_io_arw_payload_addr  = arw.source.addr & addr_mask,
            i_io_arw_payload_id    = arw.source.id,
            i_io_arw_payload_len   = arw.source.len,
            i_io_arw_payload_size  = arw.source.size,
            i_io_arw_payload_burst = arw.source.burst,
            i_io_arw_payload_lock  = arw.source.lock,
            i_io_arw_payload_write = arw.source.write,

            # W.
            i_io_w_valid         = bus.w.valid,
            o_io_w_ready         = bus.w.ready,
            i_io_w_payload_id    = 0,
            i_io_w_payload_data  = bus.w.data,
            i_io_w_payload_strb  = bus.w.strb,
            i_io_w_payload_last  = bus.w.last,

            # B.
            o_io_b_valid      = bus.b.valid,
            i_io_b_ready      = bus.b.ready,
            o_io_b_payload_id = bus.b.id,

            # R.
            o_io_r_valid        = bus.r.valid,
            i_io_r_ready        = bus.r.ready,
            o_io_r_payload_id   = bus.r.id,
            o_io_r_payload_data = bus.r.data,
            o_io_r_payload_resp = bus.r.resp,
            o_io_r_payload_last = bus.r.last,

            # HyperRAM GPIOs.
            o_hbc_ck_p_HI    = ck_p[0],
            o_hbc_ck_p_LO    = ck_p[1],
            o_hbc_ck_n_HI    = ck_n[0],
            o_hbc_ck_n_LO    = ck_n[1],
            o_hbc_cs_n       = cs_n,
            o_hbc_rst_n      = rst_n,
            o_hbc_dq_OUT_HI  = dq["OUT_HI"],
            o_hbc_dq_OUT_LO  = dq["OUT_LO"],
            o_hbc_dq_OE      = dq["OE"],
            i_hbc_dq_IN_HI   = dq["IN_HI"],
            i_hbc_dq_IN_LO   = dq["IN_LO"],
            o_hbc_rwds_OUT_HI = rwds["OUT_HI"],
            o_hbc_rwds_OUT_LO = rwds["OUT_LO"],
            o_hbc_rwds_OE     = rwds["OE"],
            i_hbc_rwds_IN_HI  = rwds["IN_HI"],
            i_hbc_rwds_IN_LO  = rwds["IN_LO"],

            # Calibration.
            o_hbc_cal_SHIFT_ENA  = shift_ena,
            o_hbc_cal_SHIFT      = shift,
            o_hbc_cal_SHIFT_SEL  = shift_sel,
            o_hbc_cal_pass       = self.cal_pass,
            o_hbc_cal_debug_info = self.cal_debug,
            i_dyn_pll_phase_en   = 0,
            i_dyn_pll_phase_sel  = 0,
        )
        self.comb += bus.b.resp.eq(axi.RESP_OKAY)

        # IP Generation (Efinity IP Manager).
        # -----------------------------------
        platform.toolchain.ipmwriter.blocks.append({
            "type"    : "IP",
            "name"    : name,
            "vendor"  : EFINIX_HYPERRAM_IP_VENDOR,
            "library" : EFINIX_HYPERRAM_IP_LIBRARY,
            "ip_name" : EFINIX_HYPERRAM_IP_NAME,
            "configs" : {
                "MHZ"        : int(ram_clk_freq/1e6),
                "RAM_DBW"    : ram_dbw,
                "RAM_ABW"    : ram_abw,
                "CR0_ILC"    : _latency_to_cr0_ilc(latency),
                "CR0_FLE"    : 1, # Fixed latency.
                "AXI_IF"     : 1,
                "AXI_DBW_2"  : data_width,
                "CAL_MODE"   : 2, # PLL dynamic phase shift auto-calibration.
                "CAL_CLK_CH" : cal_clk_ch,
            },
        })

        # CSRs.
        # -----
        if with_csr:
            self.status = CSRStatus(fields=[
                CSRField("cal_pass",  size=1,  offset=0,  description="Calibration passed."),
                CSRField("cal_debug", size=27, offset=1,  description="IP calibration debug info."),
            ])
            self.specials += [
                MultiReg(self.cal_pass,  self.status.fields.cal_pass),
                MultiReg(self.cal_debug, self.status.fields.cal_debug),
            ]
