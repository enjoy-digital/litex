MSCDIR=../..
include $(MSCDIR)/software/common.mak

OBJECTS=exception.o libc.o errno.o crc16.o crc32.o console.o system.o id.o uart.o time.o qsort.o strtod.o spiflash.o

all: crt0-$(CPU).o libbase.a libbase-nofloat.a

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libbase.a: $(OBJECTS) vsnprintf.o
	$(AR) crs libbase.a $(OBJECTS) vsnprintf.o

libbase-nofloat.a: $(OBJECTS) vsnprintf-nofloat.o
	$(AR) crs libbase-nofloat.a $(OBJECTS) vsnprintf-nofloat.o

vsnprintf-nofloat.o: vsnprintf.c
	$(call compile-dep,-DNO_FLOAT)

%.o: %.c
	$(compile-dep)

%.o: %.S
	$(assemble)

.PHONY: clean

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) crt0-$(CPU).o vsnprintf.o vsnprintf.d vsnprintf-nofloat.o vsnprintf-nofloat.d
	$(RM) libbase.a libbase-nofloat.a .*~ *~
