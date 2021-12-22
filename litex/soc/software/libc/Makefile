include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

all: libc.a

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
cross.txt:
	@echo "$$CROSSFILE" > $@

__libc.a: cross.txt
	if [ -d "$(LIBC_DIRECTORY)/$(CPUFAMILY)" ]; then \
		cp $(LIBC_DIRECTORY)/$(CPUFAMILY)/* $(PICOLIBC_DIRECTORY)/newlib/libc/machine/$(CPUFAMILY)/ ;\
	fi

	meson $(PICOLIBC_DIRECTORY) \
		-Dmultilib=false \
		-Dpicocrt=false \
		-Datomic-ungetc=false \
		-Dthread-local-storage=false \
		-Dio-long-long=true \
		-Dformat-default=integer \
		-Dincludedir=picolibc/$(TRIPLE)/include \
		-Dlibdir=picolibc/$(TRIPLE)/lib \
		--cross-file cross.txt

	meson compile
	cp newlib/libc.a __libc.a

_libc.a: $(LIBC_DIRECTORY)/stdio.c __libc.a
	$(compile)
	$(AR) csr __libc.a $@
	cp __libc.a _libc.a

libc.a: $(LIBC_DIRECTORY)/missing.c _libc.a
	$(compile)
	$(AR) csr _libc.a $@
	cp _libc.a libc.a
