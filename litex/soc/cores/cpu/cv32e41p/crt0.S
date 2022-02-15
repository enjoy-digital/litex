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
  j trap_entry # 31 firq15

.global  trap_entry
trap_entry:
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
  addi sp,sp,-16*4
  call isr
  lw x1 , 15*4(sp)
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
  addi sp,sp,16*4
  mret
  .text


crt_init:
  la sp, _fstack
  la a0, vector_table
  csrw mtvec, a0

data_init:
  la a0, _fdata
  la a1, _edata
  la a2, _fdata_rom
data_loop:
  beq a0,a1,data_done
  lw a3,0(a2)
  sw a3,0(a0)
  add a0,a0,4
  add a2,a2,4
  j data_loop
data_done:

bss_init:
  la a0, _fbss
  la a1, _ebss
bss_loop:
  beq a0,a1,bss_done
  sw zero,0(a0)
  add a0,a0,4
  j bss_loop
bss_done:

  li a0, 0x7FFF0880  //7FFF0880 enable timer + external interrupt + fast interrupt sources (until mstatus.MIE is set, they will never trigger an interrupt)
  csrw mie,a0

  j main
infinit_loop:
  j infinit_loop
