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

trap_entry:
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
  addi sp,sp,-16*8
  call isr
  ld x1 , 15*8(sp)
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
  addi sp,sp,16*8
  mret
  .text


crt_init:
  la sp, _fstack + 8
  la a0, trap_entry
  csrw mtvec, a0

bss_init:
  la a0, _fbss
  la a1, _ebss
bss_loop:
  beq a0,a1,bss_done
  sd zero,0(a0)
  add a0,a0,8
  j bss_loop
bss_done:

  call plic_init // initialize external interrupt controller
  li a0, 0x800   // external interrupt sources only (using LiteX timer);
                 // NOTE: must still enable mstatus.MIE!
  csrw mie,a0

  call main
inf_loop:
  j inf_loop
