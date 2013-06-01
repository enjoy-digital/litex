RM ?= rm -f

all: build/soc.bit build/soc.fpg

build/soc.bit build/soc.bin:
	./build.py

build/soc.fpg: build/soc.bin
	$(MAKE) -C tools
	tools/byteswap $< $@

load: build/soc.bit
	jtag -n load.jtag

flash: build/soc.fpg
	m1nor-ng build/soc.fpg

clean:
	$(RM) -r build/*

.PHONY: all load clean flash
