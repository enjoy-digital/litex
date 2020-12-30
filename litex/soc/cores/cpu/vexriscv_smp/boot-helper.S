.section    .text, "ax", @progbits
.global boot_helper
.global smp_lottery_target
.global smp_lottery_lock
.global smp_lottery_args

boot_helper:
	sw x10, smp_lottery_args  , x14
	sw x11, smp_lottery_args+4, x14
	sw x12, smp_lottery_args+8, x14
	sw x13, smp_lottery_target, x14
	fence w, w
	li x15, 1
	sw x15, smp_lottery_lock, x14
	jr x13
