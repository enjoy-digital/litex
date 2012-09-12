PYTHON=c:\Python32\python

all: build/de1.sta
# We need to change to the build directory because the Quartus tools
# tend to dump a mess of various files in the current directory.

build/de1.qsf:
	$(PYTHON) build.py

build/de1.map: build/de1.qsf
	cp de1.qpf build/de1.qpf
	cp de1.sdc build/de1.sdc	
	cd build && quartus_map de1.qpf
	
build/de1.fit: build/de1.map
	cd build && quartus_fit de1.qpf

build/de1.asm: build/de1.fit
	cd build && quartus_asm de1.qpf

build/de1.sta: build/de1.asm
	cd build && quartus_sta de1.qpf

load:
	cd build && quartus_pgm.exe -m jtag -c USB-Blaster[USB-0] -o "p;de1.sof"

clean:
	rm -rf build/*

.PHONY: load clean
