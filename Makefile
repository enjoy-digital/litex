PYTHON=python3

all: build/soc.bit

# We need to change to the build directory because the Xilinx tools
# tend to dump a mess of various files in the current directory.

build/soc.prj build/soc.ucf:
	$(PYTHON) build.py

build/soc.ngc: build/soc.prj
	cd build && xst -ifn ../soc.xst

build/soc.ngd: build/soc.ngc build/soc.ucf
	cd build && ngdbuild -uc soc.ucf soc.ngc

build/soc.ncd: build/soc.ngd
	cd build && map -ol high -w soc.ngd

build/soc-routed.ncd: build/soc.ncd
	cd build && par -ol high -w soc.ncd soc-routed.ncd

build/soc.bit build/soc.bin: build/soc-routed.ncd
	cd build && bitgen -g LCK_cycle:6 -g Binary:Yes -g INIT_9K:Yes -w soc-routed.ncd soc.bit

load: build/soc.bit
	jtag -n load.jtag

clean:
	rm -rf build/*

.PHONY: load clean
