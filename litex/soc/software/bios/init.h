#pragma once

typedef void (*init_func)(void);

extern init_func const __bios_init_start[];
extern init_func const __bios_init_end[];

#define define_init_func(f)                                           \
    const init_func __bios_init_##f __attribute__((__used__)) \
    __attribute__((__section__(".bios_init"))) = f
