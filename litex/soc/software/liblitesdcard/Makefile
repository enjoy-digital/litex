include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS=sdcard.o spisdcard.o

all: liblitesdcard.a

liblitesdcard.a: $(OBJECTS)
	$(AR) crs liblitesdcard.a $(OBJECTS)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: $(LIBLITESDCARD_DIRECTORY)/%.c
	$(compile)

%.o: %.S
	$(assemble)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS) liblitesdcard.a .*~ *~
