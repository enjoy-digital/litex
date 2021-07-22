include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS = exception.o \
	crc16.o           \
	crc32.o           \
	console.o         \
	system.o          \
	id.o              \
	uart.o            \
	time.o            \
	spiflash.o        \
	i2c.o             \
	div64.o           \
	progress.o        \
	memtest.o         \
	sim_debug.o

all: crt0.o libbase.a libbase-nofloat.a

libbase.a: $(OBJECTS)
	$(AR) crs libbase.a $(OBJECTS)

libbase-nofloat.a: $(OBJECTS)
	$(AR) crs libbase-nofloat.a $(OBJECTS)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: $(LIBBASE_DIRECTORY)/%.c
	$(compile)

%.o: $(LIBBASE_DIRECTORY)/%.S
	$(assemble)

crt0.o: $(CPU_DIRECTORY)/crt0.S
	$(assemble)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS) crt0.o vsnprintf.o vsnprintf-nofloat.o
	$(RM) libbase.a libbase-nofloat.a .*~ *~
