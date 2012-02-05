M2DIR=../..
include $(M2DIR)/software/include.mak

OBJECTS=crt0.o isr.o main.o

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
	$(LD) $(LDFLAGS) -T $< -N -o $@ $(OBJECTS) -L$(M2DIR)/software/libbase -lbase
	chmod -x $@

libs:
	make -C $(M2DIR)/software/libbase

.PHONY: clean libs

clean:
	rm -f $(OBJECTS) $(OBJECTS:.o=.d) bios.elf bios.bin bios-rescue.elf bios-rescue.bin .*~ *~
