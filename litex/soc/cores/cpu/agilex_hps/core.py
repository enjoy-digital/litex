#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.interconnect import axi

from litex.soc.cores.cpu import CPU

# Per-Variant Configuration ------------------------------------------------------------------------

# Single source of truth for all family differences. Values that could not be verified without
# Quartus Prime Pro are tagged [VERIFY: source]; because they are isolated here, they can be fixed
# in one place (and overridden from the target via add_hps_config()) once a Pro build is available.
#
# `if_names` maps a logical bridge to (interface, clock, reset) names of the HPS Platform Designer
# component; these become the `<export>_<role>` top-level ports of the generated Qsys module.
#
# Sources: altera-fpga GHRDs (construct_hps.tcl / construct_subsys_hps.tcl), mainline
# socfpga_agilex*.dtsi, and /opt/quartus_lite_23.1/riscfree/xsvd/{agilex_hps,diamond_mesa_hps}.svd.

HPS_VARIANTS = {
    # Agilex 7 (Quad Cortex-A53, GIC-400 / GICv2). Address map confirmed (Stratix-10-derived).
    "agilex7" : dict(
        human_name      = "Agilex 7 HPS (Quad Cortex-A53)",
        gcc_cpu         = "cortex-a53",
        device_family   = "Agilex 7",
        hps_ip          = "intel_agilex_hps",       # [CONFIRMED: agilex_soc_devkit_ghrd/construct_hps.tcl]
        emif            = None,                      # Dedicated altera_emif_fm_hps (no board -> deferred).
        h2f_lw_base     = 0xf900_0000,               # [CONFIRMED: rocketboards AGILEX_LW_H2F_BASE]
        h2f_lw_awidth   = 21,                        # 2MB window.  [CONFIRMED: S10/Agilex convention]
        h2f_base        = 0x8000_0000,               # [CONFIRMED: rocketboards AGILEX_H2F_BASE]
        h2f_awidth      = 30,                        # 1GB window.
        h2f_data_widths = [32, 64, 128, 256],
        f2h_data_widths = [128, 256, 512],
        f2h_irq_width   = 64,
        f2h_irq_spi     = 17,                        # GIC INTID 49 - 32.  [CONFIRMED: rocketboards HOWTO]
        uart0_base      = 0xffc0_2000,               # [CONFIRMED: socfpga_agilex.dtsi]
        gic_dist_base   = 0xfffc_1000,               # [CONFIRMED: socfpga_agilex.dtsi (gic-400)]
        uboot_defconfig = "socfpga_agilex_defconfig",
        if_names        = dict(
            h2f_lw = ("h2f_lw_axi_master", "h2f_lw_axi_clock", "h2f_lw_axi_reset"),
            h2f    = ("h2f_axi_master",    "h2f_axi_clock",    "h2f_axi_reset"),
            f2h    = ("f2h_axi_slave",     "f2h_axi_clock",    "f2h_axi_reset"),
        ),
    ),
    # Agilex 5 (2x Cortex-A76 + 2x Cortex-A55, GIC-600 / GICv3). Primary board (065B DevKit).
    "agilex5" : dict(
        human_name      = "Agilex 5 HPS (Dual Cortex-A76 + Dual Cortex-A55)",
        gcc_cpu         = "cortex-a55",              # Common baseline for the A76/A55 pair.
        device_family   = "Agilex 5",
        hps_ip          = "intel_agilex_5_soc",      # [CONFIRMED: agilex5_soc_devkit_ghrd construct_subsys_hps.tcl]
        emif            = "emif_ph2",                # [CONFIRMED: agilex5 GHRD + litex_agilex_test]
        h2f_lw_base     = 0x2000_0000,               # [VERIFY: Agilex 5 HPS TRM (intel search "0x00_2000_0000")]
        h2f_lw_awidth   = 29,                        # 512MB window.  [CONFIRMED: LWH2F_Address_Width 29]
        h2f_base        = 0x8000_0000,               # [CONFIRMED: demo doc 08]
        h2f_awidth      = 30,                        # Exposed as 1GB (component supports up to 256GB).
        h2f_data_widths = [32, 64, 128],
        f2h_data_widths = [],                        # fpga2hps is ACE5-Lite (not expressible in LiteX AXI).
        f2h_irq_width   = 64,
        f2h_irq_spi     = None,                       # [VERIFY: Agilex 5 TRM (candidates INTID 72-135)]
        uart0_base      = 0x10c0_2000,               # [CONFIRMED: socfpga_agilex5.dtsi]
        gic_dist_base   = 0x1d00_0000,               # [CONFIRMED: socfpga_agilex5.dtsi (gic-v3)]
        uboot_defconfig = "socfpga_agilex5_defconfig",
        if_names        = dict(
            h2f_lw = ("lwhps2fpga", "lwhps2fpga_axi_clock", "lwhps2fpga_axi_reset"),
            h2f    = ("hps2fpga",   "hps2fpga_axi_clock",   "hps2fpga_axi_reset"),
            f2h    = ("fpga2hps",   "fpga2hps_clock",       "fpga2hps_reset"),
        ),
    ),
    # Agilex 3 (Dual Cortex-A55, GICv3). Same A55 SoC lineage as Agilex 5 (mostly inferred).
    "agilex3" : dict(
        human_name      = "Agilex 3 HPS (Dual Cortex-A55)",
        gcc_cpu         = "cortex-a55",
        device_family   = "Agilex 3",
        hps_ip          = "intel_agilex_3_soc",      # [VERIFY: Agilex 3 GHRD (by analogy to agilex_5_soc)]
        emif            = "emif_ph2",                # [LIKELY: same in-fabric EMIF as Agilex 5]
        h2f_lw_base     = 0x2000_0000,               # [VERIFY: Agilex 3 dtsi (assumed == Agilex 5)]
        h2f_lw_awidth   = 29,
        h2f_base        = 0x8000_0000,
        h2f_awidth      = 30,
        h2f_data_widths = [32, 64, 128],
        f2h_data_widths = [],
        f2h_irq_width   = 64,
        f2h_irq_spi     = None,                       # [VERIFY: Agilex 3 TRM]
        uart0_base      = 0x10c0_2000,               # [VERIFY: socfpga_agilex3.dtsi (assumed == Agilex 5)]
        gic_dist_base   = 0x1d00_0000,               # [VERIFY: idem]
        uboot_defconfig = "socfpga_agilex3_defconfig",
        if_names        = dict(
            h2f_lw = ("lwhps2fpga", "lwhps2fpga_axi_clock", "lwhps2fpga_axi_reset"),
            h2f    = ("hps2fpga",   "hps2fpga_axi_clock",   "hps2fpga_axi_reset"),
            f2h    = ("fpga2hps",   "fpga2hps_clock",       "fpga2hps_reset"),
        ),
    ),
}

# Agilex HPS ---------------------------------------------------------------------------------------

class AgilexHPS(CPU):
    variants                 = ["agilex3", "agilex5", "agilex7"]
    category                 = "hardcore"
    family                   = "aarch64"
    name                     = "agilex_hps"
    human_name               = "Agilex HPS"
    data_width               = 64
    endianness               = "little"
    reset_address            = 0x0010_0000 # HPS DDR (Linker-only; HPS boots via SDM/FSBL/U-Boot).
    reset_address_check      = False
    gcc_triple               = "aarch64-none-elf"
    gcc_flags                = ""          # Set per-variant in __init__.
    linker_output_format     = "elf64-littleaarch64"
    nop                      = "nop"
    csr_decode               = True        # AXI address decoded in AXI2Wishbone; offset re-added in Software.
    integrated_rom_supported = False

    # I/O Regions (== H2F LW bridge window, per-variant).
    @property
    def io_regions(self):
        cfg = HPS_VARIANTS[self.variant]
        return {cfg["h2f_lw_base"]: (1 << cfg["h2f_lw_awidth"])}

    # Memory Mapping (== ARM physical addresses).
    @property
    def mem_map(self):
        cfg = HPS_VARIANTS[self.variant]
        return {
            "sram"     : 0x0010_0000,        # HPS DDR (skips first 1MB), Linker-only region.
            "rom"      : 0x0100_0000,        # HPS DDR, Linker-only region (added by target).
            "main_ram" : cfg["h2f_base"],    # Fabric seen by the ARM through the H2F window.
            "csr"      : cfg["h2f_lw_base"], # H2F LW bridge window.
        }

    def __init__(self, platform, variant, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert variant in HPS_VARIANTS
        self.platform     = platform
        self.variant      = variant
        self.cfg          = cfg = HPS_VARIANTS[variant]
        self.human_name   = cfg["human_name"]
        self.gcc_flags    = f"-mcpu={cfg['gcc_cpu']} -D__agilex_hps__ -D__{variant}_hps__"

        self.reset        = Signal() # Not used (HPS is not reset from the fabric).
        self.interrupt    = Signal(cfg["f2h_irq_width"]) # F2H IRQs (GIC SPI base cfg["f2h_irq_spi"]).
        self.periph_buses = []       # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []       # Memory buses (Connected directly to LiteDRAM).

        self.h2f_lw_master = None    # H2F LW AXI4 Master (HPS -> Fabric, CSRs access).
        self.h2f_master    = None    # H2F    AXI4 Master (HPS -> Fabric).
        self.f2h_slave     = None    # F2H    AXI4 Slave  (Fabric -> HPS, Agilex 7 only).
        self.h2f_rst_n     = Signal() # HPS -> Fabric reset.

        # Qsys System (HPS + optional HPS-EMIF), built by set_hps/add_* and emitted in do_finalize.
        self.hps_name    = "hps_system" # Qsys system/module name (stable, LiteX-chosen).
        self.hps_config  = {}           # HPS IP parameters   (raw Platform Designer names).
        self.emif        = None         # (pads, refclk_pads, config) when add_emif() is called.
        self.hps_exports = []           # (export_name, hps_interface, qsys_type, direction) tuples.
        self.cpu_params  = {}           # Instance ports of the generated Qsys module.

        # # #

        # H2F LW as Bus Master ---------------------------------------------------------------------
        self.pbus = self.add_axi_h2f_lw_master()
        self.periph_buses.append(self.pbus)

    # Configuration (Platform Designer HPS IP parameters) ------------------------------------------
    def set_hps(self, name=None, config=None):
        if name is not None:
            self.hps_name = name
        if config is not None:
            self.add_hps_config(config)

    def add_hps_config(self, config):
        # Raw Platform Designer parameter names; applied last in do_finalize so a target can
        # override/extend anything LiteX sets without editing the CPU core.
        assert isinstance(config, dict)
        self.hps_config.update(config)

    # AXI Master helper (HPS -> Fabric bridges share the same channel wiring) ----------------------
    def _connect_axi_master(self, export, axi_if, clock_domain):
        # Wire an HPS-side AXI4 master interface (exported as `<export>_*`) to a LiteX AXIInterface.
        rst_n = Signal(reset=1)
        self.comb += rst_n.eq(~ResetSignal(clock_domain))
        self.cpu_params.update({
            # Clk/Rst.
            f"i_{export}_clk_clk"       : ClockSignal(clock_domain),
            f"i_{export}_rst_reset_n"   : rst_n,
            # AW.
            f"o_{export}_awid"          : axi_if.aw.id,
            f"o_{export}_awaddr"        : axi_if.aw.addr,
            f"o_{export}_awlen"         : axi_if.aw.len,
            f"o_{export}_awsize"        : axi_if.aw.size,
            f"o_{export}_awburst"       : axi_if.aw.burst,
            f"o_{export}_awlock"        : axi_if.aw.lock,
            f"o_{export}_awprot"        : axi_if.aw.prot,
            f"o_{export}_awcache"       : axi_if.aw.cache,
            f"o_{export}_awvalid"       : axi_if.aw.valid,
            f"i_{export}_awready"       : axi_if.aw.ready,
            # W.
            f"o_{export}_wdata"         : axi_if.w.data,
            f"o_{export}_wstrb"         : axi_if.w.strb,
            f"o_{export}_wlast"         : axi_if.w.last,
            f"o_{export}_wvalid"        : axi_if.w.valid,
            f"i_{export}_wready"        : axi_if.w.ready,
            # B.
            f"i_{export}_bid"           : axi_if.b.id,
            f"i_{export}_bresp"         : axi_if.b.resp,
            f"i_{export}_bvalid"        : axi_if.b.valid,
            f"o_{export}_bready"        : axi_if.b.ready,
            # AR.
            f"o_{export}_arid"          : axi_if.ar.id,
            f"o_{export}_araddr"        : axi_if.ar.addr,
            f"o_{export}_arlen"         : axi_if.ar.len,
            f"o_{export}_arsize"        : axi_if.ar.size,
            f"o_{export}_arburst"       : axi_if.ar.burst,
            f"o_{export}_arlock"        : axi_if.ar.lock,
            f"o_{export}_arprot"        : axi_if.ar.prot,
            f"o_{export}_arcache"       : axi_if.ar.cache,
            f"o_{export}_arvalid"       : axi_if.ar.valid,
            f"i_{export}_arready"       : axi_if.ar.ready,
            # R.
            f"i_{export}_rid"           : axi_if.r.id,
            f"i_{export}_rdata"         : axi_if.r.data,
            f"i_{export}_rresp"         : axi_if.r.resp,
            f"i_{export}_rlast"         : axi_if.r.last,
            f"i_{export}_rvalid"        : axi_if.r.valid,
            f"o_{export}_rready"        : axi_if.r.ready,
        })

    def _extend_address(self, axi_if, base, window_awidth):
        # The HPS bridge presents a window-relative address; extend it to the ARM physical address
        # so the LiteX memory map matches the ARM's view (cyclonev_hps pattern).
        assert (base & ((1 << window_awidth) - 1)) == 0
        awaddr = Signal(window_awidth)
        araddr = Signal(window_awidth)
        upper  = Constant(base >> window_awidth, axi_if.address_width - window_awidth)
        self.comb += [
            axi_if.aw.addr.eq(Cat(awaddr, upper)),
            axi_if.ar.addr.eq(Cat(araddr, upper)),
        ]
        return awaddr, araddr

    # H2F LW AXI4 Master (HPS -> Fabric, CSRs access) ----------------------------------------------
    def add_axi_h2f_lw_master(self, clock_domain="sys"):
        assert self.h2f_lw_master is None
        cfg     = self.cfg
        axi_lw  = axi.AXIInterface(data_width=32, address_width=32, id_width=9, version="axi4",
            clock_domain=clock_domain)
        self.h2f_lw_master = axi_lw
        export  = "h2f_lw_axi"

        awaddr, araddr = self._extend_address(axi_lw, cfg["h2f_lw_base"], cfg["h2f_lw_awidth"])
        self._connect_axi_master(export, axi_lw, clock_domain)
        # Override the (extended) address ports with the window-relative signals.
        self.cpu_params[f"o_{export}_awaddr"] = awaddr
        self.cpu_params[f"o_{export}_araddr"] = araddr

        self.add_hps_config({"LWH2F_Enable": "true"}) # [VERIFY: exact enable param per family]
        self._export_bridge(export, "h2f_lw", clock_domain)
        return axi_lw

    # H2F AXI4 Master (HPS -> Fabric) --------------------------------------------------------------
    def add_axi_h2f_master(self, data_width=64, clock_domain="sys"):
        assert self.h2f_master is None
        cfg = self.cfg
        assert data_width in cfg["h2f_data_widths"]
        axi_h2f = axi.AXIInterface(data_width=data_width, address_width=32, id_width=9,
            version="axi4", clock_domain=clock_domain)
        self.h2f_master = axi_h2f
        export = "h2f_axi"

        awaddr, araddr = self._extend_address(axi_h2f, cfg["h2f_base"], cfg["h2f_awidth"])
        self._connect_axi_master(export, axi_h2f, clock_domain)
        self.cpu_params[f"o_{export}_awaddr"] = awaddr
        self.cpu_params[f"o_{export}_araddr"] = araddr

        self.add_hps_config({"H2F_Width": data_width}) # [VERIFY: exact width param per family]
        self._export_bridge(export, "h2f", clock_domain)
        return axi_h2f

    # F2H AXI4 Slave (Fabric -> HPS, Agilex 7 only) ------------------------------------------------
    def add_axi_f2h_slave(self, data_width=128, clock_domain="sys"):
        # On Agilex 5/3 the F2H interface is ACE5-Lite (cache-coherent), which LiteX's AXI cannot
        # express; only Agilex 7's plain-AXI4 F2H is supported here. Not connected to the shared bus
        # (an H2F->F2H loopback would deadlock); connect user DMAs directly to the returned slave.
        assert self.f2h_slave is None
        cfg = self.cfg
        if not len(cfg["f2h_data_widths"]):
            raise NotImplementedError(f"F2H slave is not supported on {self.variant} (ACE5-Lite).")
        assert data_width in cfg["f2h_data_widths"]
        axi_f2h = axi.AXIInterface(data_width=data_width, address_width=32, id_width=8,
            version="axi4", clock_domain=clock_domain)
        self.f2h_slave = axi_f2h
        export = "f2h_axi"

        rst_n = Signal(reset=1)
        self.comb += rst_n.eq(~ResetSignal(clock_domain))
        self.cpu_params.update({
            f"i_{export}_clk_clk"     : ClockSignal(clock_domain),
            f"i_{export}_rst_reset_n" : rst_n,
            # Fabric is the master; HPS side is the slave (input/output directions swapped).
            f"i_{export}_awid"    : axi_f2h.aw.id,    f"i_{export}_awaddr"  : axi_f2h.aw.addr,
            f"i_{export}_awlen"   : axi_f2h.aw.len,   f"i_{export}_awsize"  : axi_f2h.aw.size,
            f"i_{export}_awburst" : axi_f2h.aw.burst, f"i_{export}_awlock"  : axi_f2h.aw.lock,
            f"i_{export}_awprot"  : axi_f2h.aw.prot,  f"i_{export}_awcache" : axi_f2h.aw.cache,
            f"i_{export}_awvalid" : axi_f2h.aw.valid, f"o_{export}_awready" : axi_f2h.aw.ready,
            f"i_{export}_wdata"   : axi_f2h.w.data,   f"i_{export}_wstrb"   : axi_f2h.w.strb,
            f"i_{export}_wlast"   : axi_f2h.w.last,   f"i_{export}_wvalid"  : axi_f2h.w.valid,
            f"o_{export}_wready"  : axi_f2h.w.ready,
            f"o_{export}_bid"     : axi_f2h.b.id,     f"o_{export}_bresp"   : axi_f2h.b.resp,
            f"o_{export}_bvalid"  : axi_f2h.b.valid,  f"i_{export}_bready"  : axi_f2h.b.ready,
            f"i_{export}_arid"    : axi_f2h.ar.id,    f"i_{export}_araddr"  : axi_f2h.ar.addr,
            f"i_{export}_arlen"   : axi_f2h.ar.len,   f"i_{export}_arsize"  : axi_f2h.ar.size,
            f"i_{export}_arburst" : axi_f2h.ar.burst, f"i_{export}_arlock"  : axi_f2h.ar.lock,
            f"i_{export}_arprot"  : axi_f2h.ar.prot,  f"i_{export}_arcache" : axi_f2h.ar.cache,
            f"i_{export}_arvalid" : axi_f2h.ar.valid, f"o_{export}_arready" : axi_f2h.ar.ready,
            f"o_{export}_rid"     : axi_f2h.r.id,     f"o_{export}_rdata"   : axi_f2h.r.data,
            f"o_{export}_rresp"   : axi_f2h.r.resp,   f"o_{export}_rlast"   : axi_f2h.r.last,
            f"o_{export}_rvalid"  : axi_f2h.r.valid,  f"i_{export}_rready"  : axi_f2h.r.ready,
        })
        self.add_hps_config({"F2H_Width": data_width}) # [VERIFY: exact width param]
        self._export_bridge(export, "f2h", clock_domain)
        return axi_f2h

    # HPS EMIF (LPDDR4 attached to the HPS, Agilex 5/3) --------------------------------------------
    def add_emif(self, pads, refclk_pads, config=None):
        # HPS DDR on Agilex 5/3 goes through an in-fabric EMIF (emif_ph2) connected to the HPS SDRAM
        # initiator; the bitstream must be present for HPS DDR to work.
        assert self.emif is None
        if self.cfg["emif"] != "emif_ph2":
            raise NotImplementedError(f"add_emif() is not supported on {self.variant}.")
        emif_config = {} # [VERIFY: emif_ph2 HPS-mode params from agilex5 GHRD construct_agilex_emif.tcl]
        emif_config.update(config or {})
        self.emif = (pads, refclk_pads, emif_config)

        # Exported EMIF conduits (physical LPDDR4 pins, located by the platform).
        self.cpu_params.update({
            "i_emif_hps_ref_clk_clk"   : refclk_pads.p,
            "o_emif_hps_mem_mem_ck_t"  : pads.clk_p,
            "o_emif_hps_mem_mem_ck_c"  : pads.clk_n,
            "o_emif_hps_mem_mem_cke"   : pads.cke,
            "o_emif_hps_mem_mem_reset_n" : pads.reset_n,
            "o_emif_hps_mem_mem_cs"    : pads.cs,
            "o_emif_hps_mem_mem_ca"    : pads.ca,
            "io_emif_hps_mem_mem_dq"   : pads.dq,
            "io_emif_hps_mem_mem_dqs_t": pads.dqs_p,
            "io_emif_hps_mem_mem_dqs_c": pads.dqs_n,
            "io_emif_hps_mem_mem_dmi"  : pads.dmi,
            "i_emif_hps_oct_oct_rzqin" : pads.rzq,
        })

    # Qsys Export bookkeeping ----------------------------------------------------------------------
    def _export_bridge(self, export, role, clock_domain):
        cfg      = self.cfg
        iface, clk_iface, rst_iface = cfg["if_names"][role]
        # (export_name, hps_interface, qsys_type, direction).
        self.hps_exports += [
            (f"{export}",     iface,     "axi4",  "start" if role != "f2h" else "end"),
            (f"{export}_clk", clk_iface, "clock", "end"),
            (f"{export}_rst", rst_iface, "reset", "end"),
        ]

    # Qsys Tcl Generation --------------------------------------------------------------------------
    def generate_hps_tcl(self):
        cfg = self.cfg
        tcl = []
        tcl.append("package require -exact qsys 24.1") # [VERIFY: version string vs installed Pro]
        tcl.append(f"create_system {self.hps_name}")
        tcl.append(f"set_project_property DEVICE_FAMILY {{{cfg['device_family']}}}")
        tcl.append(f"set_project_property DEVICE {{{self.platform.device}}}")

        # HPS Instance.
        tcl.append(f"add_instance hps {cfg['hps_ip']}")
        for param, value in self.hps_config.items():
            tcl.append(f"set_instance_parameter_value hps {{{param}}} {{{value}}}")

        # HPS-EMIF Instance + connection (Agilex 5/3).
        if self.emif is not None:
            _, _, emif_config = self.emif
            tcl.append(f"add_instance emif_hps {cfg['emif']}")
            for param, value in emif_config.items():
                tcl.append(f"set_instance_parameter_value emif_hps {{{param}}} {{{value}}}")
            # [VERIFY: HPS<->EMIF endpoints from agilex5 GHRD (agilex_hps.emif0_ch0_axi -> emif_hps.s0_axi4)].
            tcl.append("add_connection hps.emif0_ch0_axi emif_hps.s0_axi4")
            tcl.append("set_interface_property emif_hps_mem EXPORT_OF emif_hps.mem_0")
            tcl.append("set_interface_property emif_hps_oct EXPORT_OF emif_hps.oct_0")
            tcl.append("set_interface_property emif_hps_ref_clk EXPORT_OF emif_hps.ref_clk_0")

        # Bridge/IRQ/Reset Exports (deterministic <export>_<role> module ports).
        for export, iface, qsys_type, direction in self.hps_exports:
            tcl.append(f"add_interface {export} {qsys_type} {direction}")
            tcl.append(f"set_interface_property {export} EXPORT_OF hps.{iface}")

        tcl.append("sync_sysinfo_parameters")
        tcl.append(f"save_system {self.hps_name}.qsys")
        return tcl

    def do_finalize(self):
        cfg = self.cfg
        # Interrupt / Reset exports.
        self.cpu_params["i_f2h_irq0_irq"]        = self.interrupt # [VERIFY: irq export name/width]
        self.cpu_params["o_h2f_reset_reset_n"]   = self.h2f_rst_n # [VERIFY: reset export name/polarity]
        self.hps_exports += [
            ("f2h_irq0",  "f2h_irq0",  "interrupt", "receiver"),
            ("h2f_reset", "h2f_reset", "reset",     "start"),
        ]

        # Generate and register the Qsys system (Pro flow), then instantiate it.
        from litex.build.altera.quartus import AlteraQuartusToolchain
        assert isinstance(self.platform.toolchain, AlteraQuartusToolchain)
        self.platform.toolchain.add_qsys_system(self.hps_name, self.generate_hps_tcl())
        self.specials += Instance(self.hps_name, **self.cpu_params)
