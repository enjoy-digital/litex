TARGET_PREFIX=lm32-elf-

CC_normal := $(TARGET_PREFIX)gcc
CX_normal := $(TARGET_PREFIX)g++
AS_normal := $(TARGET_PREFIX)as
AR_normal := $(TARGET_PREFIX)ar
LD_normal := $(TARGET_PREFIX)ld
OBJCOPY_normal := $(TARGET_PREFIX)objcopy
RANLIB_normal := $(TARGET_PREFIX)ranlib

CC_quiet = @echo " CC " $@ && $(TARGET_PREFIX)gcc
CX_quiet = @echo " CX " $@ && $(TARGET_PREFIX)g++
AS_quiet = @echo " AS " $@ && $(TARGET_PREFIX)as
AR_quiet = @echo " AR " $@ && $(TARGET_PREFIX)ar
LD_quiet = @echo " LD " $@ && $(TARGET_PREFIX)ld
OBJCOPY_quiet = @echo " OBJCOPY " $@ && $(TARGET_PREFIX)objcopy
RANLIB_quiet = @echo " RANLIB  " $@ && $(TARGET_PREFIX)ranlib

ifeq ($(V),1)
	CC = $(CC_normal)
	CX = $(CX_normal)
	AS = $(AS_normal)
	AR = $(AR_normal)
	LD = $(LD_normal)
	OBJCOPY = $(OBJCOPY_normal)
	RANLIB = $(RANLIB_normal)
else
	CC = $(CC_quiet)
	CX = $(CX_quiet)
	AS = $(AS_quiet)
	AR = $(AR_quiet)
	LD = $(LD_quiet)
	OBJCOPY = $(OBJCOPY_quiet)
	RANLIB = $(RANLIB_quiet)
endif

# Toolchain options
#
INCLUDES = -I$(M2DIR)/software/include/base -I$(M2DIR)/software/include -I$(M2DIR)/common
COMMONFLAGS = -O3 -mbarrel-shift-enabled -mmultiply-enabled -mdivide-enabled -msign-extend-enabled \
	-Wall -fno-builtin -nostdinc $(INCLUDES)
CFLAGS = $(COMMONFLAGS) -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes
CXXFLAGS = $(COMMONFLAGS) -fno-exceptions -ffreestanding
LDFLAGS = -nostdlib -nodefaultlibs

# compile and generate dependencies, based on
# http://scottmcpeak.com/autodepend/autodepend.html

define compilexx-dep
$(CX) -c $(CXXFLAGS) $< -o $*.o
@$(CX_normal) -MM $(CXXFLAGS) $< > $*.d
@mv -f $*.d $*.d.tmp
@sed -e 's|.*:|$*.o:|' < $*.d.tmp > $*.d
@sed -e 's/.*://' -e 's/\\$$//' < $*.d.tmp | fmt -1 | \
	sed -e 's/^ *//' -e 's/$$/:/' >> $*.d
@rm -f $*.d.tmp
endef

define compile-dep
$(CC) -c $(CFLAGS) $< -o $*.o
@$(CC_normal) -MM $(CFLAGS) $< > $*.d
@mv -f $*.d $*.d.tmp
@sed -e 's|.*:|$*.o:|' < $*.d.tmp > $*.d
@sed -e 's/.*://' -e 's/\\$$//' < $*.d.tmp | fmt -1 | \
	sed -e 's/^ *//' -e 's/$$/:/' >> $*.d
@rm -f $*.d.tmp
endef

define assemble
$(AS) -o $*.o $<
endef
