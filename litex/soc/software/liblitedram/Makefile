include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

DEFAULT_OBJECTS = sdram.o sdram_multichannel.o bist.o sdram_dbg.o sdram_spd.o utils.o accessors.o
OBJECTS = $(if $(LIBLITEDRAM_OBJECTS),$(LIBLITEDRAM_OBJECTS),$(DEFAULT_OBJECTS))

all: liblitedram.a

liblitedram.a: $(OBJECTS)
	$(AR) crs liblitedram.a $(OBJECTS)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: %.c
	$(compile)

%.o: $(LIBLITEDRAM_DIRECTORY)/%.c
	$(compile)

%.o: %.S
	$(assemble)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS) liblitedram.a .*~ *~
