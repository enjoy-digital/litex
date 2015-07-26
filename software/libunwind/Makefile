MSCDIR=../..
include $(MSCDIR)/software/common.mak

COMMONFLAGS+=-integrated-as \
	-I. -I$(MSCDIR)/software/include/dyld/ -I$(MSCDIR)/software/unwinder/include/ \
	-D__ELF__ -D__linux__

OBJECTS=UnwindRegistersSave.o UnwindRegistersRestore.o UnwindLevel1.o libunwind.o

all: libunwind.a

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

libunwind.a: $(OBJECTS)
	$(AR) crs libunwind.a $(OBJECTS)

%.o: $(MSCDIR)/software/unwinder/src/%.cpp
	$(compilexx-dep)

%.o: $(MSCDIR)/software/unwinder/src/%.c
	$(compile-dep)

%.o: $(MSCDIR)/software/unwinder/src/%.S
	$(assemble)

.PHONY: clean

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.ts) $(OBJECTS:.o=.d) libuwind.a .*~ *~
