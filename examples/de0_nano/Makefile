PYTHON=c:\Python32\python

all: build/de0_nano.sta
# We need to change to the build directory because the Quartus tools
# tend to dump a mess of various files in the current directory.

build/de0_nano.qsf:
	$(PYTHON) build.py

build/de0_nano.map: build/de0_nano.qsf
	cp de0_nano.qpf build/de0_nano.qpf
	cd build && quartus_map de0_nano.qpf
	
build/de0_nano.fit: build/de0_nano.map
	cd build && quartus_fit de0_nano.qpf

build/de0_nano.asm: build/de0_nano.fit
	cd build && quartus_asm de0_nano.qpf

build/de0_nano.sta: build/de0_nano.asm
	cd build && quartus_sta de0_nano.qpf

clean:
	rm -rf build/*

.PHONY: load clean
