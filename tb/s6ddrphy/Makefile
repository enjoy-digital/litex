SOURCES=tb_s6ddrphy.v ../../verilog/s6ddrphy/s6ddrphy.v \
	$(XILINX)/verilog/src/unisims/ODDR2.v \
	$(XILINX)/verilog/src/unisims/OSERDES2.v \
	$(XILINX)/verilog/src/unisims/ISERDES2.v \
	$(XILINX)/verilog/src/unisims/IOBUF.v \
	$(XILINX)/verilog/src/unisims/OBUFT.v \
	$(XILINX)/verilog/src/unisims/BUFPLL.v

RM ?= rm -f

all: tb_s6ddrphy

isim: tb_s6ddrphy
	./tb_s6ddrphy

cversim: $(SOURCES)
	cver $(SOURCES)

clean:
	$(RM) tb_s6ddrphy verilog.log s6ddrphy.vcd

tb_s6ddrphy: $(SOURCES)
	iverilog -o tb_s6ddrphy $(SOURCES)

.PHONY: all clean isim cversim
