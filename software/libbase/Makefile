MMDIR=../..
include $(MMDIR)/software/include.mak

OBJECTS=divsi3.o libc.o console.o system.o board.o uart.o softfloat.o softfloat-glue.o vsnprintf.o atof.o

all: libbase.a

libbase.a: $(OBJECTS)
	$(AR) clr libbase.a $(OBJECTS)
	$(RANLIB) libbase.a

.PHONY: clean

clean:
	rm -f *.o libbase.a .*~ *~ Makefile.bak
