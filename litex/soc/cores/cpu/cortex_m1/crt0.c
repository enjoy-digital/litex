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
    0, // reserved
    0, // reserved
    0, // reserved
    0, // reserved
    0, // reserved
    0, // reserved
    0, // reserved
    default_handler, // svc
    0, // reserved
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
R"(
.syntax unified

.global __gnu_thumb1_case_uhi
__gnu_thumb1_case_uhi:
	push    {r0, r1}
	mov     r1, lr
	lsrs    r1, r1, #1
	lsls    r0, r0, #1
	lsls    r1, r1, #1
	ldrh    r1, [r1, r0]
	lsls    r1, r1, #1
	add     lr, lr, r1
	pop     {r0, r1}
	bx      lr

.global __gnu_thumb1_case_uqi
__gnu_thumb1_case_uqi:
	mov     r12, r1
	mov     r1, lr
	lsrs    r1, r1, #1
	lsls    r1, r1, #1
	ldrb    r1, [r1, r0]
	lsls    r1, r1, #1
	add     lr, lr, r1
	mov     r1, r12
	bx      lr

.global __aeabi_uldivmod
__aeabi_uldivmod:
	push	{r0, r1}
	mov	r0, sp
	push	{r0, lr}
	ldr	r0, [sp, #8]
	bl	__udivmoddi4
	ldr	r3, [sp, #4]
	mov	lr, r3
	add	sp, sp, #8
	pop	{r2, r3}
	bx      lr
)"
);
