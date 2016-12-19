include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS=microudp.o tftp.o

all: libnet.a

libnet.a: $(OBJECTS)
	$(AR) crs libnet.a $(OBJECTS)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: $(LIBNET_DIRECTORY)/%.c
	$(compile)

%.o: %.S
	$(assemble)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS) libnet.a .*~ *~
