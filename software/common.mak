include $(MSCDIR)/software/include/generated/cpu.mak
TRIPLE=$(CPU)-elf
TARGET_PREFIX=$(TRIPLE)-

RM ?= rm -f

CC_normal      := clang -target $(TRIPLE)
CX_normal      := clang++ -target $(TRIPLE)
AR_normal      := $(TARGET_PREFIX)ar
LD_normal      := $(TARGET_PREFIX)ld
OBJCOPY_normal := $(TARGET_PREFIX)objcopy

CC_quiet      = @echo " CC      " $@ && $(CC_normal)
CX_quiet      = @echo " CX      " $@ && $(CX_normal)
AR_quiet      = @echo " AR      " $@ && $(AR_normal)
LD_quiet      = @echo " LD      " $@ && $(LD_normal)
OBJCOPY_quiet = @echo " OBJCOPY " $@ && $(OBJCOPY_normal)

MSC_GIT_ID := $(shell cd $(MSCDIR) && python3 -c "from misoclib.cpu.identifier import get_id; print(hex(get_id()), end='')")

ifeq ($(V),1)
	CC = $(CC_normal)
	CX = $(CX_normal)
	AR = $(AR_normal)
	LD = $(LD_normal)
	OBJCOPY = $(OBJCOPY_normal)
else
	CC = $(CC_quiet)
	CX = $(CX_quiet)
	AR = $(AR_quiet)
	LD = $(LD_quiet)
	OBJCOPY = $(OBJCOPY_quiet)
endif

# Toolchain options
#
INCLUDES = -I$(MSCDIR)/software/include/base -I$(MSCDIR)/software/include -I$(MSCDIR)/common
COMMONFLAGS = -Os $(CPUFLAGS) -Wall -fno-builtin -nostdinc -DMSC_GIT_ID=$(MSC_GIT_ID) $(INCLUDES)
CFLAGS = $(COMMONFLAGS) -fexceptions -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes
CXXFLAGS = $(COMMONFLAGS) -fexceptions -fno-rtti -ffreestanding
LDFLAGS = -nostdlib -nodefaultlibs -L$(MSCDIR)/software/include

# compile and generate dependencies, based on
# http://scottmcpeak.com/autodepend/autodepend.html

define compilexx-dep
$(CX) -c $(CXXFLAGS) $(1) $< -o $*.o
@$(CX_normal) -MM $(CXXFLAGS) $(1) $< > $*.d
@mv -f $*.d $*.d.tmp
@sed -e 's|.*:|$*.o:|' < $*.d.tmp > $*.d
@sed -e 's/.*://' -e 's/\\$$//' < $*.d.tmp | fmt -1 | \
	sed -e 's/^ *//' -e 's/$$/:/' >> $*.d
@rm -f $*.d.tmp
endef

define compile-dep
$(CC) -c $(CFLAGS) $(1) $< -o $*.o
@$(CC_normal) -MM $(CFLAGS) $(1) $< > $*.d
@mv -f $*.d $*.d.tmp
@sed -e 's|.*:|$*.o:|' < $*.d.tmp > $*.d
@sed -e 's/.*://' -e 's/\\$$//' < $*.d.tmp | fmt -1 | \
	sed -e 's/^ *//' -e 's/$$/:/' >> $*.d
@rm -f $*.d.tmp
endef

define assemble
$(CC) -c $(CFLAGS) -o $*.o $<
endef
