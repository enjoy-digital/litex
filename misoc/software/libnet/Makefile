MSCDIR=../..
include $(MSCDIR)/software/common.mak

OBJECTS=microudp.o tftp.o

all: libnet.a

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libnet.a: $(OBJECTS)
	$(AR) crs libnet.a $(OBJECTS)

%.o: %.c
	$(compile-dep)

%.o: %.S
	$(assemble)

.PHONY: clean

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.ts) $(OBJECTS:.o=.d) libnet.a .*~ *~
