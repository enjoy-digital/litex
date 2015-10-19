include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

# lm32 is not supported
ifeq ($(CPU),lm32)
	ALL_TARGET=
else
	ALL_TARGET=libdyld.a
endif

COMMONFLAGS += -I$(MISOC_DIRECTORY)/software/include/dyld

OBJECTS=dyld.o

all: $(ALL_TARGET)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libdyld.a: $(OBJECTS)
	$(AR) crs libdyld.a $(OBJECTS)

%.o: $(LIBDYLD_DIRECTORY)/%.c
	$(compile-dep)

.PHONY: clean

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) libdyld.a .*~ *~
