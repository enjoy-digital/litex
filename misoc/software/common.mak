TARGET_PREFIX=$(TRIPLE)-

RM ?= rm -f
PYTHON ?= python3

ifeq ($(CLANG),1)
CC_normal      := clang -target $(TRIPLE) -integrated-as
CX_normal      := clang++ -target $(TRIPLE) -integrated-as
else
CC_normal      := $(TARGET_PREFIX)gcc
CX_normal      := $(TARGET_PREFIX)g++
endif
AR_normal      := $(TARGET_PREFIX)ar
LD_normal      := $(TARGET_PREFIX)ld
OBJCOPY_normal := $(TARGET_PREFIX)objcopy

CC_quiet      = @echo " CC      " $@ && $(CC_normal)
CX_quiet      = @echo " CX      " $@ && $(CX_normal)
AR_quiet      = @echo " AR      " $@ && $(AR_normal)
LD_quiet      = @echo " LD      " $@ && $(LD_normal)
OBJCOPY_quiet = @echo " OBJCOPY " $@ && $(OBJCOPY_normal)

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
INCLUDES = -I$(MISOC_DIRECTORY)/software/include/base -I$(MISOC_DIRECTORY)/software/include -I$(MISOC_DIRECTORY)/common -I$(BUILDINC_DIRECTORY)
COMMONFLAGS = -Os $(CPUFLAGS) -fomit-frame-pointer -Wall -fno-builtin -nostdinc $(INCLUDES)
CFLAGS = $(COMMONFLAGS) -fexceptions -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes
CXXFLAGS = $(COMMONFLAGS) -std=c++11 -I$(MISOC_DIRECTORY)/software/include/basec++ -fexceptions -fno-rtti -ffreestanding
LDFLAGS = -nostdlib -nodefaultlibs -L$(BUILDINC_DIRECTORY)

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
