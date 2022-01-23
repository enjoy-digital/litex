#include <stdint.h>
#include "system.h"
#include "generated/soc.h"

extern uint32_t _fdata_rom, _fdata, _edata, _fbss, _ebss, _fstack;

void _start(void);
void default_handler(void);

void _start(void) {
    uint32_t *y = &_fdata_rom;
    for (uint32_t *x = &_fdata; x < &_edata; x ++)
        *x = *y ++;

    for (uint32_t *x = &_fbss; x < &_ebss; x ++)
        *x = 0;

    UART0->ctrl = 0b11; // set rx and tx enable bits
    UART0->baud_div = CONFIG_CLOCK_FREQUENCY / 115200; // FIXME

    __asm__("bl main");
    while(1);
}

void default_handler(void) {
    while(1);
}


const void* isr_vector[] __attribute__((__used__)) __attribute__((section(".isr_vector"))) = {
    &_fstack,
    _start,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    default_handler,
    0,
    0,
    0,
    0,
    default_handler,
    default_handler,
    0,
    default_handler,
    default_handler
};
