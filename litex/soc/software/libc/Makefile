include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

libc.a:
	meson $(PICOLIBC_DIRECTORY) \
		-Dmultilib=false \
		--cross-file "$(LIBC_DIRECTORY)/cross-rv32im.txt"
	meson compile
	cp newlib/libc.a libc.a

