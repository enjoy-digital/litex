/*
 * Copyright 2018, Serge Bazanski <serge@bazanski.pl>
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted.
 */

#include "picorv32-extraops.S"

/*
 * Interrupt vector.
 */
.global _start
_start:

.org 0x00000000 # Reset
  j _crt0

.org 0x00000010 # IRQ
_irq_vector:
  addi sp, sp, -16
  sw t0, 4(sp)
  sw ra, 8(sp)
  /* By convention, q2 holds true IRQ vector, but remains caller-save.
  We rely on the assumption that compiler-generated code will never touch
  the QREGs. q3 is truly scratch/caller-save. */
  picorv32_getq_insn(t0, q2)
  sw t0, 12(sp)

  jalr t0 // Call the true IRQ vector.

  lw t0, 12(sp)
  picorv32_setq_insn(q2, t0) // Restore the true IRQ vector.
  lw ra, 8(sp)
  lw t0, 4(sp)
  addi sp, sp, 16
  picorv32_retirq_insn() // return from interrupt


/*
 * IRQ handler, branched to from the vector.
 */
_irq:
  /* save x1/x2 to q1/q2 */
  picorv32_setq_insn(q2, x1)
  picorv32_setq_insn(q3, x2)

  /* use x1 to index into irq_regs */
  lui x1, %hi(irq_regs)
  addi x1, x1, %lo(irq_regs)

  /* use x2 as scratch space for saving registers */

  /* q0 (== x1), q2(== x2), q3 */
  picorv32_getq_insn(x2, q0)
  sw x2,   0*4(x1)
  picorv32_getq_insn(x2, q2)
  sw x2,   1*4(x1)
  picorv32_getq_insn(x2, q3)
  sw x2,   2*4(x1)

  /* save x3 - x31 */
  sw x3,   3*4(x1)
  sw x4,   4*4(x1)
  sw x5,   5*4(x1)
  sw x6,   6*4(x1)
  sw x7,   7*4(x1)
  sw x8,   8*4(x1)
  sw x9,   9*4(x1)
  sw x10, 10*4(x1)
  sw x11, 11*4(x1)
  sw x12, 12*4(x1)
  sw x13, 13*4(x1)
  sw x14, 14*4(x1)
  sw x15, 15*4(x1)
  sw x16, 16*4(x1)
  sw x17, 17*4(x1)
  sw x18, 18*4(x1)
  sw x19, 19*4(x1)
  sw x20, 20*4(x1)
  sw x21, 21*4(x1)
  sw x22, 22*4(x1)
  sw x23, 23*4(x1)
  sw x24, 24*4(x1)
  sw x25, 25*4(x1)
  sw x26, 26*4(x1)
  sw x27, 27*4(x1)
  sw x28, 28*4(x1)
  sw x29, 29*4(x1)
  sw x30, 30*4(x1)
  sw x31, 31*4(x1)

  /* update _irq_pending to the currently pending interrupts */
  picorv32_getq_insn(t0, q1)
  la t1, (_irq_pending)
  sw t0, 0(t1)

  /* prepare C handler stack */
  lui sp, %hi(_irq_stack)
  addi sp, sp, %lo(_irq_stack)

  /* call C handler */
  jal ra, isr

  /* use x1 to index into irq_regs */
  lui x1, %hi(irq_regs)
  addi x1, x1, %lo(irq_regs)

  /* restore q0 - q2 */
  lw x2,   0*4(x1)
  picorv32_setq_insn(q0, x2)
  lw x2,   1*4(x1)
  picorv32_setq_insn(q1, x2)
  lw x2,   2*4(x1)
  picorv32_setq_insn(q2, x2)

  /* restore x3 - x31 */
  lw x3,   3*4(x1)
  lw x4,   4*4(x1)
  lw x5,   5*4(x1)
  lw x6,   6*4(x1)
  lw x7,   7*4(x1)
  lw x8,   8*4(x1)
  lw x9,   9*4(x1)
  lw x10, 10*4(x1)
  lw x11, 11*4(x1)
  lw x12, 12*4(x1)
  lw x13, 13*4(x1)
  lw x14, 14*4(x1)
  lw x15, 15*4(x1)
  lw x16, 16*4(x1)
  lw x17, 17*4(x1)
  lw x18, 18*4(x1)
  lw x19, 19*4(x1)
  lw x20, 20*4(x1)
  lw x21, 21*4(x1)
  lw x22, 22*4(x1)
  lw x23, 23*4(x1)
  lw x24, 24*4(x1)
  lw x25, 25*4(x1)
  lw x26, 26*4(x1)
  lw x27, 27*4(x1)
  lw x28, 28*4(x1)
  lw x29, 29*4(x1)
  lw x30, 30*4(x1)
  lw x31, 31*4(x1)

  /* restore x1 - x2 from q registers */
  picorv32_getq_insn(x1, q1)
  picorv32_getq_insn(x2, q2)
  ret

/*
 * Reset handler, branched to from the vector.
 */
_crt0:
  /* zero-initialize all registers */
  addi x1, zero, 0
  addi x2, zero, 0
  addi x3, zero, 0
  addi x4, zero, 0
  addi x5, zero, 0
  addi x6, zero, 0
  addi x7, zero, 0
  addi x8, zero, 0
  addi x9, zero, 0
  addi x10, zero, 0
  addi x11, zero, 0
  addi x12, zero, 0
  addi x13, zero, 0
  addi x14, zero, 0
  addi x15, zero, 0
  addi x16, zero, 0
  addi x17, zero, 0
  addi x18, zero, 0
  addi x19, zero, 0
  addi x20, zero, 0
  addi x21, zero, 0
  addi x22, zero, 0
  addi x23, zero, 0
  addi x24, zero, 0
  addi x25, zero, 0
  addi x26, zero, 0
  addi x27, zero, 0
  addi x28, zero, 0
  addi x29, zero, 0
  addi x30, zero, 0
  addi x31, zero, 0

  /* mask all interrupts */
  li t0, 0xffffffff
  picorv32_maskirq_insn(zero, t0)
  /* reflect that in _irq_mask */
  la t1, _irq_mask
  sw t0, 0(t1)

#ifdef EXECUTE_IN_PLACE
  /* Load DATA */
  la t0, _erodata
  la t1, _fdata
  la t2, _edata
3:
  lw t3, 0(t0)
  sw t3, 0(t1)
  /* _edata is aligned to 16 bytes. Use word-xfers. */
  addi t0, t0, 4
  addi t1, t1, 4
  bltu t1, t2, 3b
#endif

  /* Clear BSS */
  la t0, _fbss
  la t1, _ebss
2:
  sw zero, 0(t0)
  addi t0, t0, 4
  bltu t0, t1, 2b

  /* set main stack */
  la sp, _fstack

  /* Set up address to IRQ handler since vector is hardcoded.
  By convention, q2 keeps the pointer to the true IRQ handler,
  to emulate relocatable interrupts. */
  la t0, _irq
  picorv32_setq_insn(q2, t0)

  /* jump to main */
  jal ra, main

1:
  /* loop forever */
  j 1b


/*
 * Enable interrupts by copying the software mask to the hardware mask
 */
.global _irq_enable
_irq_enable:
  /* Set _irq_enabled to true */
  la t0, _irq_enabled
  addi t1, zero, 1
  sw t1, 0(t0)
  /* Set the HW IRQ mask to _irq_mask */
  la t0, _irq_mask
  lw t0, 0(t0)
  picorv32_maskirq_insn(zero, t0)
  ret

/*
 * Disable interrupts by masking all interrupts (the mask should already be
 * up to date)
 */
.global _irq_disable
_irq_disable:
  /* Mask all IRQs */
  li t0, 0xffffffff
  picorv32_maskirq_insn(zero, t0)
  /* Set _irq_enabled to false */
  la t0, _irq_enabled
  sw zero, (t0)
  ret

/*
 * Set interrrupt mask.
 * This updates the software mask (for readback and interrupt inable/disable)
 * and the hardware mask.
 * 1 means interrupt is masked (disabled).
 */
.global _irq_setmask
_irq_setmask:
  /* Update _irq_mask */
  la t0, _irq_mask
  sw a0, (t0)
  /* Are interrupts enabled? */
  la t0, _irq_enabled
  lw t0, 0(t0)
  beq t0, zero, 1f
  /* If so, update the HW IRQ mask */
  picorv32_maskirq_insn(zero, a0)
1:
  ret


.section .bss
irq_regs:
  /* saved interrupt registers, x0 - x31 */
  .fill 32,4

  /* interrupt stack */
  .fill 256,4
_irq_stack:

/*
 * Bitfield of pending interrupts, updated on ISR entry.
 */
.global _irq_pending
_irq_pending:
  .word 0

/*
 * Software copy of enabled interrupts. Do not write directly, use
 * _irq_set_mask instead.
 */
.global _irq_mask
_irq_mask:
  .word 0

/*
 * Software state of global interrupts being enabled or disabled. Do not write
 * directly, use _irq_disable / _irq_enable instead.
 */
.global _irq_enabled
_irq_enabled:
  .word 0
