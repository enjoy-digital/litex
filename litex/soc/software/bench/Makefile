include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS = crt0.o main.o
CFLAGS += -O2
VPATH = $(BIOS_DIRECTORY):$(CPU_DIRECTORY)
LSCRIPT = $(SOC_DIRECTORY)/software/bios/linker.ld

all: bios.bin

bios.elf: $(OBJECTS) $(LSCRIPT)
	$(CC) $(LDFLAGS) -T $(LSCRIPT) -N -o $@ $(OBJECTS) \
		$(PACKAGES:%=-L../%) -Wl,--start-group $(LIBS:lib%=-l%) -Wl,--end-group \
		-Wl,--gc-sections -Wl,-Map,$@.map

bios.bin: bios.elf
	$(OBJCOPY) -O binary $< $@

%.o: %.c
	$(compile)

%.o: %.S
	$(assemble)

-include $(OBJECTS:.o=.d)
.PHONY: all
