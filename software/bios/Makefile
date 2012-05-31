M2DIR=../..
include $(M2DIR)/software/common.mak

OBJECTS=crt0.o isr.o ddrinit.o main.o microudp.o tftp.o boot-helper.o boot.o

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
		-L$(M2DIR)/software/libbase \
		-L$(CRTDIR) \
		-lbase -lcompiler_rt
	chmod -x $@

%.o: %.c
	$(compile-dep)

libs:
	make -C $(M2DIR)/software/libbase

flash: bios.bin
	m1nor bios.bin

clean:
	rm -f $(OBJECTS) $(OBJECTS:.o=.d) bios.elf bios.bin bios-rescue.elf bios-rescue.bin .*~ *~

.PHONY: clean libs flash
