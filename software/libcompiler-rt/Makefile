MSCDIR=../..
include $(MSCDIR)/software/common.mak

CFLAGS+=-D_YUGA_LITTLE_ENDIAN=0 -D_YUGA_BIG_ENDIAN=1 -Wno-missing-prototypes

OBJECTS=divsi3.o modsi3.o comparedf2.o negsf2.o negdf2.o addsf3.o subsf3.o mulsf3.o divsf3.o lshrdi3.o muldi3.o divdi3.o ashldi3.o ashrdi3.o udivmoddi4.o \
  floatsisf.o floatunsisf.o fixsfsi.o fixunssfsi.o adddf3.o subdf3.o muldf3.o divdf3.o floatsidf.o floatunsidf.o floatdidf.o fixdfsi.o fixunsdfsi.o \
  clzsi2.o ctzsi2.o udivdi3.o umoddi3.o

all: libcompiler-rt.a

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libcompiler-rt.a: $(OBJECTS)
	$(AR) clr libcompiler-rt.a $(OBJECTS)
	$(RANLIB) libcompiler-rt.a

%.o: $(CRTDIR)/lib/builtins/%.c
	$(compile-dep)

.PHONY: clean

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.ts) $(OBJECTS:.o=.d) libcompiler-rt.a .*~ *~
