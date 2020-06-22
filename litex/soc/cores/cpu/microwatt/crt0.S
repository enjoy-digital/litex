/* Copyright 2013-2014 IBM Corp.
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

#define EXCEPTION(nr)		\
	.=  nr;      \
	b	.

	/* More exception stubs */
	EXCEPTION(0x100)
	EXCEPTION(0x200)
	EXCEPTION(0x300)
	EXCEPTION(0x380)
	EXCEPTION(0x400)
	EXCEPTION(0x480)
	EXCEPTION(0x500)
	EXCEPTION(0x600)
	EXCEPTION(0x700)
	EXCEPTION(0x800)
	EXCEPTION(0x900)
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

	.text

