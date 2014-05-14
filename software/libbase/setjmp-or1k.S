/* setjmp.S. Implementation of setjmp.

   Copyright (C) 2010, Embecosm Limited <info@embecosm.com>

   Contributor Jeremy Bennett <jeremy.bennett@embecosm.com>

   Licensed under 2-clause BSD.
*/

/* -------------------------------------------------------------------------- */
/*!setjmp

   All processor state is saved in the buffer provided. We need not save r0
   (it will always be zero) and we need not save r11 (it will always be
   overridden here, and in longjmp).

   @todo We should prefer to save and restore the status register, but this is
	 not directly possible in user code. There is some merit in code to
	 set the flag, since in compiled C code, that might be expected to hold
	 a value. We leave a space for this information for future enhancement.

   @param[out] env(r3)  A buffer to save all the current processor state.

   @return  zero.*/
/* -------------------------------------------------------------------------- */
	.align	4
        .global	setjmp
        .type	setjmp,@function
setjmp:
	l.sw	4(r3),r1		/* Slot 0 saved for flag in future */
	l.sw	8(r3),r2
	l.sw	12(r3),r3
	l.sw	16(r3),r4
	l.sw	20(r3),r5
	l.sw	24(r3),r6
	l.sw	28(r3),r7
	l.sw	32(r3),r8
	l.sw	36(r3),r9
	l.sw	40(r3),r10		/* Skip r11 */
	l.sw	44(r3),r12
	l.sw	48(r3),r13
	l.sw	52(r3),r14
	l.sw	56(r3),r15
	l.sw	60(r3),r16
	l.sw	64(r3),r17
	l.sw	68(r3),r18
	l.sw	72(r3),r19
	l.sw	76(r3),r20
	l.sw	80(r3),r21
	l.sw	84(r3),r22
	l.sw	88(r3),r23
	l.sw	92(r3),r24
	l.sw	96(r3),r25
	l.sw	100(r3),r26
	l.sw	104(r3),r27
	l.sw	108(r3),r28
	l.sw	112(r3),r29
	l.sw	116(r3),r30
	l.sw	120(r3),r31


	l.jr	r9
	 l.addi	r11,r0,0		/* Zero result */


	.size	setjmp, .-setjmp
