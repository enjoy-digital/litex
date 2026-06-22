.global main
.global isr
.global _start

.global smp_lottery_target
.global smp_lottery_lock
.global smp_lottery_args
.global smp_slave

#define MSTATUS_FS_INITIAL (1 << 13)
#define MSTATUS_FS_CLEAN (2 << 13)
#define MSTATUS_FS_DIRTY (3 << 13)
#define MSTATUS_FS_MASK (3 << 13)

#if __riscv_xlen == 64
#define STORE sd
#define LOAD ld
#define WORD 8
#else
#define STORE sw
#define LOAD lw
#define WORD 4
#endif

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
  STORE x1,  - 1*WORD(sp)
  STORE x5,  - 2*WORD(sp)
  STORE x6,  - 3*WORD(sp)
  STORE x7,  - 4*WORD(sp)
  STORE x10, - 5*WORD(sp)
  STORE x11, - 6*WORD(sp)
  STORE x12, - 7*WORD(sp)
  STORE x13, - 8*WORD(sp)
  STORE x14, - 9*WORD(sp)
  STORE x15, -10*WORD(sp)
  STORE x16, -11*WORD(sp)
  STORE x17, -12*WORD(sp)
  STORE x28, -13*WORD(sp)
  STORE x29, -14*WORD(sp)
  STORE x30, -15*WORD(sp)
  STORE x31, -16*WORD(sp)
  addi sp,sp,-16*WORD
  call isr
  LOAD x1 , 15*WORD(sp)
  LOAD x5,  14*WORD(sp)
  LOAD x6,  13*WORD(sp)
  LOAD x7,  12*WORD(sp)
  LOAD x10, 11*WORD(sp)
  LOAD x11, 10*WORD(sp)
  LOAD x12,  9*WORD(sp)
  LOAD x13,  8*WORD(sp)
  LOAD x14,  7*WORD(sp)
  LOAD x15,  6*WORD(sp)
  LOAD x16,  5*WORD(sp)
  LOAD x17,  4*WORD(sp)
  LOAD x28,  3*WORD(sp)
  LOAD x29,  2*WORD(sp)
  LOAD x30,  1*WORD(sp)
  LOAD x31,  0*WORD(sp)
  addi sp,sp,16*WORD
  mret
  .text


crt_init:
  la sp, _fstack
  la a0, trap_entry
  csrw mtvec, a0
  
enable_fpu:
  li x1, MSTATUS_FS_INITIAL
  csrs mstatus, x1

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

  call plic_init // initialize external interrupt controller
  li t0, 0x800   // external interrupt sources only (using LiteX timer);
                 // NOTE: must still enable mstatus.MIE!
  csrw mie,t0

  call main
infinit_loop:
  j infinit_loop

//Initialized to avoid having them set to zero by BSS clear
.bss
  smp_lottery_target: .word 0
  smp_lottery_args:   .word 0; .word 0; .word 0
  smp_lottery_lock:   .word 0

