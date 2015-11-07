include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS=microudp.o tftp.o

all: libnet.a

libnet.a: $(OBJECTS)
	$(AR) crs libnet.a $(OBJECTS)

%.o: $(LIBNET_DIRECTORY)/%.c
	$(compile)

%.o: %.S
	$(assemble)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS) libnet.a .*~ *~
