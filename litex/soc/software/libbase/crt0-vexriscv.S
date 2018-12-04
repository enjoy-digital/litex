#define r_type_insn(_f7, _rs2, _rs1, _f3, _rd, _opc) \
.word (((_f7) << 25) | ((_rs2) << 20) | ((_rs1) << 15) | ((_f3) << 12) | ((_rd) << 7) | ((_opc) << 0))

#define LOAD_VIRTUAL(_rd, _rs1, _rs2 ) \
r_type_insn(0b0000000, _rs2, _rs1, 0b111, _rd, 0b0001111)

#define LOAD_TLB(_rd, _rs1, _rs2 ) \
r_type_insn(0b0000001, _rs2, _rs1, 0b111, _rd, 0b0001111)

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
  la sp, _fstack + 4
  la a0, trap_entry
  csrw mtvec, a0


mapping:
    li x5, 0x000C0000
    li x7, 0xf8040000
    LOAD_VIRTUAL(0, 5, 0)
    LOAD_TLB(0, 5, 7)

bss_init:
  la a0, _fbss
  la a1, _ebss
bss_loop:
  beq a0,a1,bss_done
  sw zero,0(a0)
  add a0,a0,4
  j bss_loop
bss_done:

  li a0, 0x880  //880 enable timer + external interrupt sources (until mstatus.MIE is set, they will never trigger an interrupt)
  csrw mie,a0

  call main
infinit_loop:
  j infinit_loop
