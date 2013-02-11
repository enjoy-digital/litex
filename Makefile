all: build/soc.bit

build/soc.bit build/soc.bin:
	./build.py

load: build/soc.bit
	jtag -n load.jtag

clean:
	rm -rf build/*

.PHONY: load clean
