include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS=ffunicode.o ff.o sata.o

all: liblitesata.a

liblitesata.a: $(OBJECTS)
	$(AR) crs liblitesata.a $(OBJECTS)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: $(LIBLITESATA_DIRECTORY)/%.c
	$(compile)

%.o: $(LIBLITESATA_DIRECTORY)/fat/%.c
	$(compile)

%.o: %.S
	$(assemble)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS) liblitesata.a .*~ *~
