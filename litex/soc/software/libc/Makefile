include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

pINCLUDES = -I$(PICOLIBC_DIRECTORY)/newlib/libc/tinystdio \
            -I$(PICOLIBC_DIRECTORY)/newlib/libc/include \
            -I$(SOC_DIRECTORY)/software/include \
            -I$(BUILDINC_DIRECTORY)/../libc \
            -I$(BUILDINC_DIRECTORY) \
            -I$(CPU_DIRECTORY)

pCOMMONFLAGS = -Os $(CPUFLAGS) -g3 -fomit-frame-pointer -Wall -fno-builtin -nostdlib -fno-stack-protector $(pINCLUDES)
pCFLAGS = $(pCOMMONFLAGS) -fexceptions -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes

all: libc.a iob.c.o

iob.c.o:
	$(CC) \
		-c $(LIBC_DIRECTORY)/iob.c \
		-o $@ \
		$(pCFLAGS)
	$(AR) csr libc.a iob.c.o

libc.a:
	meson $(PICOLIBC_DIRECTORY) \
		-Dmultilib=false \
		--cross-file "$(LIBC_DIRECTORY)/cross-rv32im.txt"
	meson compile
	cp newlib/libc.a libc.a

