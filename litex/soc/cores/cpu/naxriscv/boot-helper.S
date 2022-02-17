.section    .text, "ax", @progbits
.global     boot_helper
boot_helper:
    li x13, 0x40F00000
	jr x13
