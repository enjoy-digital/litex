TARGET_PREFIX=$(TRIPLE)-

RM ?= rm -f
PYTHON ?= python3

CARGO_TRIPLE=$(subst or1k-linux,or1k-unknown-none,$(TRIPLE))

ifeq ($(CLANG),1)
CC_normal      := clang -target $(TRIPLE) -integrated-as
CX_normal      := clang++ -target $(TRIPLE) -integrated-as
else
CC_normal      := $(TARGET_PREFIX)gcc -std=gnu99
CX_normal      := $(TARGET_PREFIX)g++
endif
AR_normal      := $(TARGET_PREFIX)ar
LD_normal      := $(TARGET_PREFIX)ld
OBJCOPY_normal := $(TARGET_PREFIX)objcopy
CARGO_normal   := env CARGO_TARGET_DIR=$(realpath .)/cargo cargo build --target $(CARGO_TRIPLE)

CC_quiet      = @echo " CC      " $@ && $(CC_normal)
CX_quiet      = @echo " CX      " $@ && $(CX_normal)
AR_quiet      = @echo " AR      " $@ && $(AR_normal)
LD_quiet      = @echo " LD      " $@ && $(LD_normal)
OBJCOPY_quiet = @echo " OBJCOPY " $@ && $(OBJCOPY_normal)
CARGO_quiet   = @echo " CARGO   " $@ && $(CARGO_normal)

ifeq ($(V),1)
	CC = $(CC_normal)
	CX = $(CX_normal)
	AR = $(AR_normal)
	LD = $(LD_normal)
	OBJCOPY = $(OBJCOPY_normal)
	CARGO = $(CARGO_normal) --verbose
else
	CC = $(CC_quiet)
	CX = $(CX_quiet)
	AR = $(AR_quiet)
	LD = $(LD_quiet)
	OBJCOPY = $(OBJCOPY_quiet)
	CARGO = $(CARGO_quiet)
.SILENT:
endif

# http://scottmcpeak.com/autodepend/autodepend.html
# Generate *.d Makefile dependencies fragments, include using;
# -include $(OBJECTS:.o=.d)
DEPFLAGS += -MD -MP

# Toolchain options
#
INCLUDES = -I$(SOC_DIRECTORY)/software/include/base -I$(SOC_DIRECTORY)/software/include -I$(SOC_DIRECTORY)/common -I$(BUILDINC_DIRECTORY)
COMMONFLAGS = $(DEPFLAGS) -Os $(CPUFLAGS) -g3 -fomit-frame-pointer -ffunction-sections -Wall -fno-builtin -nostdinc $(INCLUDES)
CFLAGS = $(COMMONFLAGS) -fexceptions -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes -Werror=incompatible-pointer-types
CXXFLAGS = $(COMMONFLAGS) -std=c++11 -I$(SOC_DIRECTORY)/software/include/basec++ -fexceptions -fno-rtti -ffreestanding
LDFLAGS = --gc-sections -nostdlib -nodefaultlibs -L$(BUILDINC_DIRECTORY)
RUSTOUT = cargo/$(CARGO_TRIPLE)/debug
export RUSTFLAGS = -Ctarget-feature=+mul,+div,+ffl1,+cmov,+addc -Crelocation-model=static -Copt-level=s

define compilexx
$(CX) -c $(CXXFLAGS) $(1) $< -o $@
endef

define compile
$(CC) -c $(CFLAGS) $(1) $< -o $@
endef

define assemble
$(CC) -c $(CFLAGS) -o $@ $<
endef

define cargo
$(CARGO)
endef
