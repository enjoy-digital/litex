PYTHON=

all: build/soc.map

# We need to change to the build directory because the Quartus tools
# tend to dump a mess of various files in the current directory.

build/soc.qsf:
	$(PYTHON) build.py

build/soc.map: build/soc.qsf
	cp soc.qpf build/de0_nano.qpf
	cd build && quartus_map de0_nano.qpf

clean:
	rm -rf build/*

.PHONY: load clean
