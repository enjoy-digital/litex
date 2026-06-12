include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

# Permit TFTP_SERVER_PORT override from shell environment / command line
ifdef TFTP_SERVER_PORT
CFLAGS += -DTFTP_SERVER_PORT=$(TFTP_SERVER_PORT)
endif

OBJECTS = boot-helper.o	\
	  boot.o			\
	  helpers.o			\
	  cmd_bios.o		\
	  cmd_mem.o			\
	  cmd_boot.o		\
	  cmd_i2c.o			\
	  cmd_spiflash.o	\
	  cmd_litedram.o	\
	  cmd_liteeth.o		\
	  cmd_litesdcard.o  \
	  cmd_litesata.o    \
	  sim_debug.o		\
	  main.o            \
	  crt0.o

ifneq "$(or $(BIOS_CONSOLE_NO_AUTOCOMPLETE),$(BIOS_CONSOLE_LITE))" ""
CFLAGS += -DBIOS_CONSOLE_NO_AUTOCOMPLETE
else
OBJECTS += complete.o
endif

ifdef BIOS_CONSOLE_NO_HISTORY
CFLAGS += -DBIOS_CONSOLE_NO_HISTORY
endif

ifdef BIOS_CONSOLE_DISABLE
CFLAGS += -DBIOS_CONSOLE_DISABLE
endif

ifdef BIOS_CONSOLE_NO_ANSI
CFLAGS += -DBIOS_CONSOLE_NO_ANSI
endif

ifdef BIOS_CONSOLE_LITE
CFLAGS += -DBIOS_CONSOLE_LITE
OBJECTS += readline_simple.o
else
OBJECTS += readline.o
endif

ifeq ($(CPU), zynq7000)
LSCRIPT = linker-zynq.ld
else ifeq ($(CPU), zynqmp)
LSCRIPT = linker-zynqmp.ld
else
LSCRIPT = linker.ld
endif

COMMA = ,
REGULAR_LIBS = $(filter-out $(ALWAYS_LINK_LIBS),$(LIBS))
ALWAYS_LINK_LIBFLAGS = $(if $(ALWAYS_LINK_LIBS),-Wl$(COMMA)--whole-archive $(ALWAYS_LINK_LIBS:lib%=-l%) -Wl$(COMMA)--no-whole-archive)

ifneq ($(BIOS_STACK_MARGIN),)
MEMUSAGE_ARGS += --fail-stack-margin $(BIOS_STACK_MARGIN)
endif

all: bios.bin
	$(PYTHON) -m litex.soc.software.memusage $(MEMUSAGE_ARGS) bios.elf $(CURDIR)/../include/generated/regions.ld $(TRIPLE)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
ifneq ($(OS),Windows_NT)
	chmod -x $@
endif
ifeq ($(CPUENDIANNESS),little)
	$(PYTHON) -m litex.soc.software.crcfbigen $@ --little
else
	$(PYTHON) -m litex.soc.software.crcfbigen $@
endif

bios.elf: $(BIOS_DIRECTORY)/$(LSCRIPT) $(OBJECTS)

vpath %.a $(PACKAGES:%=../%)

%.elf: crt0.o $(LIBS:%=%.a)
	$(CC) $(LDFLAGS) -T $(BIOS_DIRECTORY)/$(LSCRIPT) -N -o $@ \
		$(OBJECTS) \
		$(PACKAGES:%=-L../%) \
		-Wl,--start-group \
		$(REGULAR_LIBS:lib%=-l%) \
		$(ALWAYS_LINK_LIBFLAGS) \
		-Wl,--end-group \
		-Wl,--gc-sections \
		-Wl,-Map,$@.map

ifneq ($(OS),Windows_NT)
	chmod -x $@
endif

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

VPATH = $(BIOS_DIRECTORY):$(BIOS_DIRECTORY)/cmds:$(CPU_DIRECTORY)

%.o: %.c
	$(compile)

%.o: %.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) bios.elf bios.bin .*~ *~

.PHONY: all clean
