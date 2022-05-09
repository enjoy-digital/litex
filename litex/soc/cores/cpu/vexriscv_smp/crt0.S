.global main
.global isr
.global _start

.global smp_lottery_target
.global smp_lottery_lock
.global smp_lottery_args
.global smp_slave

.option arch,+zicsr

_start:
  j crt_init
  nop
  nop
  nop
  nop
  nop
  nop
  nop

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
  la a0, trap_entry
  csrw mtvec, a0
  sw x0, smp_lottery_lock, a1

smp_tyranny:
  csrr a0, mhartid
  beqz a0, data_init

smp_slave:
  lw a0, smp_lottery_lock
  beqz a0, smp_slave
  fence r, r

  .word(0x100F) //i$ flush
  lw x10, smp_lottery_args
  lw x11, smp_lottery_args+4
  lw x12, smp_lottery_args+8
  lw x13, smp_lottery_target
  jr x13

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

  call main
infinit_loop:
  j infinit_loop



//Initialized to avoid having them set to zero by BSS clear
.bss
  smp_lottery_target: .word 0
  smp_lottery_args:   .word 0; .word 0; .word 0
  smp_lottery_lock:   .word 0

