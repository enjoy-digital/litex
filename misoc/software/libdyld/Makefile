MSCDIR=../..
include $(MSCDIR)/software/common.mak

COMMONFLAGS += -I$(MSCDIR)/software/include/dyld

OBJECTS=dyld.o

all: libdyld.a

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libdyld.a: $(OBJECTS)
	$(AR) crs libdyld.a $(OBJECTS)

.PHONY: clean

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) libdyld.a .*~ *~
