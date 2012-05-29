# Mico32 toolchain
#
CROSS_COMPILER=lm32-elf-
# TODO: mico32 should be renamed lm32 in LLVM
CLANG=clang -ccc-host-triple mico32-elf

CC_normal := $(CLANG)
AR_normal := $(CROSS_COMPILER)ar
LD_normal := $(CROSS_COMPILER)ld
OBJCOPY_normal := $(CROSS_COMPILER)objcopy
RANLIB_normal := $(CROSS_COMPILER)ranlib

CC_quiet = @echo " CC " $@ && $(CLANG)
AR_quiet = @echo " AR " $@ && $(CROSS_COMPILER)ar
LD_quiet = @echo " LD " $@ && $(CROSS_COMPILER)ld
OBJCOPY_quiet = @echo " OBJCOPY " $@ && $(CROSS_COMPILER)objcopy
RANLIB_quiet = @echo " RANLIB  " $@ && $(CROSS_COMPILER)ranlib

ifeq ($(V),1)
    CC = $(CC_normal)
    AR = $(AR_normal)
    LD = $(LD_normal)
    OBJCOPY = $(OBJCOPY_normal)
    RANLIB = $(RANLIB_normal)
else
    CC = $(CC_quiet)
    AR = $(AR_quiet)
    LD = $(LD_quiet)
    OBJCOPY = $(OBJCOPY_quiet)
    RANLIB = $(RANLIB_quiet)
endif

# Toolchain options
#
INCLUDES = -I$(M2DIR)/software/include/base -I$(M2DIR)/software/include -I$(M2DIR)/common
CFLAGS = -O9 -Wall -Wstrict-prototypes -Wold-style-definition -Wshadow \
	 -Wmissing-prototypes -fsigned-char -nostdinc $(INCLUDES)
LDFLAGS = -nostdlib -nodefaultlibs

# compile and generate dependencies, based on
# http://scottmcpeak.com/autodepend/autodepend.html

%.o: $(SRCDIR)%.c
	$(CC) -c $(CFLAGS) $(SRCDIR)$*.c -o $*.o
	@$(CC_normal) -MM $(CFLAGS) $(SRCDIR)$*.c > $*.d
	@mv -f $*.d $*.d.tmp
	@sed -e 's|.*:|$*.o:|' < $*.d.tmp > $*.d
	@sed -e 's/.*://' -e 's/\\$$//' < $*.d.tmp | fmt -1 | \
	  sed -e 's/^ *//' -e 's/$$/:/' >> $*.d
	@rm -f $*.d.tmp
