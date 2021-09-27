include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS =  \
	crc16.o    \
	crc32.o    \
	system.o   \
	progress.o \
	memtest.o

all: libutils.a

libutils.a: $(OBJECTS)
	$(AR) crs libutils.a $(OBJECTS)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: $(LIBUTILS_DIRECTORY)/%.c
	$(compile)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS)
	$(RM) libutils.a .*~ *~
