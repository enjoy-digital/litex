M2DIR=../..
include $(M2DIR)/software/common.mak

OBJECTS=crt0.o isr.o dvisampler0.o dvisampler1.o main.o

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

define gen0
@echo " GEN " $@
@sed -e "s/dvisamplerX/dvisampler0/g;s/DVISAMPLERX/DVISAMPLER0/g;s/fb_dmaX/fb_dma0/g" $< > $@
endef

define gen1
@echo " GEN " $@
@sed -e "s/dvisamplerX/dvisampler1/g;s/DVISAMPLERX/DVISAMPLER1/g;s/fb_dmaX/fb_dma1/g" $< > $@
endef

dvisampler0.c: dvisamplerX.c
	$(gen0)
dvisampler0.h: dvisamplerX.h
	$(gen0)
dvisampler1.c: dvisamplerX.c
	$(gen1)
dvisampler1.h: dvisamplerX.h
	$(gen1)

isr.o: dvisampler0.h dvisampler1.h
main.o: dvisampler0.h dvisampler1.h
dvisampler0.o: dvisampler0.h
dvisampler1.o: dvisampler1.h

libs:
	$(MAKE) -C $(M2DIR)/software/libcompiler-rt
	$(MAKE) -C $(M2DIR)/software/libbase

load: videomixer.bin
	$(MAKE) -C $(M2DIR)/tools
	$(M2DIR)/tools/flterm --port /dev/ttyUSB0 --kernel videomixer.bin

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) videomixer.elf videomixer.bin .*~ *~
	$(RM) dvisampler0.h dvisampler0.c dvisampler1.h dvisampler1.c

.PHONY: all main.o clean libs load
