include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

# lm32 is not supported
ifeq ($(CPU),lm32)
	ALL_TARGET=
else
	ALL_TARGET=libunwind.a
endif

COMMONFLAGS+=-integrated-as \
	-I. -I$(MISOC_DIRECTORY)/software/include/dyld/ -I$(MISOC_DIRECTORY)/software/unwinder/include/ \
	-I$(LIBUNWIND_DIRECTORY) \
	-D__ELF__ -D__linux__ -D_LIBUNWIND_NO_HEAP -DNDEBUG

OBJECTS=UnwindRegistersSave.o UnwindRegistersRestore.o UnwindLevel1.o libunwind.o

all: $(ALL_TARGET)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libunwind.a: $(OBJECTS)
	$(AR) crs libunwind.a $(OBJECTS)

%.o: $(MISOC_DIRECTORY)/software/unwinder/src/%.cpp
	$(compilexx-dep)

%.o: $(MISOC_DIRECTORY)/software/unwinder/src/%.c
	$(compile-dep)

%.o: $(MISOC_DIRECTORY)/software/unwinder/src/%.S
	$(assemble)

.PHONY: clean

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.ts) $(OBJECTS:.o=.d) libunwind.a .*~ *~
