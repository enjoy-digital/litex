include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

newlib/libc.a:
	$(LIBC_DIRECTORY)/do-rv32im-configure $(PICOLIBC_DIRECTORY)
	meson compile
	sh $(LIBC_DIRECTORY)/swap_libc.sh
