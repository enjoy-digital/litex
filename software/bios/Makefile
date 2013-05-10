M2DIR=../..
include $(M2DIR)/software/common.mak

OBJECTS=crt0.o isr.o sdram.o main.o boot-helper.o boot.o dataflow.o

all: bios.bin

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.bin: %.elf
	$(MAKE) -C $(M2DIR)/tools
	$(OBJCOPY) -O binary $< $@
	chmod -x $@
	$(M2DIR)/tools/mkmmimg $@ write

bios.elf: linker.ld $(OBJECTS) libs
bios-rescue.elf: linker-rescue.ld $(OBJECTS) libs

%.elf:
	$(LD) $(LDFLAGS) -T $< -N -o $@ $(OBJECTS) \
		-L$(M2DIR)/software/libnet \
		-L$(M2DIR)/software/libbase \
		-L$(M2DIR)/software/libcompiler-rt \
		-lnet -lbase -lcompiler-rt
	chmod -x $@

main.o: main.c
	$(compile-dep)

%.o: %.c
	$(compile-dep)

%.o: %.S
	$(assemble)

libs:
	$(MAKE) -C $(M2DIR)/software/libcompiler-rt
	$(MAKE) -C $(M2DIR)/software/libbase
	$(MAKE) -C $(M2DIR)/software/libnet

flash: bios.bin
	m1nor bios.bin

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) bios.elf bios.bin bios-rescue.elf bios-rescue.bin .*~ *~

.PHONY: all main.o clean libs flash
