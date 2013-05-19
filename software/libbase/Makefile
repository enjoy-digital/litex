M2DIR=../..
include $(M2DIR)/software/common.mak

OBJECTS=setjmp.o libc.o errno.o crc16.o crc32.o console.o system.o board.o uart.o qsort.o strtod.o

all: libbase.a libbase-nofloat.a

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libbase.a: $(OBJECTS) vsnprintf.o
	$(AR) clr libbase.a $(OBJECTS) vsnprintf.o
	$(RANLIB) libbase.a

libbase-nofloat.a: $(OBJECTS) vsnprintf-nofloat.o
	$(AR) clr libbase-nofloat.a $(OBJECTS) vsnprintf-nofloat.o
	$(RANLIB) libbase-nofloat.a

vsnprintf-nofloat.o: vsnprintf.c
	$(call compile-dep,-DNO_FLOAT)

%.o: %.c
	$(compile-dep)

%.o: %.S
	$(assemble)

.PHONY: clean

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) vsnprintf.o vsnprintf.d vsnprintf-nofloat.o vsnprintf-nofloat.d
	$(RM) libbase.a libbase-nofloat.a .*~ *~
