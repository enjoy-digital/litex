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
	  sdcard.o			\
	  main.o			\
	  boot-helper.o		\
	  boot.o			\
	  helpers.o			\
	  cmd_bios.o		\
	  cmd_boot.o		\
	  cmd_litedram.o	\
	  cmd_liteeth.o		\
	  cmd_mem.o	        \
	  cmd_litesdcard.o	\
	  cmd_spiflash.o	\

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


%.elf: ../libbase/crt0-ctr.o \
	../libcompiler_rt/libcompiler_rt.a \
	../libbase/libbase-nofloat.a \
	../liblitedram/liblitedram.a \
	../libliteeth/libliteeth.a
	$(LD) $(LDFLAGS) -T $(BIOS_DIRECTORY)/linker.ld -N -o $@ \
		../libbase/crt0-ctr.o \
		$(OBJECTS) \
		-L../libcompiler_rt \
		-L../libbase \
		-L../liblitedram \
		-L../libliteeth \
		$(BP_LIBS) \
		-lcompiler_rt -lbase-nofloat -llitedram -lliteeth \
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
