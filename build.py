#!/usr/bin/env python3

import os

from mibuild.platforms import m1
from mibuild.tools import write_to_file

import top
import cif

def main():
	platform = m1.Platform()
	soc = top.SoC(platform)
	
	platform.add_platform_command("""
NET "{clk50}" TNM_NET = "GRPclk50";
TIMESPEC "TSclk50" = PERIOD "GRPclk50" 20 ns HIGH 50%;
""", clk50=platform.lookup_request("clk50"))

	platform.add_platform_command("""
INST "m1crg/wr_bufpll" LOC = "BUFPLL_X0Y2";
INST "m1crg/rd_bufpll" LOC = "BUFPLL_X0Y3";

PIN "m1crg/bufg_x1.O" CLOCK_DEDICATED_ROUTE = FALSE;
""")

	if hasattr(soc, "fb"):
		platform.add_platform_command("""
NET "vga_clk" TNM_NET = "GRPvga_clk";
NET "sys_clk" TNM_NET = "GRPsys_clk";
TIMESPEC "TSise_sucks1" = FROM "GRPvga_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSise_sucks2" = FROM "GRPsys_clk" TO "GRPvga_clk" TIG;
""")

	if hasattr(soc, "minimac"):
		platform.add_platform_command("""
NET "{phy_rx_clk}" TNM_NET = "GRPphy_rx_clk";
NET "{phy_tx_clk}" TNM_NET = "GRPphy_tx_clk";
TIMESPEC "TSphy_rx_clk" = PERIOD "GRPphy_rx_clk" 40 ns HIGH 50%;
TIMESPEC "TSphy_tx_clk" = PERIOD "GRPphy_tx_clk" 40 ns HIGH 50%;
TIMESPEC "TSphy_tx_clk_io" = FROM "GRPphy_tx_clk" TO "PADS" 10 ns;
TIMESPEC "TSphy_rx_clk_io" = FROM "PADS" TO "GRPphy_rx_clk" 10 ns;
""",
		phy_rx_clk=platform.lookup_request("eth_clocks").rx,
		phy_tx_clk=platform.lookup_request("eth_clocks").tx,)

	if hasattr(soc, "dvisampler0"):
		platform.add_platform_command("""
NET "{dviclk0}" TNM_NET = "GRPdviclk0";
NET "{dviclk0}" CLOCK_DEDICATED_ROUTE = FALSE;
TIMESPEC "TSdviclk0" = PERIOD "GRPdviclk0" 26.7 ns HIGH 50%;
""", dviclk0=platform.lookup_request("dvi_in", 0).clk)
	if hasattr(soc, "dvisampler1"):
		platform.add_platform_command("""
NET "{dviclk1}" TNM_NET = "GRPdviclk1";
NET "{dviclk1}" CLOCK_DEDICATED_ROUTE = FALSE;
TIMESPEC "TSdviclk1" = PERIOD "GRPdviclk1" 26.7 ns HIGH 50%;
""", dviclk1=platform.lookup_request("dvi_in", 1).clk)
	
	for d in ["m1crg", "s6ddrphy", "minimac3"]:
		platform.add_source_dir(os.path.join("verilog", d))
	platform.add_sources(os.path.join("verilog", "lm32", "submodule", "rtl"), 
		"lm32_cpu.v", "lm32_instruction_unit.v", "lm32_decoder.v",
		"lm32_load_store_unit.v", "lm32_adder.v", "lm32_addsub.v", "lm32_logic_op.v",
		"lm32_shifter.v", "lm32_multiplier.v", "lm32_mc_arithmetic.v",
		"lm32_interrupt.v", "lm32_ram.v", "lm32_dp_ram.v", "lm32_icache.v",
		"lm32_dcache.v", "lm32_top.v", "lm32_debug.v", "lm32_jtag.v", "jtag_cores.v",
		"jtag_tap_spartan6.v", "lm32_itlb.v", "lm32_dtlb.v")
	platform.add_sources(os.path.join("verilog", "lm32"), "lm32_config.v")

	platform.build_cmdline(soc)
	csr_header = cif.get_csr_header(soc.csr_base, soc.csrbankarray, soc.interrupt_map)
	write_to_file("software/include/hw/csr.h", csr_header)

if __name__ == "__main__":
	main()
