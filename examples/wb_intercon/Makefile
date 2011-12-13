SOURCES=tb_intercon.v intercon.v master.v slave.v

all: tb_intercon

sim: tb_intercon
	./tb_intercon

cversim: $(SOURCES)
	cver $(SOURCES)

clean:
	rm -f tb_intercon intercon.v intercon.vcd verilog.log

tb_intercon: $(SOURCES)
	iverilog -o tb_intercon $(SOURCES)

intercon.v: intercon_conv.py
	python3 intercon_conv.py > intercon.v

.PHONY: clean sim cversim
