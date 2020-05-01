/*
 * (C) Copyright 2012, Stefan Kristiansson <stefan.kristiansson@saunalahti.fi>
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of
 * the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston,
 * MA 02111-1307 USA
 */

#include <spr-defs.h>

/*
 * OR1K Architecture has a 128 byte "red zone" after the stack that can not be
 * touched by exception handlers. GCC uses this red zone for locals and
 * temps without needing to change the stack pointer.
 */
#define OR1K_RED_ZONE_SIZE	128

/*
 * We need 4 bytes (32 bits) * 32 registers space on the stack to save all the
 * registers.
 */
#define EXCEPTION_STACK_SIZE	((4*32) + OR1K_RED_ZONE_SIZE)

#define HANDLE_EXCEPTION                    ; \
    l.addi  r1, r1, -EXCEPTION_STACK_SIZE   ; \
    l.sw    0x1c(r1), r9                    ; \
    l.jal   _exception_handler              ; \
     l.nop                                  ; \
    l.lwz   r9, 0x1c(r1)                    ; \
    l.addi  r1, r1, EXCEPTION_STACK_SIZE    ; \
    l.rfe                                   ; \
     l.nop


.section    .text, "ax", @progbits
.global     _start
_start:
_reset_handler:
    l.movhi r0, 0
    l.movhi r1, 0
    l.movhi r2, 0
    l.movhi r3, 0
    l.movhi r4, 0
    l.movhi r5, 0
    l.movhi r6, 0
    l.movhi r7, 0
    l.movhi r8, 0
    l.movhi r9, 0
    l.movhi r10, 0
    l.movhi r11, 0
    l.movhi r12, 0
    l.movhi r13, 0
    l.movhi r14, 0
    l.movhi r15, 0
    l.movhi r16, 0
    l.movhi r17, 0
    l.movhi r18, 0
    l.movhi r19, 0
    l.movhi r20, 0
    l.movhi r21, 0
    l.movhi r22, 0
    l.movhi r23, 0
    l.movhi r24, 0
    l.movhi r25, 0
    l.movhi r26, 0
    l.movhi r27, 0
    l.movhi r28, 0
    l.movhi r29, 0
    l.movhi r30, 0
    l.movhi r31, 0

    l.ori   r21, r0, SPR_SR_SM
    l.mtspr r0, r21, SPR_SR
    l.movhi r21, hi(_reset_handler)
    l.ori   r21, r21, lo(_reset_handler)
    l.mtspr r0, r21, SPR_EVBAR
    /* enable caches */
    l.jal   _cache_init
     l.nop
    l.j     _crt0
     l.nop

    /* bus error */
    .org    0x200
    HANDLE_EXCEPTION

    /* data page fault */
    .org    0x300
    HANDLE_EXCEPTION

    /* instruction page fault */
    .org    0x400
    HANDLE_EXCEPTION

    /* tick timer */
    .org    0x500
    HANDLE_EXCEPTION

    /* alignment */
    .org    0x600
    HANDLE_EXCEPTION

    /* illegal instruction */
    .org    0x700
    HANDLE_EXCEPTION

    /* external interrupt */
    .org    0x800
    HANDLE_EXCEPTION

    /* D-TLB miss */
    .org    0x900
    HANDLE_EXCEPTION

    /* I-TLB miss */
    .org    0xa00
    HANDLE_EXCEPTION

    /* range */
    .org    0xb00
    HANDLE_EXCEPTION

    /* system call */
    .org    0xc00
    HANDLE_EXCEPTION

    /* floating point */
    .org    0xd00
    HANDLE_EXCEPTION

    /* trap */
    .org    0xe00
    HANDLE_EXCEPTION

    /* reserved */
    .org    0xf00
    HANDLE_EXCEPTION

    .org 0x1000
_crt0:
    /* Setup stack and global pointer */
    l.movhi    r1, hi(_fstack)
    l.ori     r1, r1, lo(_fstack)

    /* Clear BSS */
    l.movhi    r21, hi(_fbss)
    l.ori     r21, r21, lo(_fbss)
    l.movhi    r3, hi(_ebss)
    l.ori     r3, r3, lo(_ebss)
.clearBSS:
    l.sfeq  r21, r3
    l.bf    .callMain
     l.nop
    l.sw      0(r21), r0
    l.addi    r21, r21, 4
    l.j      .clearBSS
     l.nop

.callMain:
    l.j     main
     l.nop

_exception_handler:
    l.sw    0x00(r1), r2
    l.sw    0x04(r1), r3
    l.sw    0x08(r1), r4
    l.sw    0x0c(r1), r5
    l.sw    0x10(r1), r6
    l.sw    0x14(r1), r7
    l.sw    0x18(r1), r8
    l.sw    0x20(r1), r10
    l.sw    0x24(r1), r11
    l.sw    0x28(r1), r12
    l.sw    0x2c(r1), r13
    l.sw    0x30(r1), r14
    l.sw    0x34(r1), r15
    l.sw    0x38(r1), r16
    l.sw    0x3c(r1), r17
    l.sw    0x40(r1), r18
    l.sw    0x44(r1), r19
    l.sw    0x48(r1), r20
    l.sw    0x4c(r1), r21
    l.sw    0x50(r1), r22
    l.sw    0x54(r1), r23
    l.sw    0x58(r1), r24
    l.sw    0x5c(r1), r25
    l.sw    0x60(r1), r26
    l.sw    0x64(r1), r27
    l.sw    0x68(r1), r28
    l.sw    0x6c(r1), r29
    l.sw    0x70(r1), r30
    l.sw    0x74(r1), r31

    /* Save return address */
    l.or    r14, r0, r9
    /* Calculate exception vector from handler address */
    l.andi  r3, r9, 0xf00
    l.srli  r3, r3, 8
    /* Pass saved register state */
    l.or    r4, r0, r1
    /* Extract exception PC */
    l.mfspr r5, r0, SPR_EPCR_BASE
    /* Extract exception effective address */
    l.mfspr r6, r0, SPR_EEAR_BASE
    /* Extract exception SR */
    l.mfspr r7, r0, SPR_ESR_BASE
    /* Call exception handler with the link address as argument */
    l.jal   exception_handler
     l.nop

    /* Load return address */
    l.or    r9, r0, r14
    /* Restore state */
    l.lwz   r2, 0x00(r1)
    l.lwz   r3, 0x04(r1)
    l.lwz   r4, 0x08(r1)
    l.lwz   r5, 0x0c(r1)
    l.lwz   r6, 0x10(r1)
    l.lwz   r7, 0x14(r1)
    l.lwz   r8, 0x18(r1)
    l.lwz   r10, 0x20(r1)
    l.lwz   r11, 0x24(r1)
    l.lwz   r12, 0x28(r1)
    l.lwz   r13, 0x2c(r1)
    l.lwz   r14, 0x30(r1)
    l.lwz   r15, 0x34(r1)
    l.lwz   r16, 0x38(r1)
    l.lwz   r17, 0x3c(r1)
    l.lwz   r18, 0x40(r1)
    l.lwz   r19, 0x44(r1)
    l.lwz   r20, 0x48(r1)
    l.lwz   r21, 0x4c(r1)
    l.lwz   r22, 0x50(r1)
    l.lwz   r23, 0x54(r1)
    l.lwz   r24, 0x58(r1)
    l.lwz   r25, 0x5c(r1)
    l.lwz   r26, 0x60(r1)
    l.lwz   r27, 0x64(r1)
    l.lwz   r28, 0x68(r1)
    l.lwz   r29, 0x6c(r1)
    l.lwz   r30, 0x70(r1)
    l.lwz   r31, 0x74(r1)
    l.jr    r9
     l.nop

.global _cache_init
_cache_init:
    /*
    This function is to be used ONLY during reset, before main() is called.
    TODO: Perhaps break into individual enable instruction/data cache
          sections functions, and provide disable functions, also, all
          callable from C
    */

    /* Instruction cache enable */
    /* Check if IC present and skip enabling otherwise */
#if 1
.L6:
    l.mfspr r3,r0,SPR_UPR
    l.andi  r7,r3,SPR_UPR_ICP
    l.sfeq  r7,r0
    l.bf    .L8
    l.nop

    /* Disable IC */
    l.mfspr r6,r0,SPR_SR
    l.addi  r5,r0,-1
    l.xori  r5,r5,SPR_SR_ICE
    l.and   r5,r6,r5
    l.mtspr r0,r5,SPR_SR

    /* Establish cache block size
    If BS=0, 16;
    If BS=1, 32;
    r14 contain block size
    */
    l.mfspr r3,r0,SPR_ICCFGR
    l.andi  r7,r3,SPR_ICCFGR_CBS
    l.srli  r8,r7,7
    l.ori   r4,r0,16
    l.sll   r14,r4,r8

    /* Establish number of cache sets
    r10 contains number of cache sets
    r8 contains log(# of cache sets)
    */
    l.andi  r7,r3,SPR_ICCFGR_NCS
    l.srli  r8,r7,3
    l.ori   r4,r0,1
    l.sll   r10,r4,r8

    /* Invalidate IC */
    l.addi  r6,r0,0
    l.sll   r5,r14,r8

.L7:    l.mtspr r0,r6,SPR_ICBIR
    l.sfne  r6,r5
    l.bf    .L7
    l.add   r6,r6,r14

    /* Enable IC */
    l.mfspr r6,r0,SPR_SR
    l.ori   r6,r6,SPR_SR_ICE
    l.mtspr r0,r6,SPR_SR
    l.nop
    l.nop
    l.nop
    l.nop
    l.nop
    l.nop
    l.nop
    l.nop
    /* Data cache enable */
    /* Check if DC present and skip enabling otherwise */
#endif
.L8:
#if 1
    l.mfspr r3,r0,SPR_UPR
    l.andi  r7,r3,SPR_UPR_DCP
    l.sfeq  r7,r0
    l.bf    .L10
    l.nop
    /* Disable DC */
    l.mfspr r6,r0,SPR_SR
    l.addi  r5,r0,-1
    l.xori  r5,r5,SPR_SR_DCE
    l.and   r5,r6,r5
    l.mtspr r0,r5,SPR_SR
    /* Establish cache block size
       If BS=0, 16;
       If BS=1, 32;
       r14 contain block size
    */
    l.mfspr r3,r0,SPR_DCCFGR
    l.andi  r7,r3,SPR_DCCFGR_CBS
    l.srli  r8,r7,7
    l.ori   r4,r0,16
    l.sll   r14,r4,r8
    /* Establish number of cache sets
       r10 contains number of cache sets
       r8 contains log(# of cache sets)
    */
    l.andi  r7,r3,SPR_DCCFGR_NCS
    l.srli  r8,r7,3
    l.ori   r4,r0,1
    l.sll   r10,r4,r8
    /* Invalidate DC */
    l.addi  r6,r0,0
    l.sll   r5,r14,r8

.L9:
    l.mtspr r0,r6,SPR_DCBIR
    l.sfne  r6,r5
    l.bf    .L9
    l.add   r6,r6,r14
    /* Enable DC */
    l.mfspr r6,r0,SPR_SR
    l.ori   r6,r6,SPR_SR_DCE
    l.mtspr r0,r6,SPR_SR
#endif
.L10:
    /* Return */
    l.jr    r9
    l.nop
