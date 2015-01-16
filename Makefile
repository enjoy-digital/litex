MSCDIR = ../misoc
CURDIR = ../lite-sata
PYTHON = python3
TOOLCHAIN = vivado
PROGRAMMER = vivado

CMD = $(PYTHON) make.py -X $(CURDIR) -Op toolchain $(TOOLCHAIN) -Op programmer $(PROGRAMMER) -t bist_kc705

csv:
	cd $(MSCDIR) && $(CMD) --csr_csv $(CURDIR)/test/csr.csv build-csr-csv -Ot export_mila True
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
