include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS = \
	uart.o     \
	spiflash.o \
	i2c.o      \

all: libcomm.a

libcomm.a: $(OBJECTS)
	$(AR) crs libcomm.a $(OBJECTS)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: $(LIBCOMM_DIRECTORY)/%.c
	$(compile)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS)
	$(RM) libcomm.a .*~ *~
