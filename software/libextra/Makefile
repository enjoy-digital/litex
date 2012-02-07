M2DIR=../..
include $(M2DIR)/software/include.mak

OBJECTS=crc16.o crc32.o

all: libextra.a

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libextra.a: $(OBJECTS)
	$(AR) clr libextra.a $(OBJECTS)
	$(RANLIB) libextra.a

.PHONY: clean

clean:
	rm -f $(OBJECTS) $(OBJECTS:.o=.d) libextra.a .*~ *~
