M2DIR=../..
include $(M2DIR)/software/common.mak

OBJECTS=setjmp.o libc.o errno.o crc16.o crc32.o console.o timer.o system.o board.o uart.o vsnprintf.o strtod.o qsort.o

all: libbase.a

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libbase.a: $(OBJECTS)
	$(AR) clr libbase.a $(OBJECTS)
	$(RANLIB) libbase.a

%.o: %.c
	$(compile-dep)

%.o: %.S
	$(assemble)

.PHONY: clean

clean:
	rm -f $(OBJECTS) $(OBJECTS:.o=.ts) $(OBJECTS:.o=.d) libbase.a .*~ *~
