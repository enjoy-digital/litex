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

.balign 256

vector_table:
  j trap_entry # 0 unused
  j trap_entry # 1 unused
  j trap_entry # 2 unused
  j trap_entry # 3 software
  j trap_entry # 4 unused
  j trap_entry # 5 unused
  j trap_entry # 6 unused
  j trap_entry # 7 timer
  j trap_entry # 8 unused
  j trap_entry # 9 unused
  j trap_entry # 10 unused
  j trap_entry # 11 external
  j trap_entry # 12 unused
  j trap_entry # 13 unused
  j trap_entry # 14 unused
  j trap_entry # 15 unused
  j trap_entry # 16 firq0
  j trap_entry # 17 firq1
  j trap_entry # 18 firq2
  j trap_entry # 19 firq3
  j trap_entry # 20 firq4
  j trap_entry # 21 firq5
  j trap_entry # 22 firq6
  j trap_entry # 23 firq7
  j trap_entry # 24 firq8
  j trap_entry # 25 firq9
  j trap_entry # 26 firq10
  j trap_entry # 27 firq11
  j trap_entry # 28 firq12
  j trap_entry # 29 firq13
  j trap_entry # 30 firq14
  j trap_entry # 31 unused

.global  trap_entry
trap_entry:
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
  .text

crt_init:
  la sp, _fstack
  la t0, vector_table
  csrw mtvec, t0

data_init:
  la t0, _fdata
  la t1, _edata
  la t2, _fdata_rom
data_loop:  
  beq t0, t1, data_done
  lw t3, 0(t2)
  sw t3, 0(t0)
  addi t0, t0, 4
  addi t2, t2, 4
  j data_loop
data_done:

bss_init:
  la t0, _fbss
  la t1, _ebss
bss_loop:  
  beq t0, t1, bss_done
  sw zero, 0(t0)
  addi t0, t0, 4
  j bss_loop
bss_done:

  call main

infinit_loop:
  j infinit_loop

