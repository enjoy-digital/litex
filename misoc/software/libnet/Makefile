include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

OBJECTS=microudp.o tftp.o

all: libnet.a

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libnet.a: $(OBJECTS)
	$(AR) crs libnet.a $(OBJECTS)

%.o: $(LIBNET_DIRECTORY)/%.c
	$(compile-dep)

%.o: %.S
	$(assemble)

.PHONY: clean

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.ts) $(OBJECTS:.o=.d) libnet.a .*~ *~
