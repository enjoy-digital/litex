M2DIR=../..
include $(M2DIR)/software/common.mak

OBJECTS=crt0.o isr.o main.o

all: videomixer.bin

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	chmod -x $@

videomixer.elf: linker.ld $(OBJECTS) libs

%.elf:
	$(LD) $(LDFLAGS) -T $< -N -o $@ $(OBJECTS) \
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
	make -C $(M2DIR)/software/libcompiler-rt
	make -C $(M2DIR)/software/libbase

load: videomixer.bin
	make -C $(M2DIR)/tools
	$(M2DIR)/tools/flterm --port /dev/ttyUSB0 --kernel videomixer.bin

clean:
	rm -f $(OBJECTS) $(OBJECTS:.o=.d) videomixer.elf videomixer.bin .*~ *~

.PHONY: main.o clean libs load
