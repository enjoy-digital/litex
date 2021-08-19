include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

all: libc.a iob.c.o missing.c.o

CPUFAMILY=

ifneq ($(findstring $(CPU), serv femtorv picorv32 minerva vexriscv vexriscv_smp ibex cv32e40p rocket blackparrot),)
	CPUFAMILY = riscv
else ifeq ($(CPU), lm32)
	CPUFAMILY = lm32
else ifeq ($(CPU), mor1kx)
	CPUFAMILY = or1k
else ifeq ($(CPU), microwatt)
	CPUFAMILY = powerpc
	CFLAGS += -DLONG_LONG_MIN=LLONG_MIN -DLONG_LONG_MAX=LLONG_MAX -DLONG_LONG_MIN=LLONG_MIN -DULONG_LONG_MAX=ULLONG_MAX
else ifeq ($(CPU), zynq7000)
	CPUFAMILY = arm
else
	$(error Unsupported CPU)
endif

define CROSSFILE
[binaries]
c = '$(TRIPLE)-gcc'
ar = '$(TRIPLE)-gcc-ar'
as = '$(TRIPLE)-as'
nm = '$(TRIPLE)-gcc-nm'
strip = '$(TRIPLE)-strip'

[host_machine]
system = 'unknown'
cpu_family = '$(CPUFAMILY)'
cpu = '$(CPU)'
endian = '$(CPUENDIANNESS)'

[built-in options]
c_args = [ $(foreach flag,$(filter-out $(DEPFLAGS) -flto,$(CFLAGS)),'$(flag)',) ]
c_link_args = [ $(foreach flag,$(filter-out -flto,$(LDFLAGS)),'$(flag)',) ]
endef

export CROSSFILE
cross.txt:
	@echo "$$CROSSFILE" > $@

libc.a: cross.txt
	if [ -d "$(LIBC_DIRECTORY)/$(CPUFAMILY)" ]; then \
		cp $(LIBC_DIRECTORY)/$(CPUFAMILY)/* $(PICOLIBC_DIRECTORY)/newlib/libc/machine/$(CPUFAMILY)/ ;\
	fi

	meson $(PICOLIBC_DIRECTORY) \
		-Dmultilib=false \
		-Dpicocrt=false \
		-Dnewlib-global-errno=true \
		-Dio-long-long=true \
		-Dincludedir=picolibc/$(TRIPLE)/include \
		-Dlibdir=picolibc/$(TRIPLE)/lib \
		--cross-file cross.txt

	meson compile
	cp newlib/libc.a libc.a

iob.c.o: $(LIBC_DIRECTORY)/iob.c
	$(compile)
	$(AR) csr libc.a $@

missing.c.o: $(LIBC_DIRECTORY)/missing.c
	$(compile)
	$(AR) csr libc.a $@

