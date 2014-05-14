/* 
 * setjmp/longjmp for LatticeMico32.
 * Contributed by Jon Beniston <jon@beniston.com>
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 */
 
	.section	.text
	.align	4

	.globl	setjmp
	.type	setjmp,@function
	.globl	longjmp
	.type	longjmp,@function

/* setjmp: save all callee saves into jmp_buf
   r1 - Address of jmp_buf
*/

setjmp:
        sw      (r1+0), r11
        sw      (r1+4), r12
        sw      (r1+8), r13
        sw      (r1+12), r14
        sw      (r1+16), r15
        sw      (r1+20), r16
        sw      (r1+24), r17
        sw      (r1+28), r18
        sw      (r1+32), r19
        sw      (r1+36), r20
        sw      (r1+40), r21
        sw      (r1+44), r22
        sw      (r1+48), r23
        sw      (r1+52), r24
        sw      (r1+56), r25
        sw      (r1+60), gp
        sw      (r1+64), fp
        sw      (r1+68), sp
        sw      (r1+72), ra
        mvi     r1, 0
        ret

/* longjmp: restore all callee saves from jmp_buf
   r1 - Address of jmb_buf
   r2 - Value to return with
*/

        .global     longjmp
        .type       longjmp,@function
        .align      4

longjmp:
        lw      r11, (r1+0)
        lw      r12, (r1+4)
        lw      r13, (r1+8)
        lw      r14, (r1+12)
        lw      r15, (r1+16)
        lw      r16, (r1+20)
        lw      r17, (r1+24)
        lw      r18, (r1+28)
        lw      r19, (r1+32)
        lw      r20, (r1+36)
        lw      r21, (r1+40)
        lw      r22, (r1+44)
        lw      r23, (r1+48)
        lw      r24, (r1+52)
        lw      r25, (r1+56)
        lw      gp, (r1+60)
        lw      fp, (r1+64)
        lw      sp, (r1+68)
        lw      ra, (r1+72)
        mv      r1, r2
        ret


