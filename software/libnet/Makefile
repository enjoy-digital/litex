M2DIR=../..
include $(M2DIR)/software/common.mak

OBJECTS=microudp.o tftp.o

all: libnet.a

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libnet.a: $(OBJECTS)
	$(AR) clr libnet.a $(OBJECTS)
	$(RANLIB) libnet.a

%.o: %.c
	$(compile-dep)

%.o: %.S
	$(assemble)

.PHONY: clean

clean:
	rm -f $(OBJECTS) $(OBJECTS:.o=.ts) $(OBJECTS:.o=.d) libnet.a .*~ *~
