PYTHON=C:\Python32\python

all: build/top.sta

build/top.sta:
	cp top.sdc build/top.sdc
	$(PYTHON) build.py
	
load:
	cd build && quartus_pgm.exe -m jtag -c USB-Blaster[USB-0] -o "p;top.sof"
	
clean:
	rm -rf build/*

.PHONY: load clean
