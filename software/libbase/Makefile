M2DIR=../..
include $(M2DIR)/software/include.mak

OBJECTS=divsi3.o libc.o console.o system.o board.o uart.o softfloat.o softfloat-glue.o vsnprintf.o atof.o

all: libbase.a

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libbase.a: $(OBJECTS)
	$(AR) clr libbase.a $(OBJECTS)
	$(RANLIB) libbase.a

.PHONY: clean

clean:
	rm -f $(OBJECTS) $(OBJECTS:.o=.d) libbase.a .*~ *~
