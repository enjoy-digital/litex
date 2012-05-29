Description := LatticeMico32

Configs := lm32
Arch := lm32

CC := clang

# TODO: mico32 should be renamed lm32 in LLVM
CFLAGS := -Wall -Werror -O3 -D_YUGA_LITTLE_ENDIAN=0 -D_YUGA_BIG_ENDIAN=1 -ccc-host-triple mico32-elf

FUNCTIONS := divsi3 modsi3 comparedf2 negsf2 negdf2 addsf3 subsf3 mulsf3 divsf3 \
  floatsisf floatunsisf fixsfsi fixunssfsi adddf3 subdf3 muldf3 divdf3 floatsidf floatunsidf fixdfsi fixunsdfsi

# Those are already implemented in HW and should not be needed.
# But the other functions directly depend on them.
FUNCTIONS += udivsi3 lshrdi3 muldi3 ashldi3
