M2DIR=../..
include $(M2DIR)/software/common.mak

OBJECTS=isr.o main.o

all: memtest.bin

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	chmod -x $@

memtest.elf: $(OBJECTS) libs

%.elf:
	$(LD) $(LDFLAGS) \
		-T $(M2DIR)/software/libbase/linker-sdram.ld \
		-N -o $@ \
		$(M2DIR)/software/libbase/crt0.o \
		$(OBJECTS) \
		-L$(M2DIR)/software/libbase \
		-L$(M2DIR)/software/libcompiler-rt \
		-lbase -lcompiler-rt
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

load: memtest.bin
	$(MAKE) -C $(M2DIR)/tools
	$(M2DIR)/tools/flterm --port /dev/ttyUSB0 --kernel memtest.bin


clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) memtest.elf memtest.bin
	$(RM) .*~ *~

.PHONY: all main.o clean libs load
