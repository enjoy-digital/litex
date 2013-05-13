RM ?= rm -f

all: build/top.bit build/top.fpg

build/top.bit build/top.bin:
	./build.py

build/top.fpg: build/top.bin
	$(MAKE) -C tools
	tools/byteswap $< $@

load: build/top.bit
	jtag -n load.jtag

clean:
	$(RM) -r build/*

.PHONY: all load clean
