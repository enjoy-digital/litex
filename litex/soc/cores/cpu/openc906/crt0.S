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
  la sp, _fstack
  la t0, trap_entry
  csrw mtvec, t0
  # Invalidate L1I+L1D, Branch History Table, Branch Target Bufer
  li t0, 0x70013
  csrw 0x7c2, t0
  # Enable L1I+L1D, Return Stack, BHT, BTB
  li t0, 0x73
  csrs 0x7c1, t0
  # Enable Unaligned Access, User-mode cache operation, CLINT S-mode
  # interrupts, PTE memory attributes and T-HEAD extension
  li t0, 0x638000
  csrs 0x7c0, t0
  # Enable L1I+L1D prefetch, Loop enhancement
  # Bypass L1 for write operations larger than 3 cache lines
  # Prefetch 8 cache lines
  li t0, 0x450c
  csrs 0x7c5, t0

data_init:
  la t0, _fdata
  la t1, _edata
  la t2, _fdata_rom
data_loop:
  beq t0,t1,data_done
  ld t3,0(t2)
  sd t3,0(t0)
  add t0,t0,8
  add t2,t2,8
  j data_loop
data_done:

bss_init:
  la t0, _fbss
  la t1, _ebss
bss_loop:
  beq t0,t1,bss_done
  sd zero,0(t0)
  add t0,t0,8
  j bss_loop
bss_done:

  call plic_init // initialize external interrupt controller
  li t0, 0x800   // external interrupt sources only (using LiteX timer);
                 // NOTE: must still enable mstatus.MIE!
  csrw mie,t0

  call main
inf_loop:
  j inf_loop
