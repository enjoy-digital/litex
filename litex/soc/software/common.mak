ifeq ($(TRIPLE),--native--)
TARGET_PREFIX=
else
TARGET_PREFIX=$(TRIPLE)-
endif

RM ?= rm -f
PYTHON ?= python3
CCACHE ?=

ifeq ($(CLANG),1)
CC_normal      := $(CCACHE) clang -target $(TRIPLE) -integrated-as
CX_normal      := $(CCACHE) clang++ -target $(TRIPLE) -integrated-as
else
CC_normal      := $(CCACHE) $(TARGET_PREFIX)gcc -std=gnu99
CX_normal      := $(CCACHE) $(TARGET_PREFIX)g++
endif
AR_normal      := $(TARGET_PREFIX)gcc-ar
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

# http://scottmcpeak.com/autodepend/autodepend.html
# Generate *.d Makefile dependencies fragments, include using;
# -include $(OBJECTS:.o=.d)
DEPFLAGS += -MD -MP

# Toolchain options
#
INCLUDES = -I$(PICOLIBC_DIRECTORY)/newlib/libc/tinystdio \
           -I$(PICOLIBC_DIRECTORY)/newlib/libc/include \
           -I$(LIBBASE_DIRECTORY) \
           -I$(SOC_DIRECTORY)/software/include \
           -I$(SOC_DIRECTORY)/software \
           -I$(BUILDINC_DIRECTORY) \
           -I$(BUILDINC_DIRECTORY)/../libc \
           -I$(CPU_DIRECTORY)
COMMONFLAGS = $(DEPFLAGS) -Os $(CPUFLAGS) -g3 -fomit-frame-pointer -Wall -fno-builtin -fno-stack-protector $(INCLUDES)
ifneq ($(CPUFAMILY), arm)
COMMONFLAGS += -fexceptions
endif
CFLAGS = $(COMMONFLAGS) -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes
CXXFLAGS = $(COMMONFLAGS) -std=c++11 -I$(SOC_DIRECTORY)/software/include/basec++ -fno-rtti -ffreestanding
LDFLAGS = -nostdlib -nodefaultlibs -Wl,--no-dynamic-linker -Wl,--build-id=none $(CFLAGS) -L$(BUILDINC_DIRECTORY)

define compilexx
$(CX) -c $(CXXFLAGS) $(1) $< -o $@
endef

define compile
$(CC) -c $(CFLAGS) $(1) $< -o $@
endef

define assemble
$(CC) -c $(CFLAGS) -o $@ $<
endef
