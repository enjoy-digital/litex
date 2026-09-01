# VeeR EH1's DMA AXI slave only accepts word accesses. LiteX loops ICCM
# accesses from the LSU through this port, so writes to ICCM need aligned
# read-modify-write transactions. Other destinations retain normal memcpy
# semantics, including unaligned byte copies.

	.macro load_byte result, address, scratch0, scratch1
	li \scratch0, 0xff000000
	and \scratch1, \address, \scratch0
	li \scratch0, 0xee000000
	bne \scratch1, \scratch0, .Lload_byte_normal\@
	andi \scratch1, \address, -4
	lw \result, 0(\scratch1)
	andi \scratch1, \address, 3
	slli \scratch1, \scratch1, 3
	srl \result, \result, \scratch1
	andi \result, \result, 0xff
	j .Lload_byte_done\@
.Lload_byte_normal\@:
	lbu \result, 0(\address)
.Lload_byte_done\@:
	.endm

	.section .text, "ax", @progbits
	.p2align 2
	.global memcpy
	.type memcpy, @function
memcpy:
	mv t0, a0
	beqz a2, .Lmemcpy_done

	# ICCM occupies the fixed 0xee00_0000 region in the LiteX memory map.
	li t1, 0xff000000
	and t2, t0, t1
	li t1, 0xee000000
	beq t2, t1, .Lmemcpy_iccm

.Lmemcpy_bytes:
	load_byte t1, a1, t4, t5
	sb t1, 0(t0)
	addi t0, t0, 1
	addi a1, a1, 1
	addi a2, a2, -1
	bnez a2, .Lmemcpy_bytes
	ret

.Lmemcpy_iccm:
	andi t2, t0, -4
	lw t3, 0(t2)
	load_byte t1, a1, t4, t5
	andi t4, t0, 3
	slli t4, t4, 3
	sll t1, t1, t4
	li t5, 0xff
	sll t5, t5, t4
	not t5, t5
	and t3, t3, t5
	or t3, t3, t1
	sw t3, 0(t2)
	addi t0, t0, 1
	addi a1, a1, 1
	addi a2, a2, -1
	bnez a2, .Lmemcpy_iccm
	fence
	fence.i

.Lmemcpy_done:
	ret

	.size memcpy, .-memcpy
