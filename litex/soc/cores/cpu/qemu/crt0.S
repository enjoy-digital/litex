.global main
.global isr
.global _start

_start:
	j crt_init
	nop
	nop
	nop
	nop
	nop
	nop
	nop

.global trap_entry
trap_entry:
#if __riscv_xlen == 64
	sd x1,  - 1*8(sp)
	sd x5,  - 2*8(sp)
	sd x6,  - 3*8(sp)
	sd x7,  - 4*8(sp)
	sd x10, - 5*8(sp)
	sd x11, - 6*8(sp)
	sd x12, - 7*8(sp)
	sd x13, - 8*8(sp)
	sd x14, - 9*8(sp)
	sd x15, -10*8(sp)
	sd x16, -11*8(sp)
	sd x17, -12*8(sp)
	sd x28, -13*8(sp)
	sd x29, -14*8(sp)
	sd x30, -15*8(sp)
	sd x31, -16*8(sp)
	addi sp, sp, -16*8
	call isr
	ld x1,  15*8(sp)
	ld x5,  14*8(sp)
	ld x6,  13*8(sp)
	ld x7,  12*8(sp)
	ld x10, 11*8(sp)
	ld x11, 10*8(sp)
	ld x12,  9*8(sp)
	ld x13,  8*8(sp)
	ld x14,  7*8(sp)
	ld x15,  6*8(sp)
	ld x16,  5*8(sp)
	ld x17,  4*8(sp)
	ld x28,  3*8(sp)
	ld x29,  2*8(sp)
	ld x30,  1*8(sp)
	ld x31,  0*8(sp)
	addi sp, sp, 16*8
#else
	sw x1,  - 1*4(sp)
	sw x5,  - 2*4(sp)
	sw x6,  - 3*4(sp)
	sw x7,  - 4*4(sp)
	sw x10, - 5*4(sp)
	sw x11, - 6*4(sp)
	sw x12, - 7*4(sp)
	sw x13, - 8*4(sp)
	sw x14, - 9*4(sp)
	sw x15, -10*4(sp)
	sw x16, -11*4(sp)
	sw x17, -12*4(sp)
	sw x28, -13*4(sp)
	sw x29, -14*4(sp)
	sw x30, -15*4(sp)
	sw x31, -16*4(sp)
	addi sp, sp, -16*4
	call isr
	lw x1,  15*4(sp)
	lw x5,  14*4(sp)
	lw x6,  13*4(sp)
	lw x7,  12*4(sp)
	lw x10, 11*4(sp)
	lw x11, 10*4(sp)
	lw x12,  9*4(sp)
	lw x13,  8*4(sp)
	lw x14,  7*4(sp)
	lw x15,  6*4(sp)
	lw x16,  5*4(sp)
	lw x17,  4*4(sp)
	lw x28,  3*4(sp)
	lw x29,  2*4(sp)
	lw x30,  1*4(sp)
	lw x31,  0*4(sp)
	addi sp, sp, 16*4
#endif
	mret
	.text

crt_init:
	la sp, _fstack
	la a0, trap_entry
	csrw mtvec, a0

data_init:
	la a0, _fdata
	la a1, _edata
	la a2, _fdata_rom
data_loop:
	beq a0, a1, data_done
#if __riscv_xlen == 64
	ld a3, 0(a2)
	sd a3, 0(a0)
	addi a0, a0, 8
	addi a2, a2, 8
#else
	lw a3, 0(a2)
	sw a3, 0(a0)
	addi a0, a0, 4
	addi a2, a2, 4
#endif
	j data_loop
data_done:

bss_init:
	la a0, _fbss
	la a1, _ebss
bss_loop:
	beq a0, a1, bss_done
#if __riscv_xlen == 64
	sd zero, 0(a0)
	addi a0, a0, 8
#else
	sw zero, 0(a0)
	addi a0, a0, 4
#endif
	j bss_loop
bss_done:

	call main
infinit_loop:
	j infinit_loop
