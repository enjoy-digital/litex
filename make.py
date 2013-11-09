#!/usr/bin/env python3

import argparse, os, importlib, subprocess

from mibuild.tools import write_to_file

from misoclib import cpuif
from misoclib.s6ddrphy import initsequence
import top, jtag

def build(platform_name, build_bitstream, build_header, csr_csv_filename, *soc_args, **soc_kwargs):
	platform_module = importlib.import_module("mibuild.platforms."+platform_name)
	platform = platform_module.Platform()
	soc = top.SoC(platform, platform_name, *soc_args, **soc_kwargs)
	
	platform.add_platform_command("""
INST "mxcrg/wr_bufpll" LOC = "BUFPLL_X0Y2";
INST "mxcrg/rd_bufpll" LOC = "BUFPLL_X0Y3";

PIN "mxcrg/bufg_x1.O" CLOCK_DEDICATED_ROUTE = FALSE;
PIN "dviout_pix_bufg.O" CLOCK_DEDICATED_ROUTE = FALSE;
""")

	if hasattr(soc, "fb"):
		platform.add_platform_command("""
NET "{vga_clk}" TNM_NET = "GRPvga_clk";
NET "sys_clk" TNM_NET = "GRPsys_clk";
TIMESPEC "TSise_sucks1" = FROM "GRPvga_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSise_sucks2" = FROM "GRPsys_clk" TO "GRPvga_clk" TIG;
""", vga_clk=soc.fb.driver.clocking.cd_pix.clk)

	for d in ["mxcrg", "minimac3"]:
		platform.add_source_dir(os.path.join("verilog", d))
	platform.add_sources(os.path.join("verilog", "lm32", "submodule", "rtl"), 
		"lm32_cpu.v", "lm32_instruction_unit.v", "lm32_decoder.v",
		"lm32_load_store_unit.v", "lm32_adder.v", "lm32_addsub.v", "lm32_logic_op.v",
		"lm32_shifter.v", "lm32_multiplier.v", "lm32_mc_arithmetic.v",
		"lm32_interrupt.v", "lm32_ram.v", "lm32_dp_ram.v", "lm32_icache.v",
		"lm32_dcache.v", "lm32_top.v", "lm32_debug.v", "lm32_jtag.v", "jtag_cores.v",
		"jtag_tap_spartan6.v", "lm32_itlb.v", "lm32_dtlb.v")
	platform.add_sources(os.path.join("verilog", "lm32"), "lm32_config.v")

	if build_bitstream:
		build_name = "soc-"+platform_name
		platform.build(soc, build_name=build_name)
		subprocess.call(["tools/byteswap", "build/"+build_name+".bin", "build/"+build_name+".fpg"])
	else:
		soc.finalize()
	if build_header:
		csr_header = cpuif.get_csr_header(soc.csr_base, soc.csrbankarray, soc.interrupt_map)
		write_to_file("software/include/hw/csr.h", csr_header)
		
		sdram_phy_header = initsequence.get_sdram_phy_header(soc.ddrphy)
		write_to_file("software/include/hw/sdram_phy.h", sdram_phy_header)
	if csr_csv_filename:
		csr_csv = cpuif.get_csr_csv(soc.csr_base, soc.csrbankarray)
		write_to_file(csr_csv_filename, csr_csv)

def main():
	parser = argparse.ArgumentParser(description="MiSoC - a high performance SoC based on Migen.")
	parser.add_argument("-p", "--platform", default="mixxeo", help="platform to build for")
	parser.add_argument("-B", "--no-bitstream", default=False, action="store_true", help="do not build bitstream file")
	parser.add_argument("-H", "--no-header", default=False, action="store_true", help="do not build C header files with CSR/IRQ/SDRAM_PHY defs")
	parser.add_argument("-c", "--csr-csv", default="", help="save CSR map in CSV file")
	parser.add_argument("-l", "--load", default=False, action="store_true", help="load bitstream to SRAM")
	parser.add_argument("-f", "--flash", default=False, action="store_true", help="load bitstream to flash")
	parser.add_argument("-m", "--with-memtest", default=False, action="store_true", help="include memtest cores")
	args = parser.parse_args()

	build(args.platform, not args.no_bitstream, not args.no_header, args.csr_csv, args.with_memtest)
	if args.load:
		jtag.load("build/soc-"+args.platform+".bit")
	if args.flash:
		jtag.flash("build/soc-"+args.platform+".fpg")

if __name__ == "__main__":
	main()
