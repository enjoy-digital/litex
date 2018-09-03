include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

ifeq ($(CPUENDIANNESS),big)
CFLAGS+=-D_YUGA_LITTLE_ENDIAN=0 -D_YUGA_BIG_ENDIAN=1 -Wno-missing-prototypes
else
CFLAGS+=-D_YUGA_LITTLE_ENDIAN=1 -D_YUGA_BIG_ENDIAN=0 -Wno-missing-prototypes
endif

OBJECTS=umodsi3.o udivsi3.o divsi3.o modsi3.o comparesf2.o comparedf2.o negsf2.o negdf2.o addsf3.o subsf3.o mulsf3.o divsf3.o lshrdi3.o muldi3.o divdi3.o ashldi3.o ashrdi3.o udivmoddi4.o \
  floatsisf.o floatunsisf.o fixsfsi.o fixdfdi.o fixunssfsi.o fixunsdfdi.o adddf3.o subdf3.o muldf3.o divdf3.o floatsidf.o floatunsidf.o floatdidf.o fixdfsi.o fixunsdfsi.o \
  clzsi2.o ctzsi2.o udivdi3.o umoddi3.o moddi3.o ucmpdi2.o

all: libcompiler_rt.a

libcompiler_rt.a: $(OBJECTS)
	$(CC) -c $(CFLAGS) $(1) $(SOC_DIRECTORY)/software/libcompiler_rt/mulsi3.c -o mulsi3.o
	$(AR) crs libcompiler_rt.a $(OBJECTS) mulsi3.o

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

mulsi3.o: $(SOC_DIRECTORY)/software/libcompiler_rt/mulsi3.c
	$(compile)

%.o: $(SOC_DIRECTORY)/software/compiler_rt/lib/builtins/%.c
	$(compile)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.ts) $(OBJECTS:.o=.d) libcompiler_rt.a .*~ *~
