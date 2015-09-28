include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

COMMONFLAGS+=-integrated-as \
	-I. -I$(MISOC_DIRECTORY)/software/include/dyld/ -I$(MISOC_DIRECTORY)/software/unwinder/include/ \
	-I$(LIBUNWIND_DIRECTORY) \
	-D__ELF__ -D__linux__ -D_LIBUNWIND_NO_HEAP -DNDEBUG

OBJECTS=UnwindRegistersSave.o UnwindRegistersRestore.o UnwindLevel1.o libunwind.o

all: libunwind.a

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
