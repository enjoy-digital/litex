/* Copyright 2013-2014 IBM Corp.
 * Copyright 2020 Raptor Engineering, LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * 	http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
 * implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#define FIXUP_ENDIAN						   \
	tdi   0,0,0x48;	  /* Reverse endian of b . + 8		*/ \
	b     191f;	  /* Skip trampoline if endian is good	*/ \
	.long 0xa600607d; /* mfmsr r11				*/ \
	.long 0x01006b69; /* xori r11,r11,1			*/ \
	.long 0x05009f42; /* bcl 20,31,$+4			*/ \
	.long 0xa602487d; /* mflr r10				*/ \
	.long 0x14004a39; /* addi r10,r10,20			*/ \
	.long 0xa64b5a7d; /* mthsrr0 r10			*/ \
	.long 0xa64b7b7d; /* mthsrr1 r11			*/ \
	.long 0x2402004c; /* hrfid				*/ \
191:


/* Load an immediate 64-bit value into a register */
#define LOAD_IMM64(r, e)			\
	lis     r,(e)@highest;			\
	ori     r,r,(e)@higher;			\
	rldicr  r,r, 32, 31;			\
	oris    r,r, (e)@h;			\
	ori     r,r, (e)@l;

	. = 0
.global _start
_start:
	FIXUP_ENDIAN

	/* Grab our own address */
	bcl	20,31,$+4
0:	mflr	%r12

	/* Get our TOC */
	addis	%r2,%r12,(.TOC.-0b)@h
	addi	%r2,%r2,(.TOC.-0b)@l

	/* Copy data from ROM to SRAM */
	ld	%r3,_fdata@got(%r2)
	ld	%r4,_edata@got(%r2)
	ld	%r5,_fdata_rom@got(%r2)
	subf	%r6,%r3,%r4
	srdi.	%r6,%r6,3
	beq	1f
	li	%r10,0
	mtctr	%r6
0:	ldx	%r0,%r10,%r5
	stdx	%r0,%r10,%r3
	addi	%r10,%r10,8
	bdnz	0b
1:
	/* Clear BSS */
	ld	%r3,_fbss@got(%r2)
	ld	%r4,_ebss@got(%r2)
	subf	%r6,%r3,%r4
	srdi.	%r6,%r6,3
	beq	1f
	li	%r0,0
	subi	%r3,%r3,8
	mtctr	%r6
0:	stdu	%r0,8(%r3)
	bdnz	0b
1:
	/* setup stack */
	ld	%r1,_fstack@got(%r2)
	subi  %r1,%r1,0x100
	bl	main
	b .

#define REDZONE_SIZE    (512)
#define REG_SAVE_SIZE	((32 + 5)*8)
#define STACK_FRAME_C_MINIMAL   64

#define SAVE_NIA	(32*8)
#define SAVE_LR		(33*8)
#define SAVE_CTR	(34*8)
#define SAVE_CR		(35*8)
#define SAVE_SRR1	(36*8)

#define EXCEPTION(nr)	\
	.=  nr;		\
	b	.

#define FORWARD_EXCEPTION(nr)					\
	. = nr;							\
	stdu	%r1,-(REG_SAVE_SIZE+REDZONE_SIZE)(%r1);		\
	std	%r0,   1*8(%r1);				\
	LOAD_IMM64(%r0, nr);					\
	b	__isr

	/* More exception stubs */
	EXCEPTION(0x100)
	EXCEPTION(0x200)
	EXCEPTION(0x300)
	EXCEPTION(0x380)
	EXCEPTION(0x400)
	EXCEPTION(0x480)
	FORWARD_EXCEPTION(0x500)
	EXCEPTION(0x600)
	EXCEPTION(0x700)
	EXCEPTION(0x800)
	FORWARD_EXCEPTION(0x900)
	EXCEPTION(0x980)
	EXCEPTION(0xa00)
	EXCEPTION(0xb00)
	EXCEPTION(0xc00)
	EXCEPTION(0xd00)
	EXCEPTION(0xe00)
	EXCEPTION(0xe20)
	EXCEPTION(0xe40)
	EXCEPTION(0xe60)
	EXCEPTION(0xe80)
	EXCEPTION(0xf00)
	EXCEPTION(0xf20)
	EXCEPTION(0xf40)
	EXCEPTION(0xf60)
	EXCEPTION(0xf80)
#if 0
	EXCEPTION(0x1000)
	EXCEPTION(0x1100)
	EXCEPTION(0x1200)
	EXCEPTION(0x1300)
	EXCEPTION(0x1400)
	EXCEPTION(0x1500)
	EXCEPTION(0x1600)
#endif

//  Exception handler
__isr:
/*
 * Assume where we are coming from has a stack and can save there.
 * We save the full register set. Since we are calling out to C, we
 * could just save the ABI volatile registers
 */
/*
 * The first two lines below are executed in the exception handler, so that r0
 * can be used to store the origin exception vector
 */
//	stdu	%r1,-(REG_SAVE_SIZE+REDZONE_SIZE)(%r1)
//	std	%r0,   1*8(%r1)
//	std	%r1,   1*8(%r1)
	std	%r2,   2*8(%r1)
	std	%r3,   3*8(%r1)
	std	%r4,   4*8(%r1)
	std	%r5,   5*8(%r1)
	std	%r6,   6*8(%r1)
	std	%r7,   7*8(%r1)
	std	%r8,   8*8(%r1)
	std	%r9,   9*8(%r1)
	std	%r10, 10*8(%r1)
	std	%r11, 11*8(%r1)
	std	%r12, 12*8(%r1)
	std	%r13, 13*8(%r1)
	std	%r14, 14*8(%r1)
	std	%r15, 15*8(%r1)
	std	%r16, 16*8(%r1)
	std	%r17, 17*8(%r1)
	std	%r18, 18*8(%r1)
	std	%r19, 19*8(%r1)
	std	%r20, 20*8(%r1)
	std	%r21, 21*8(%r1)
	std	%r22, 22*8(%r1)
	std	%r23, 23*8(%r1)
	std	%r24, 24*8(%r1)
	std	%r25, 25*8(%r1)
	std	%r26, 26*8(%r1)
	std	%r27, 27*8(%r1)
	std	%r28, 28*8(%r1)
	std	%r29, 29*8(%r1)
	std	%r30, 30*8(%r1)
	std	%r31, 31*8(%r1)
	mr	%r10, %r0
	mfsrr0	%r0
	std	%r0,  SAVE_NIA(%r1)
	mflr	%r0
	std	%r0,  SAVE_LR(%r1)
	mfctr	%r0
	std	%r0,  SAVE_CTR(%r1)
	mfcr	%r0
	std	%r0,  SAVE_CR(%r1)
	mfsrr1	%r0
	std	%r0,  SAVE_SRR1(%r1)

	stdu	%r1,-STACK_FRAME_C_MINIMAL(%r1)

	/* Load IRQ handler address from SRAM */
	LOAD_IMM64(%r3, __isr_address)
	ld	%r3,   0(%r3)

	mtctr	%r3,
	mr	%r3, %r10
	bctrl
	nop
	ld	%r1, 0(%r1)

	ld	%r0,   1*8(%r1)
//	ld	%r1,   1*8(%r1) // do this at rfid
	ld	%r2,   2*8(%r1)
//	ld	%r3,   3*8(%r1) // do this at rfid
	ld	%r4,   4*8(%r1)
	ld	%r5,   5*8(%r1)
	ld	%r6,   6*8(%r1)
	ld	%r7,   7*8(%r1)
	ld	%r8,   8*8(%r1)
	ld	%r9,   9*8(%r1)
	ld	%r10, 10*8(%r1)
	ld	%r11, 11*8(%r1)
	ld	%r12, 12*8(%r1)
	ld	%r13, 13*8(%r1)
	ld	%r14, 14*8(%r1)
	ld	%r15, 15*8(%r1)
	ld	%r16, 16*8(%r1)
	ld	%r17, 17*8(%r1)
	ld	%r18, 18*8(%r1)
	ld	%r19, 19*8(%r1)
	ld	%r20, 20*8(%r1)
	ld	%r21, 21*8(%r1)
	ld	%r22, 22*8(%r1)
	ld	%r23, 23*8(%r1)
	ld	%r24, 24*8(%r1)
	ld	%r25, 25*8(%r1)
	ld	%r26, 26*8(%r1)
	ld	%r27, 27*8(%r1)
	ld	%r28, 28*8(%r1)
	ld	%r29, 29*8(%r1)
	ld	%r30, 30*8(%r1)
	ld	%r31, 31*8(%r1)

	ld	%r3, SAVE_LR(%r1)
	mtlr	%r3
	ld	%r3, SAVE_CTR(%r1)
	mtctr	%r3
	ld	%r3, SAVE_CR(%r1)
	mtcr	%r3
	ld	%r3, SAVE_SRR1(%r1)
	mtsrr1	%r3
	ld	%r3, SAVE_NIA(%r1)
	mtsrr0	%r3

	/* restore %r3 */
	ld	%r3, 3*8(%r1)

	/* do final fixup r1 */
	ld	%r1, 0*8(%r1)

	rfid

	.text

	.globl __isr_address
	.data
	.align 8
__isr_address:
	.long isr