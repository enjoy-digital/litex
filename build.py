#!/usr/bin/env python3

import os
from mibuild.platforms import m1
import top

def main():
	plat = m1.Platform()
	soc = top.SoC()
	
	# set pin constraints
	plat.request("clk50", obj=soc.crg.clk50_pad)
	plat.request("user_btn", 1, obj=soc.crg.trigger_reset)
	plat.request("norflash_rst_n", obj=soc.crg.norflash_rst_n)
	plat.request("vga_clock", obj=soc.crg.vga_clk_pad)
	plat.request("ddram_clock", obj=soc.crg, name_map=lambda s: "ddr_clk_pad_" + s)
	plat.request("eth_clocks", obj=soc.crg, name_map=lambda s: "eth_" + s + "_clk_pad")
	
	plat.request("norflash", obj=soc.norflash)
	plat.request("serial", obj=soc.uart)
	plat.request("ddram", obj=soc.ddrphy, name_map=lambda s: "sd_" + s)
	plat.request("eth", obj=soc.minimac, name_map=lambda s: "phy_" + s)
	plat.request("vga", obj=soc.fb, name_map=lambda s: "vga_" + s)
	plat.request("dvi_in", 0, obj=soc.dvisampler0)
	plat.request("dvi_in", 1, obj=soc.dvisampler1)
	
	# set extra constraints
	plat.add_platform_command("""
NET "{clk50}" TNM_NET = "GRPclk50";
TIMESPEC "TSclk50" = PERIOD "GRPclk50" 20 ns HIGH 50%;
INST "m1crg/wr_bufpll" LOC = "BUFPLL_X0Y2";
INST "m1crg/rd_bufpll" LOC = "BUFPLL_X0Y3";

PIN "m1crg/bufg_x1.O" CLOCK_DEDICATED_ROUTE = FALSE;

NET "{phy_rx_clk}" TNM_NET = "GRPphy_rx_clk";
NET "{phy_tx_clk}" TNM_NET = "GRPphy_tx_clk";
TIMESPEC "TSphy_rx_clk" = PERIOD "GRPphy_rx_clk" 40 ns HIGH 50%;
TIMESPEC "TSphy_tx_clk" = PERIOD "GRPphy_tx_clk" 40 ns HIGH 50%;
TIMESPEC "TSphy_tx_clk_io" = FROM "GRPphy_tx_clk" TO "PADS" 10 ns;
TIMESPEC "TSphy_rx_clk_io" = FROM "PADS" TO "GRPphy_rx_clk" 10 ns;

NET "asfifo*/counter_read/gray_count*" TIG;
NET "asfifo*/counter_write/gray_count*" TIG;
NET "asfifo*/preset_empty*" TIG;
""",
		clk50=soc.crg.clk50_pad,
		phy_rx_clk=soc.crg.eth_rx_clk_pad,
		phy_tx_clk=soc.crg.eth_tx_clk_pad)
	
	# add Verilog sources
	for d in ["generic", "m1crg", "s6ddrphy", "minimac3"]:
		plat.add_source_dir(os.path.join("verilog", d))
	plat.add_sources(os.path.join("verilog", "lm32", "submodule", "rtl"), 
		"lm32_cpu.v", "lm32_instruction_unit.v", "lm32_decoder.v",
		"lm32_load_store_unit.v", "lm32_adder.v", "lm32_addsub.v", "lm32_logic_op.v",
		"lm32_shifter.v", "lm32_multiplier.v", "lm32_mc_arithmetic.v",
		"lm32_interrupt.v", "lm32_ram.v", "lm32_dp_ram.v", "lm32_icache.v",
		"lm32_dcache.v", "lm32_top.v", "lm32_debug.v", "lm32_jtag.v", "jtag_cores.v",
		"jtag_tap_spartan6.v", "lm32_itlb.v", "lm32_dtlb.v")
	plat.add_sources(os.path.join("verilog", "lm32"), "lm32_config.v")
	
	plat.build_cmdline(soc)

if __name__ == "__main__":
	main()
