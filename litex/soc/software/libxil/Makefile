include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

all: libxil.a

CFLAGS += -nostartfiles

OBJECTS = xil_cache.o \
	xil_exception.o \
	asm_vectors.o \
	boot.o \
	translation_table.o \
	xil-crt0.o \
	vectors.o \
	xtime_l.o

%.o: embeddedsw/lib/bsp/standalone/src/arm/common/%.c
	$(compile)

ifeq ($(CPU), zynqmp)
%.o: embeddedsw/lib/bsp/standalone/src/arm/ARMv8/64bit/%.c
	$(compile)
%.o: embeddedsw/lib/bsp/standalone/src/arm/ARMv8/64bit/gcc/%.S
	$(assemble)
%.o: embeddedsw/lib/bsp/standalone/src/arm/ARMv8/64bit/platform/ZynqMP/gcc/%.S
	$(assemble)

else ifeq ($(CPU), zynq7000)

OBJECTS += cpu_init.o

%.o: embeddedsw/lib/bsp/standalone/src/arm/cortexa9/%.c
	$(compile)
%.o: embeddedsw/lib/bsp/standalone/src/arm/cortexa9/gcc/%.S
	$(assemble)

endif

libxil.a: $(OBJECTS)
	$(AR) crs $@ $^

clean:
	$(RM) $(OBJECTS) libxil.a
