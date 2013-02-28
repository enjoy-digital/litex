import os
from mibuild.platforms import de0nano
from mibuild.altera_quartus import _add_period_constraint
import top

def main():
	plat = de0nano.Platform()
	soc = top.SoC()
	
	# set pin constraints
	plat.request("clk50", obj=soc.clk50)
	plat.request("key", obj=soc.key)
	plat.request("led", obj=soc.led)
	plat.request("gpio_2", obj=soc.gpio_2)
	
	# set extra constraints
	plat.add_platform_command("""
set_global_assignment -name FAMILY "Cyclone IV E"
set_global_assignment -name TOP_LEVEL_ENTITY "top"
set_global_assignment -name VERILOG_INPUT_VERSION SYSTEMVERILOG_2005
set_global_assignment -name CYCLONEII_RESERVE_NCEO_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_FLASH_NCE_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DATA0_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DATA1_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DCLK_AFTER_CONFIGURATION "USE AS REGULAR IO"
""")

	_add_period_constraint(plat, "sys_clk", 20.0)
	cd = dict()
	cd["sys"] = soc.cd_sys
	plat.build_cmdline(soc.get_fragment(), clock_domains=cd)

if __name__ == "__main__":
	main()