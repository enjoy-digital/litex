include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

OBJECTS=isr.o sdram.o main.o boot-helper-$(CPU).o boot.o dataflow.o

all: bios.bin

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	chmod -x $@
	$(PYTHON) -m misoc.tools.mkmscimg $@

bios.elf: $(BIOS_DIRECTORY)/linker.ld $(OBJECTS)

%.elf:
	$(LD) $(LDFLAGS) -T $< -N -o $@ \
		../libbase/crt0-$(CPU).o \
		$(OBJECTS) \
		-L../libnet \
		-L../libbase \
		-L../libcompiler_rt \
		-lnet -lbase-nofloat -lcompiler_rt
	chmod -x $@

main.o: $(BIOS_DIRECTORY)/main.c
	$(compile)

%.o: $(BIOS_DIRECTORY)/%.c
	$(compile)

%.o: $(BIOS_DIRECTORY)/%.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) bios.elf bios.bin .*~ *~

.PHONY: all clean main.o
