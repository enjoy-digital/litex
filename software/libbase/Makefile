MMDIR=../..
include $(MMDIR)/software/include.mak

OBJECTS=divsi3.o libc.o console.o system.o board.o uart.o softfloat.o softfloat-glue.o vsnprintf.o atof.o

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

all: libbase.a

libbase.a: $(OBJECTS)
	$(AR) clr libbase.a $(OBJECTS)
	$(RANLIB) libbase.a

.PHONY: clean

clean:
	rm -f $(OBJECTS) $(OBJECTS:.o=.d) libbase.a .*~ *~ Makefile.bak
