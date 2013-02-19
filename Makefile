all: build/top.bit build/top.fpg

build/top.bit build/top.bin:
	./build.py

build/top.fpg: build/top.bin
	make -C tools
	tools/byteswap $< $@

load: build/top.bit
	jtag -n load.jtag

clean:
	rm -rf build/*

.PHONY: load clean
