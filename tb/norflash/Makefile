SOURCES=tb_norflash.v norflash.v

all: tb_norflash

isim: tb_norflash
	./tb_norflash

cversim: $(SOURCES)
	cver $(SOURCES)

norflash.v: norflash_conv.py
	python3 norflash_conv.py > norflash.v

clean:
	rm -f tb_norflash verilog.log norflash.vcd norflash.v

tb_norflash: $(SOURCES)
	iverilog -o tb_norflash $(SOURCES)

.PHONY: clean sim cversim
