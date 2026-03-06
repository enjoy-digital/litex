include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

all: libc.a

LIBC_MODE ?= full
ifeq ($(LIBC_MODE),minimal)
ifeq ($(CPUFAMILY),riscv)
EFFECTIVE_LIBC_MODE = minimal
else
EFFECTIVE_LIBC_MODE = full
endif
else
EFFECTIVE_LIBC_MODE = full
endif

CFLAGS = $(COMMONFLAGS) -Wpragmas

ifeq ($(CPU), microwatt)
	CFLAGS += -DLONG_LONG_MIN=LLONG_MIN -DLONG_LONG_MAX=LLONG_MAX -DLONG_LONG_MIN=LLONG_MIN -DULONG_LONG_MAX=ULLONG_MAX
endif

ifeq ($(CCACHE), )
	MESON_CROSS_CC = '$(TRIPLE)-gcc'
else
	MESON_CROSS_CC = ['$(CCACHE)', '$(TRIPLE)-gcc']
endif

define CROSSFILE
[binaries]
c     = $(MESON_CROSS_CC)
ar    = '$(TRIPLE)-gcc-ar'
as    = '$(TRIPLE)-as'
nm    = '$(TRIPLE)-gcc-nm'
strip = '$(TRIPLE)-strip'

[host_machine]
system     = 'unknown'
cpu_family = '$(CPUFAMILY)'
cpu        = '$(CPU)'
endian     = '$(CPUENDIANNESS)'

[built-in options]
c_args      = [ $(foreach flag,$(filter-out $(DEPFLAGS) -flto,$(CFLAGS)),'$(flag)',) ]
c_link_args = [ $(foreach flag,$(filter-out -flto,$(LDFLAGS)),'$(flag)',) ]
endef

export CROSSFILE
MESON_CROSS_FILE = $(BUILDINC_DIRECTORY)/cross-picolibc.txt

$(MESON_CROSS_FILE):
	@echo "$$CROSSFILE" > $@

PICOLIBC_SRC_DIR = $(BUILDINC_DIRECTORY)/../picolibc_src

PICO_MESON_FLAGS = \
	-Dmultilib=false \
	-Dpicocrt=false \
	-Datomic-ungetc=false \
	-Dthread-local-storage=false \
	-Dnewlib-multithread=false \
	-Dnewlib-retargetable-locking=false \
	-Dnewlib-iconv-encodings=none \
	-Dio-long-long=true \
	-Dformat-default=$(PICOLIBC_FORMAT) \
	-Dincludedir=picolibc/$(TRIPLE)/include \
	-Dlibdir=picolibc/$(TRIPLE)/lib

$(PICOLIBC_SRC_DIR): $(MESON_CROSS_FILE)
	$(RM) -r $(PICOLIBC_SRC_DIR)
	cp -a $(PICOLIBC_DIRECTORY) $(BUILDINC_DIRECTORY)/../picolibc_src

	if [ -d "$(LIBC_DIRECTORY)/$(CPUFAMILY)" ]; then \
		cp $(LIBC_DIRECTORY)/$(CPUFAMILY)/* $(BUILDINC_DIRECTORY)/../picolibc_src/newlib/libc/machine/$(CPUFAMILY)/ ;\
	fi

configure-picolibc: $(PICOLIBC_SRC_DIR)
	if [ -f build.ninja ]; then \
		meson setup . $(PICOLIBC_SRC_DIR) $(PICO_MESON_FLAGS) --cross-file $(MESON_CROSS_FILE) --wipe; \
	else \
		meson setup . $(PICOLIBC_SRC_DIR) $(PICO_MESON_FLAGS) --cross-file $(MESON_CROSS_FILE); \
	fi

__libc.a: configure-picolibc
	meson compile
	cp newlib/libc.a __libc.a

FORMAT_DEFAULT_DEFINE = -DFORMAT_DEFAULT_$(shell echo $(PICOLIBC_FORMAT) | tr a-z A-Z)
MINIMAL_PICOLIBC_CFLAGS = \
	$(filter-out $(DEPFLAGS),$(CFLAGS)) \
	-Wpragmas \
	-I$(PICOLIBC_SRC_DIR)/newlib/libm/common \
	-I$(PICOLIBC_SRC_DIR)/newlib/libc/machine/$(CPUFAMILY) \
	-I$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio \
	-I$(PICOLIBC_SRC_DIR)/newlib/libc/include \
	-I$(PICOLIBC_SRC_DIR)/semihost \
	-include $(CURDIR)/picolibc.h \
	-nostdlib \
	-fno-common \
	-frounding-math \
	-fsignaling-nans \
	-fno-stack-protector \
	-fno-builtin-copysignl \
	-U_FORTIFY_SOURCE \
	$(FORMAT_DEFAULT_DEFINE) \
	-Werror=implicit-function-declaration \
	-Werror=vla \
	-Warray-bounds \
	-Wold-style-definition \
	-Werror=double-promotion \
	-Wno-missing-braces \
	-Wno-implicit-int \
	-Wno-return-type \
	-D_LIBC

MINIMAL_PICOLIBC_SRCS = \
	$(PICOLIBC_SRC_DIR)/newlib/libc/ctype/ctype_.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/errno/errno.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/string/strchr.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/string/strncpy.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/string/strncmp.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/string/strnlen.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/fgetc.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/fputc.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/fputs.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/printf.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/puts.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/strtoul.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/machine/riscv/memcpy-asm.S \
	$(PICOLIBC_SRC_DIR)/newlib/libc/machine/riscv/memmove.S \
	$(PICOLIBC_SRC_DIR)/newlib/libc/machine/riscv/memset.S \
	$(PICOLIBC_SRC_DIR)/newlib/libc/machine/riscv/strcmp.S \
	$(PICOLIBC_SRC_DIR)/newlib/libc/machine/riscv/strcpy.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/machine/riscv/strlen.c

ifeq ($(PICOLIBC_FORMAT),integer)
MINIMAL_PICOLIBC_SRCS += $(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/vfiprintf.c
else ifeq ($(PICOLIBC_FORMAT),float)
MINIMAL_PICOLIBC_SRCS += \
	$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/vfprintff.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/ftoa_engine.c
else
MINIMAL_PICOLIBC_SRCS += \
	$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/vfprintf.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/dtoa_engine.c \
	$(PICOLIBC_SRC_DIR)/newlib/libc/tinystdio/dtoa_data.c \
	$(PICOLIBC_SRC_DIR)/newlib/libm/machine/riscv/s_fpclassify.c
endif

define minimal_obj
minimal_$(subst /,_,$(basename $(1))).o
endef

MINIMAL_PICOLIBC_OBJECTS = $(foreach src,$(MINIMAL_PICOLIBC_SRCS),$(call minimal_obj,$(src)))

# The minimal sources live in the copied picolibc staging tree, so make must
# materialize that tree before it can resolve these file prerequisites.
$(MINIMAL_PICOLIBC_SRCS): | $(PICOLIBC_SRC_DIR)

define compile_minimal_c
$(CC) -c $(MINIMAL_PICOLIBC_CFLAGS) $(1) $< -o $@
endef

define compile_minimal_s
$(CC) -c $(MINIMAL_PICOLIBC_CFLAGS) $< -o $@
endef

define add_minimal_rule
$(call minimal_obj,$(1)): $(1) configure-picolibc
	$$(if $$(filter .S,$$(suffix $(1))),$$(compile_minimal_s),$$(call compile_minimal_c,))
endef

$(foreach src,$(MINIMAL_PICOLIBC_SRCS),$(eval $(call add_minimal_rule,$(src))))

__libc_minimal.a: $(MINIMAL_PICOLIBC_OBJECTS)
	$(AR) crs $@ $(MINIMAL_PICOLIBC_OBJECTS)

_libc.a: $(LIBC_DIRECTORY)/stdio.c __libc.a
	$(compile)
	$(AR) csr __libc.a $@
	cp __libc.a _libc.a

_libc_minimal.a: $(LIBC_DIRECTORY)/stdio.c __libc_minimal.a
	$(compile)
	$(AR) csr __libc_minimal.a $@
	cp __libc_minimal.a _libc_minimal.a

libc-minimal.a: $(LIBC_DIRECTORY)/missing.c _libc_minimal.a
	$(compile)
	$(AR) csr _libc_minimal.a $@
	cp _libc_minimal.a libc-minimal.a

ifeq ($(EFFECTIVE_LIBC_MODE),minimal)
libc.a: libc-minimal.a
	cp libc-minimal.a libc.a
else
libc.a: $(LIBC_DIRECTORY)/missing.c _libc.a
	$(compile)
	$(AR) csr _libc.a $@
	cp _libc.a libc.a
endif
