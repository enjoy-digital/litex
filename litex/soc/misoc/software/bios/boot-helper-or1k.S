.section    .text, "ax", @progbits
.global     boot_helper
boot_helper:
	l.jr r6
	l.nop
