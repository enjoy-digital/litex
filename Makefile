MSCDIR = ../misoc
CURDIR = ../k7sataphy
PYTHON = python3
TOOLCHAIN = ise
PLATFORM = kc705
PROGRAMMER = impact

CMD = $(PYTHON) make.py -X $(CURDIR) -Op toolchain $(TOOLCHAIN) -Op programmer $(PROGRAMMER) -p $(PLATFORM) -t test

csv:
	cd $(MSCDIR) && $(CMD) --csr_csv $(CURDIR)/test/csr.csv build-csr-csv
	cd $(CURDIR)

bit:
	cd $(MSCDIR) && $(CMD) build-bitstream
	cd $(CURDIR)

build: csv bit

load:
	cd $(MSCDIR) && $(CMD) load-bitstream
	cd $(CURDIR)

test:
	cd test && $(PYTHON) test_regs.py
	cd $(CURDIR)

all: build load test

.PHONY: load test all
