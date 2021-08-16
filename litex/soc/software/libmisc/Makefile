include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS = \
	exception.o \
	sim_debug.o

all: libmisc.a

libmisc.a: $(OBJECTS)
	$(AR) crs libmisc.a $(OBJECTS)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: $(LIBMISC_DIRECTORY)/%.c
	$(compile)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS)
	$(RM) libmisc.a .*~ *~
