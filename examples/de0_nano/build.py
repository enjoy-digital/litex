#!/usr/bin/env python3

import os
from mibuild.platforms import de0nano
import top

def main():
	platform = de0nano.Platform()
	soc = top.SoC(platform)
	
	
	# set extra constraints
	platform.add_platform_command("""
set_global_assignment -name FAMILY "Cyclone IV E"
set_global_assignment -name TOP_LEVEL_ENTITY "top"
set_global_assignment -name VERILOG_INPUT_VERSION SYSTEMVERILOG_2005
""")

	platform.build_cmdline(soc)

if __name__ == "__main__":
	main()