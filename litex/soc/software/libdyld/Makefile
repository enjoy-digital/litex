include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

# lm32 is not supported
ifeq ($(CPU),lm32)
	ALL_TARGET=
else
	ALL_TARGET=libdyld.a
endif

COMMONFLAGS += -I$(SOC_DIRECTORY)/software/include/dyld

OBJECTS=dyld.o

all: $(ALL_TARGET)

libdyld.a: $(OBJECTS)
	$(AR) crs libdyld.a $(OBJECTS)

%.o: $(LIBDYLD_DIRECTORY)/%.c
	$(compile)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS) libdyld.a .*~ *~
