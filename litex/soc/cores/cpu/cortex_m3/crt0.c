#include <stdint.h>
#include "system.h"
#include "generated/soc.h"

extern uint32_t _fdata_rom, _fdata, _edata, _fbss, _ebss, _fstack;
extern void isr(void);

void _start(void);
void default_handler(void);

volatile unsigned int irqs_enabled;

void _start(void) {
    __asm__(
        "mov r0, %0\n"
        "mov sp, r0\n" : : "r" (&_fstack)
    );
    uint32_t *y = &_fdata_rom;
    for (uint32_t *x = &_fdata; x < &_edata; x ++)
        *x = *y ++;

    for (uint32_t *x = &_fbss; x < &_ebss; x ++)
        *x = 0;

    __asm__("bl main");
    while(1);
}


void default_handler(void) {
    while(1);
}

const void* isr_vector[] __attribute__((__used__)) __attribute__((section(".isr_vector"))) = {
    &_fstack,
    _start, // reset
    default_handler, // nmi
    default_handler, // hard fault
    default_handler, // mem manage
    default_handler, // bus fault
    default_handler, // usage fault
    (void *) 0x55, // reserved
    0, // reserved
    0, // reserved
    0, // reserved
    default_handler, // svc
    default_handler, // debug mon
    0, // reserved
    default_handler, // pend sv
    default_handler, // systick
    // external
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
};

__asm__ (
"__gnu_thumb1_case_uhi:\n"
"push    {r0, r1}\n"
"mov     r1, lr\n"
"lsrs    r1, r1, #1\n"
"lsls    r0, r0, #1\n"
"lsls    r1, r1, #1\n"
"ldrh    r1, [r1, r0]\n"
"lsls    r1, r1, #1\n"
"add     lr, lr, r1\n"
"pop     {r0, r1}\n"
"bx      lr\n"
);
