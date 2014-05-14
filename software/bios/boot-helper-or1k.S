.section    .text, "ax", @progbits
.global     boot_helper
boot_helper:
	/* Invalidate instruction cache */
	/* FIXME: wcsr ICC, r0 */
	l.nop
	l.nop
	l.nop
	l.nop
	l.jr r7
