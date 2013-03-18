#!/usr/bin/env python3

import os
from mibuild.platforms import de0nano
import top

def main():
	plat = de0nano.Platform()
	soc = top.SoC()
	
	# set pin constraints
	plat.request("led", 0, obj=soc.led)
	
	#plat.request("led", 4, obj=soc.uart_rx_event.o)
	#plat.request("led", 5, obj=soc.uart_tx_event.o)
	#plat.request("led", 7, obj=soc.debug_event.o)
	plat.request("serial", 0, obj=soc.uart2csr)
	
	# set extra constraints
	plat.add_platform_command("""
set_global_assignment -name FAMILY "Cyclone IV E"
set_global_assignment -name TOP_LEVEL_ENTITY "top"
set_global_assignment -name VERILOG_INPUT_VERSION SYSTEMVERILOG_2005
""")

	plat.build_cmdline(soc.get_fragment())

if __name__ == "__main__":
	main()