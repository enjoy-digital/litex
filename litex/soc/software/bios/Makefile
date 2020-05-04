include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

ifeq ($(CPU),blackparrot)
BP_LIBS =  -L$(BP_LITEX_SOFTWARE)
BP_FLAGS = -lgcc
endif
# Permit TFTP_SERVER_PORT override from shell environment / command line
ifdef TFTP_SERVER_PORT
CFLAGS += -DTFTP_SERVER_PORT=$(TFTP_SERVER_PORT)
endif

OBJECTS = isr.o			\
	  sdram.o		\
	  sdcard.o		\
	  main.o		\
	  boot-helper.o		\
	  boot.o		\
	  helpers.o		\
	  cmd_bios.o		\
	  cmd_boot.o		\
	  cmd_dram.o		\
	  cmd_mdio.o		\
	  cmd_mem_access.o	\
	  cmd_sdcard.o		\
	  cmd_spi_flash.o	\
	  cmd_usddrphy.o

ifneq "$(or $(TERM_NO_COMPLETE),$(TERM_MINI))" ""
CFLAGS += -DTERM_NO_COMPLETE
else
OBJECTS += complete.o
endif

ifdef TERM_NO_HIST
CFLAGS += -DTERM_NO_HIST
endif

ifdef TERM_MINI
CFLAGS += -DTERM_MINI
OBJECTS += readline_simple.o
else
OBJECTS += readline.o
endif

all: bios.bin
	$(PYTHON) -m litex.soc.software.memusage bios.elf $(CURDIR)/../include/generated/regions.ld $(TRIPLE)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
ifneq ($(OS),Windows_NT)
	chmod -x $@
endif
ifeq ($(CPUENDIANNESS),little)
	$(PYTHON) -m litex.soc.software.mkmscimg $@ --little
else
	$(PYTHON) -m litex.soc.software.mkmscimg $@
endif

bios.elf: $(BIOS_DIRECTORY)/linker.ld $(OBJECTS)


%.elf: ../libbase/crt0-ctr.o ../libnet/libnet.a ../libbase/libbase-nofloat.a ../libcompiler_rt/libcompiler_rt.a
	$(LD) $(LDFLAGS) -T $(BIOS_DIRECTORY)/linker.ld -N -o $@ \
		../libbase/crt0-ctr.o \
		$(OBJECTS) \
		-L../libnet \
		-L../libbase \
		-L../libcompiler_rt \
		$(BP_LIBS) \
		-lnet -lbase-nofloat -lcompiler_rt \
		$(BP_FLAGS)
	
ifneq ($(OS),Windows_NT)
	chmod -x $@
endif

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: $(BIOS_DIRECTORY)/%.c
	$(compile)

%.o: $(BIOS_DIRECTORY)/commands/%.c
	$(compile)

%.o: $(BIOS_DIRECTORY)/%.S
	$(assemble)

boot-helper.o: $(CPU_DIRECTORY)/boot-helper.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) bios.elf bios.bin .*~ *~

.PHONY: all clean
