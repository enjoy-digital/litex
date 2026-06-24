#
# This file is part of LiteX.
#
# Copyright (c) 2022-2026 Florent Kermarrec <florent@enjoy-digital.fr>
#               2023 Protech Engineering <m.marzaro@protechgoup.it>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex.build.vhd2v_converter import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32
from litex.soc.integration.soc import SoCRegion

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = [
    "minimal",
    "minimal+debug",
    "lite",
    "lite+debug",
    "standard",
    "standard+debug",
    "full",
    "full+debug",
    "numa",
    "numa+debug",
]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                               /------------ Base ISA
    #                               |    /------- Hardware Multiply + Divide
    #                               |    |/----- Atomics
    #                               |    ||/---- Compressed ISA
    #                               |    |||/--- Single-Precision Floating-Point
    #                               |    ||||/-- Double-Precision Floating-Point
    #                               i    macfd
    "minimal":          "-march=rv32i2p0      -mabi=ilp32",
    "minimal+debug":    "-march=rv32i2p0      -mabi=ilp32",
    "lite":             "-march=rv32i2p0_mc   -mabi=ilp32",
    "lite+debug":       "-march=rv32i2p0_mc   -mabi=ilp32",
    "standard":         "-march=rv32i2p0_mc   -mabi=ilp32",
    "standard+debug":   "-march=rv32i2p0_mc   -mabi=ilp32",
    "full":             "-march=rv32i2p0_mc   -mabi=ilp32",
    "full+debug":       "-march=rv32i2p0_mc   -mabi=ilp32",
    "numa":             "-march=rv32i2p0_ac   -mabi=ilp32",
    "numa+debug":       "-march=rv32i2p0_ac   -mabi=ilp32",
}

# NEORV32 ------------------------------------------------------------------------------------------

class NEORV32(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "neorv32"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0xF000_0000: 0x0FFF_BFFF} # Origin, Length.
    cpu_count            = 1

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  GCC_FLAGS[self.variant]
        flags += " -D__neorv32__ "
        return flags

    # Command line configuration arguments.
    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group(title="CPU options")

        cpu_group.add_argument("--cpu-count", default=1, type=int, help="How many Neorv32 CPU.")

    @staticmethod
    def args_read(args):
        NEORV32.cpu_count = args.cpu_count

    def __init__(self, platform, variant="standard"):
        if self.cpu_count not in [1, 2]:
            raise ValueError("NEORV32 supports 1 or 2 CPU cores.")

        self.platform     = platform
        self.variant      = variant
        self.human_name   = f"NEORV32-{variant}"
        self.reset        = Signal()
        self.with_bursting = variant.split("+")[0] in ["full", "numa"]
        # Peripheral buses (Connected to main SoC's bus).
        self.periph_buses = [
            wishbone.Interface(
                data_width    = 32,
                address_width = 32,
                addressing    = "byte",
                bursting      = self.with_bursting,
            )
        ]
        # Memory buses (Connected directly to LiteDRAM).
        self.memory_buses = []

        # # #

        # CPU Instance.
        wb_stb = Signal()
        wb_cyc = Signal()
        cpu_params = dict(
            # Clk/Rst.
            i_clk_i  = ClockSignal("sys"),
            i_rstn_i = ~(ResetSignal() | self.reset),

            # JTAG.
            i_jtag_tck_i  = 0,
            i_jtag_tdi_i  = 0,
            o_jtag_tdo_o  = Open(),
            i_jtag_tms_i  = 0,

            # Interrupt.
            i_irq_mei_i = 0,

            # I/D Wishbone Bus.
            o_wb_adr_o = self.periph_buses[0].adr,
            i_wb_dat_i = self.periph_buses[0].dat_r,
            o_wb_dat_o = self.periph_buses[0].dat_w,
            o_wb_we_o  = self.periph_buses[0].we,
            o_wb_sel_o = self.periph_buses[0].sel,
            o_wb_stb_o = wb_stb,
            o_wb_cyc_o = wb_cyc,
            o_wb_cti_o = self.periph_buses[0].cti,
            i_wb_ack_i = self.periph_buses[0].ack,
            i_wb_err_i = self.periph_buses[0].err,

            p_CONFIG = {
                "minimal"        : 0,
                "minimal+debug"  : 0,
                "lite"           : 1,
                "lite+debug"     : 1,
                "standard"       : 2,
                "standard+debug" : 2,
                "full"           : 3,
                "full+debug"     : 3,
                "numa"           : 4,
                "numa+debug"     : 4,
            }[self.variant],
            p_DEBUG     = "debug" in self.variant,
            p_DUAL_CORE = self.cpu_count == 2,
        )
        # NEORV32's XBUS can pulse stb while keeping cyc asserted for the
        # pending access; LiteX Wishbone slaves expect stb until ack.
        self.comb += [
            self.periph_buses[0].stb.eq(wb_cyc),
            self.periph_buses[0].cyc.eq(wb_cyc),
            self.periph_buses[0].bte.eq(0),
        ]

        # TODO
        if "debug" in variant:
            self.add_debug(cpu_params)

        self.vhd2v_converter = VHD2VConverter(self.platform,
            name          = "neorv32_litex_core_complex",
            library       = "neorv32",
            force_convert = True,
            ports         = cpu_params,
        )
        self.add_sources(self.vhd2v_converter)

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "rom"       : 0x0000_0000,
            "sram"      : 0x0100_0000,
            "main_ram"  : 0x4000_0000,
            "dmem"      : 0x8000_0000,
            "csr"       : 0xF000_0000,
        }

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        assert reset_address == 0x0000_0000

    def add_debug(self, cpu_params):
        if not hasattr(self, "i_jtag_tck"):
            self.i_jtag_tck = Signal()
            self.i_jtag_tdi = Signal()
            self.o_jtag_tdo = Signal()
            self.i_jtag_tms = Signal()
        else:
            self.o_jtag_tdi = self.i_jtag_tdo
            self.i_jtag_tdo = Signal()

        cpu_params.update(
            i_jtag_tck_i  = self.i_jtag_tck,
            i_jtag_tdi_i  = self.i_jtag_tdi,
            o_jtag_tdo_o  = self.o_jtag_tdo,
            i_jtag_tms_i  = self.i_jtag_tms,
        )

    @staticmethod
    def _patch_litex_wrapper(filename):
        def replace_once(content, old, new, marker):
            if marker in content:
                return content
            if old not in content:
                raise OSError(f"Unable to patch NEORV32 LiteX wrapper: {marker}.")
            return content.replace(old, new, 1)

        with open(filename, "r") as f:
            content = f.read()

        content = replace_once(
            content,
            "    CONFIG : natural; -- configuration select (0=minimal, 1=lite, 2=standard, 3=full)\n"
            "    DEBUG  : boolean  -- enable on-chip debugger, valid for all configurations\n",
            "    CONFIG    : natural; -- configuration select (0=minimal, 1=lite, 2=standard, 3=full)\n"
            "    DEBUG     : boolean; -- enable on-chip debugger, valid for all configurations\n"
            "    DUAL_CORE : boolean  -- enable native dual-core mode\n",
            "DUAL_CORE : boolean",
        )
        content = replace_once(
            content,
            "    wb_cyc_o   : out std_ulogic; -- valid cycle\n"
            "    wb_ack_i   : in  std_ulogic; -- transfer acknowledge\n",
            "    wb_cyc_o   : out std_ulogic; -- valid cycle\n"
            "    wb_cti_o   : out std_ulogic_vector(2 downto 0); -- cycle type\n"
            "    wb_ack_i   : in  std_ulogic; -- transfer acknowledge\n",
            "wb_cti_o   : out std_ulogic_vector(2 downto 0)",
        )
        content = replace_once(
            content,
            "    CLOCK_FREQUENCY       => 0,                              -- clock frequency of clk_i in Hz [not required by the core complex]\n",
            "    CLOCK_FREQUENCY       => 0,                              -- clock frequency of clk_i in Hz [not required by the core complex]\n"
            "    DUAL_CORE_EN          => DUAL_CORE,                      -- enable native dual-core mode\n",
            "DUAL_CORE_EN          => DUAL_CORE,",
        )
        if "CACHE_BURSTS_EN       => false," in content:
            content = content.replace(
                "    CACHE_BURSTS_EN       => false,\n",
                "    CACHE_BURSTS_EN       => true,\n",
                1,
            )
        else:
            content = replace_once(
                content,
                "    ICACHE_EN             => configs_c.icache(CONFIG),\n",
                "    ICACHE_EN             => configs_c.icache(CONFIG),\n"
                "    CACHE_BURSTS_EN       => true,\n",
                "CACHE_BURSTS_EN       => true,",
            )
        content = replace_once(
            content,
            "    xbus_cyc_o => wb_cyc_o,   -- valid cycle\n"
            "    xbus_dat_i => wb_dat_i,   -- read data\n",
            "    xbus_cyc_o => wb_cyc_o,   -- valid cycle\n"
            "    xbus_cti_o => wb_cti_o,   -- cycle type\n"
            "    xbus_dat_i => wb_dat_i,   -- read data\n",
            "xbus_cti_o => wb_cti_o,",
        )

        with open(filename, "w") as f:
            f.write(content)

    def add_sources(self, vhd2v_converter):
        cdir = os.path.abspath(os.path.dirname(__file__))
        # List VHDL sources.
        sources = {
            "core" : [
                "neorv32_application_image.vhd",
                "neorv32_bootloader_image.vhd",
                "neorv32_boot_rom.vhd",
                "neorv32_bus.vhd",
                "neorv32_cache.vhd",
                "neorv32_cfs.vhd",
                "neorv32_clint.vhd",
                "neorv32_cpu_alu.vhd",
                "neorv32_cpu_control.vhd",
                "neorv32_cpu_counters.vhd",
                "neorv32_cpu_cp_bitmanip.vhd",
                "neorv32_cpu_cp_cfu.vhd",
                "neorv32_cpu_cp_cond.vhd",
                "neorv32_cpu_cp_crypto.vhd",
                "neorv32_cpu_cp_fpu.vhd",
                "neorv32_cpu_cp_muldiv.vhd",
                "neorv32_cpu_cp_shifter.vhd",
                "neorv32_cpu_decompressor.vhd",
                "neorv32_cpu_frontend.vhd",
                "neorv32_cpu_hwtrig.vhd",
                "neorv32_cpu_lsu.vhd",
                "neorv32_cpu_pmp.vhd",
                "neorv32_cpu_regfile.vhd",
                "neorv32_cpu_trace.vhd",
                "neorv32_cpu.vhd",
                "neorv32_debug_auth.vhd",
                "neorv32_debug_dm.vhd",
                "neorv32_debug_dtm.vhd",
                "neorv32_dma.vhd",
                "neorv32_dmem.vhd",
                "neorv32_gpio.vhd",
                "neorv32_gptmr.vhd",
                "neorv32_imem.vhd",
                "neorv32_neoled.vhd",
                "neorv32_onewire.vhd",
                "neorv32_package.vhd",
                "neorv32_prim.vhd",
                "neorv32_pwm.vhd",
                "neorv32_sdi.vhd",
                "neorv32_slink.vhd",
                "neorv32_spi.vhd",
                "neorv32_sysinfo.vhd",
                "neorv32_sys.vhd",
                "neorv32_top.vhd",
                "neorv32_tracer.vhd",
                "neorv32_trng.vhd",
                "neorv32_twd.vhd",
                "neorv32_twi.vhd",
                "neorv32_uart.vhd",
                "neorv32_wdt.vhd",
                "neorv32_xbus.vhd",
            ],

            "system_integration": [
                "neorv32_litex_core_complex.vhd",
            ],
        }

        # Download VHDL sources (if not already present).
        # Version 1.12.6.2
        sha1       = "e8a44708ee07d396ab4c4495a1638f25e2d6e9b0"
        hw_version = 'x"01120602"'
        base_url   = f"https://raw.githubusercontent.com/stnolting/neorv32/{sha1}/rtl"

        # Older LiteX versions cached NEORV32 files directly in cdir. Avoid
        # mixing those stale sources with the currently pinned NEORV32 revision.
        source_dir = cdir
        package    = os.path.join(cdir, "neorv32_package.vhd")
        if os.path.exists(package):
            with open(package, "r") as f:
                if hw_version not in f.read():
                    source_dir = os.path.join(cdir, "sources", sha1)
        os.makedirs(source_dir, exist_ok=True)

        for directory, vhds in sources.items():
            for vhd in vhds:
                source = os.path.join(source_dir, vhd)
                vhd2v_converter.add_source(source)
                if not os.path.exists(source):
                    os.system(f"wget {base_url}/{directory}/{vhd} -P {source_dir}")

        self._patch_litex_wrapper(os.path.join(source_dir, "neorv32_litex_core_complex.vhd"))

    def add_soc_components(self, soc):
        # The NEORV32 cache can issue incrementing XBUS bursts. Request burst-aware
        # Wishbone SRAMs before the default ROM/SRAM are instantiated.
        if self.with_bursting and soc.bus.standard == "wishbone":
            soc.bus.bursting = True
        soc.bus.add_region("dmem", SoCRegion(origin=self.mem_map["dmem"], size=8*1024, cached=True, linker=True))
        soc.add_config("CPU_COUNT", self.cpu_count)

    def do_finalize(self):
        assert hasattr(self, "reset_address")
