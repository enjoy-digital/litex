#!/bin/sh

AR=riscv64-unknown-elf-ar

for obj in \
    vsnprintf.c.o \
    vfprintf.c.o \
    fputc.c.o \
    filestrput.c.o \
    dtoa_ryu.c.o \
    ryu_table.c.o \
    ryu_umul128.c.o \
    ryu_log10.c.o \
    ryu_log2pow5.c.o \
    ryu_pow5bits.c.o \
    ryu_divpow2.c.o \
    qsort.c.o \
    strchr.c.o \
    strpbrk.c.o \
    strrchr.c.o \
    strcpy.c.o \
    strncpy.c.o \
    strcmp.S.o \
    strncmp.c.o \
    strcat.c.o \
    strncat.c.o \
    strlen.c.o \
    strnlen.c.o \
    strspn.c.o \
    memcmp.c.o \
    memset.S.o \
    memcpy.c.o \
    memmove.S.o \
    strstr.c.o \
    memchr.c.o \
    strtoul.c.o \
    strtol.c.o \
    snprintf.c.o \
    sprintf.c.o \
    rand.c.o \
    srand.c.o \
    abort.c.o \
    errno.c.o \
    strerror.c.o \
    strtod.c.o \
    ctype_.c.o \
    locale.c.o \
    mbtowc_r.c.o \
    wctomb_r.c.o \
    strcasecmp.c.o \
    isdigit.c.o \
; do
    $AR x "newlib/libc.a" $obj
    $AR csr "../libbase/libbase.a" $obj
    $AR csr "../libbase/libbase-nofloat.a" $obj
    rm $obj
done

