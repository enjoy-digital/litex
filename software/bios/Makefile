MSCDIR=../..
include $(MSCDIR)/software/common.mak
PYTHON = python3

OBJECTS=isr.o sdram.o main.o boot-helper.o boot.o dataflow.o

all: bios.bin

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	chmod -x $@
	$(PYTHON) $(MSCDIR)/mkmscimg.py -i $@

bios.elf: linker.ld $(OBJECTS) libs

%.elf:
	$(LD) $(LDFLAGS) -T $< -N -o $@ \
		$(MSCDIR)/software/libbase/crt0.o \
		$(OBJECTS) \
		-L$(MSCDIR)/software/libnet \
		-L$(MSCDIR)/software/libbase \
		-L$(MSCDIR)/software/libcompiler-rt \
		-lnet -lbase-nofloat -lcompiler-rt
	chmod -x $@

main.o: main.c
	$(compile-dep)

%.o: %.c
	$(compile-dep)

%.o: %.S
	$(assemble)

libs:
	$(MAKE) -C $(MSCDIR)/software/libcompiler-rt
	$(MAKE) -C $(MSCDIR)/software/libbase
	$(MAKE) -C $(MSCDIR)/software/libnet

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) bios.elf bios.bin .*~ *~

.PHONY: all main.o clean libs
