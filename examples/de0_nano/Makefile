all: build/soc-de0nano.sta

build/soc-de0nano.sta:
	./make.py

load:
	cd build && quartus_pgm -m jtag -c USB-Blaster[USB-0] -o "p;soc-de0nano.sof"

clean:
	rm -rf build/*

.PHONY: load clean
