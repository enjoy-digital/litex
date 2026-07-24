/*
 * This file is part of LiteX.
 *
 * Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
 * SPDX-License-Identifier: BSD-2-Clause
 *
 * Minimal Cortex-A9 startup for the Cyclone V HPS: the BIOS is loaded/launched from the
 * Preloader/U-Boot (ex: go 0x01000000), in Supervisor mode, MMU/Caches disabled (use U-Boot's
 * "dcache flush; dcache off; icache off" before "go" if needed).
 */

.syntax unified
.cpu cortex-a9
.fpu vfpv3
.arm

/* Exception Vectors (VBAR-relative, placed at the start of the image so that the entry point
   is the Reset vector; VBAR requires 32-byte alignment). */
.text
.align 5
.global _start
_start:
	b reset_handler /* Reset.            */
	b hang          /* Undefined.        */
	b hang          /* Supervisor Call.  */
	b hang          /* Prefetch Abort.   */
	b hang          /* Data Abort.       */
	b hang          /* Reserved.         */
	b irq_handler   /* IRQ.              */
	b hang          /* FIQ.              */

reset_handler:
	/* Disable IRQ/FIQ. */
	cpsid if

	/* Set the Vector Base Address to our vectors (and use VBAR: SCTLR.V=0). */
	ldr r0, =_start
	mcr p15, 0, r0, c12, c0, 0
	mrc p15, 0, r0, c1, c0, 0
	bic r0, r0, #(1 << 13)
	mcr p15, 0, r0, c1, c0, 0

	/* Enable VFP/NEON (the BIOS is built hard-float; not guaranteed to be on after U-Boot). */
	mrc p15, 0, r0, c1, c0, 2
	orr r0, r0, #(0xf << 20)
	mcr p15, 0, r0, c1, c0, 2
	isb
	mov r0, #(1 << 30)
	vmsr fpexc, r0

	/* Setup IRQ mode stack, then switch back to Supervisor mode with the main stack. */
	cps #0x12
	ldr sp, =_irq_stack_top
	cps #0x13
	ldr sp, =_fstack

	/* Copy .data from its load address to RAM. */
	ldr r0, =_fdata
	ldr r1, =_edata
	ldr r2, =_fdata_rom
1:	cmp r0, r1
	bhs 2f
	ldr r3, [r2], #4
	str r3, [r0], #4
	b   1b
2:
	/* Clear .bss. */
	ldr r0, =_fbss
	ldr r1, =_ebss
	mov r2, #0
1:	cmp r0, r1
	bhs 2f
	str r2, [r0], #4
	b   1b
2:
	bl litex_startup_init
	bl main
hang:
	b hang

/* IRQ trampoline: save the caller-saved registers + SPSR, call isr(), restore and return. */
irq_handler:
	sub   lr, lr, #4
	push  {r0-r3, r12, lr}
	mrs   r0, spsr
	push  {r0, r1}                /* r1: keeps the stack 8-byte aligned (AAPCS). */
	bl    isr
	pop   {r0, r1}
	msr   spsr_cxsf, r0
	ldmfd sp!, {r0-r3, r12, pc}^  /* ^: also restores CPSR from SPSR. */

/* IRQ mode stack. */
.section .bss
.align 3
_irq_stack:
	.space 0x400
_irq_stack_top:
