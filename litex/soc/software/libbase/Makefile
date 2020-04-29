include $(SDK_DIRECTORY)/include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS=exception.o libc.o errno.o crc16.o crc32.o console.o \
	system.o id.o uart.o time.o qsort.o strtod.o spiflash.o spisdcard.o strcasecmp.o mdio.o

PRODUCTS=crt0-$(CPU)-ctr.o crt0-$(CPU)-xip.o libbase.a libbase-nofloat.a

all: $(PRODUCTS)

install: all
	cp $(PRODUCTS) $(SDK_DIRECTORY)/lib

libbase.a: $(OBJECTS) vsnprintf.o
	$(AR) crs libbase.a $(OBJECTS) vsnprintf.o

libbase-nofloat.a: $(OBJECTS) vsnprintf-nofloat.o
	$(AR) crs libbase-nofloat.a $(OBJECTS) vsnprintf-nofloat.o

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

vsnprintf-nofloat.o: $(LIBBASE_DIRECTORY)/vsnprintf.c
	$(call compile,-DNO_FLOAT)

%.o: $(LIBBASE_DIRECTORY)/%.c
	$(compile)

%.o: $(LIBBASE_DIRECTORY)/%.S
	$(assemble)

crt0-$(CPU)-ctr.o: $(LIBBASE_DIRECTORY)/crt0-$(CPU).S
	$(assemble)

crt0-$(CPU)-xip.o: $(LIBBASE_DIRECTORY)/crt0-$(CPU).S
	$(CC) -c -DEXECUTE_IN_PLACE $(CFLAGS) -o $@ $<

.PHONY: all clean

clean:
	$(RM) $(OBJECTS) crt0-$(CPU).o crt0-$(CPU)-flash.o vsnprintf.o vsnprintf-nofloat.o
	$(RM) libbase.a libbase-nofloat.a .*~ *~
