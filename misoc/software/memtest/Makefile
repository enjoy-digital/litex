MSCDIR=../..
include $(MSCDIR)/software/common.mak

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
		-T $(MSCDIR)/software/libbase/linker-sdram.ld \
		-N -o $@ \
		$(MSCDIR)/software/libbase/crt0-$(CPU).o \
		$(OBJECTS) \
		-L$(MSCDIR)/software/libbase \
		-L$(MSCDIR)/software/libcompiler-rt \
		-lbase -lcompiler-rt
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

load: memtest.bin
	$(MAKE) -C $(MSCDIR)/tools
	$(MSCDIR)/tools/flterm --port /dev/ttyUSB0 --kernel memtest.bin


clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) memtest.elf memtest.bin
	$(RM) .*~ *~

.PHONY: all main.o clean libs load
