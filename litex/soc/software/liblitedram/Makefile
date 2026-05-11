include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS = sdram.o sdram1.o sdram2.o sdram3.o sdram_multichannel.o bist.o sdram_dbg.o sdram_spd.o utils.o accessors.o accessors1.o accessors2.o accessors3.o

all: liblitedram.a

liblitedram.a: $(OBJECTS)
	$(AR) crs liblitedram.a $(OBJECTS)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: $(LIBLITEDRAM_DIRECTORY)/%.c
	$(compile)

%.o: %.S
	$(assemble)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS) liblitedram.a .*~ *~
