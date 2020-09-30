.section    .text, "ax", @progbits
.global     boot_helper
// void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr)
boot_helper:
	mtctr 	%r6,
	bctrl
	ba	0
