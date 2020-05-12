#define MIE_MEIE 	0x800

	.global _start
_start:
	j reset_vector

reset_vector:
	la sp, _fstack
	la t0, trap_vector
	csrw mtvec, t0

	// initialize .bss
	la t0, _fbss
	la t1, _ebss
1:	beq t0, t1, 2f
	sw zero, 0(t0)
	addi t0, t0, 4
	j 1b
2:
	// enable external interrupts
	li t0, MIE_MEIE
	csrs mie, t0

	call main
1:	j 1b

trap_vector:
	addi sp, sp, -16*4
	sw ra,  0*4(sp)
	sw t0,  1*4(sp)
	sw t1,  2*4(sp)
	sw t2,  3*4(sp)
	sw a0,  4*4(sp)
	sw a1,  5*4(sp)
	sw a2,  6*4(sp)
	sw a3,  7*4(sp)
	sw a4,  8*4(sp)
	sw a5,  9*4(sp)
	sw a6, 10*4(sp)
	sw a7, 11*4(sp)
	sw t3, 12*4(sp)
	sw t4, 13*4(sp)
	sw t5, 14*4(sp)
	sw t6, 15*4(sp)
	call isr
	lw ra,  0*4(sp)
	lw t0,  1*4(sp)
	lw t1,  2*4(sp)
	lw t2,  3*4(sp)
	lw a0,  4*4(sp)
	lw a1,  5*4(sp)
	lw a2,  6*4(sp)
	lw a3,  7*4(sp)
	lw a4,  8*4(sp)
	lw a5,  9*4(sp)
	lw a6, 10*4(sp)
	lw a7, 11*4(sp)
	lw t3, 12*4(sp)
	lw t4, 13*4(sp)
	lw t5, 14*4(sp)
	lw t6, 15*4(sp)
	addi sp, sp, 16*4
	mret
