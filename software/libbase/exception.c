void isr(void);

#ifdef __or1k__

#define EXTERNAL_IRQ 0x800

void exception_handler(unsigned long vect, unsigned long *sp);
void exception_handler(unsigned long vect, unsigned long *sp)
{
	if((vect & 0xf00) == EXTERNAL_IRQ) {
		isr();
	} else {
		/* Unhandled exception */
		for(;;);
	}
}
#endif
