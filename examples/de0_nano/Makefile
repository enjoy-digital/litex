all: build/top.sta

build/top.sta:
	./build.py

load:
	cd build && quartus_pgm -m jtag -c USB-Blaster[USB-0] -o "p;top.sof"


clean:
	rm -rf build/*

.PHONY: load clean
