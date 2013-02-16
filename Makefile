all: build/top.bit

build/top.bit build/top.bin:
	./build.py

load: build/top.bit
	jtag -n load.jtag

clean:
	rm -rf build/*

.PHONY: load clean
