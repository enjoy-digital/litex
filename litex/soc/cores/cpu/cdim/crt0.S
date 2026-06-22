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

crt_init:
  la $sp, _fstack

data_init:
	la	$t0, _fdata
	la	$t1, _edata
	la	$t2, _fdata_rom
data_loop:
	beq	$t0, $t1, data_done
	lw	$t3, 0($t2)
  	sw	$t3, 0($t0)
	addiu	$t0, $t0,4
  	addiu	$t2, $t2,4
  	b	data_loop
data_done:

bss_init:
	la	$t0, _fbss
  	la	$t1, _ebss
bss_loop:
	beq	$t0, $t1, bss_done
  	sw	$zero, 0($t0)
  	addiu	$t0, $t0, 4
	b	bss_loop
bss_done:

  la  $t9, main
  jalr $t9
inf_loop:
  b inf_loop
