include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

all: libxil.a

CFLAGS += -nostartfiles

OBJECTS = xil_cache.o \
	xil_exception.o \
	asm_vectors.o \
	boot.o \
	cpu_init.o \
	translation_table.o \
	xil-crt0.o \
	vectors.o \
	xtime_l.o

libxil.a: $(OBJECTS)
	$(AR) crs $@ $^

%.o: embeddedsw/lib/bsp/standalone/src/arm/cortexa9/%.c
	$(compile)

%.o: embeddedsw/lib/bsp/standalone/src/arm/common/%.c
	$(compile)

%.o: embeddedsw/lib/bsp/standalone/src/arm/cortexa9/gcc/%.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) libxil.a
