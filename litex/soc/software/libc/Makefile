include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

all: libc.a iob.c.o

CPUFAMILY=

ifneq ($(findstring $(CPU), serv femtorv picorv32 minerva vexriscv vexriscv_smp ibex cv32e40p rocket blackparrot),)
	CPUFAMILY = riscv
else ifeq ($(CPU), lm32)
	CPUFAMILY = lm32
else ifeq ($(CPU), mor1kx)
	CPUFAMILY = or1k
else ifeq ($(CPU), microwatt)
	CPUFAMILY = powerpc
else ifeq ($(CPU), zynq7000)
	CPUFAMILY = arm
else
	$(error Unsupported CPU)
endif

define CROSSFILE
[binaries]
c = '$(TRIPLE)-gcc'
ar = '$(TRIPLE)-ar'
as = '$(TRIPLE)-as'
nm = '$(TRIPLE)-nm'
strip = '$(TRIPLE)-strip'

[host_machine]
system = 'unknown'
cpu_family = '$(CPUFAMILY)'
cpu = '$(CPU)'
endian = '$(CPUENDIANNESS)'

[built-in options]
c_args = [ '-DPRINTF_LEVEL=1', $(foreach flag,$(filter-out $(INCLUDES) $(DEPFLAGS),$(CFLAGS)),'$(flag)',) ]
c_link_args = [ '-DPRINTF_LEVEL=1', $(foreach flag,$(LDFLAGS),'$(flag)',) ]
endef

export CROSSFILE
cross.txt:
	@echo "$$CROSSFILE" > $@

$(PICOLIBC_DIRECTORY)/newlib/libc/machine/$(CPUFAMILY)/meson.build:
	cp $(LIBC_DIRECTORY)/$(CPUFAMILY)-meson.build $@

libc.a: cross.txt $(PICOLIBC_DIRECTORY)/newlib/libc/machine/$(CPUFAMILY)/meson.build
	meson $(PICOLIBC_DIRECTORY) \
		-Dmultilib=false \
		-Dpicocrt=false \
		-Dincludedir=picolibc/$(TRIPLE)/include \
		-Dlibdir=picolibc/$(TRIPLE)/lib \
		--cross-file cross.txt
	meson compile
	cp newlib/libc.a libc.a

iob.c.o: $(LIBC_DIRECTORY)/iob.c
	$(compile)
	$(AR) csr libc.a iob.c.o

