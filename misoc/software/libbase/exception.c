void isr(void);

#ifdef __or1k__

#define EXTERNAL_IRQ 0x8

void exception_handler(unsigned long vect, unsigned long *regs,
                       unsigned long pc, unsigned long ea);
void exception_handler(unsigned long vect, unsigned long *regs,
                       unsigned long pc, unsigned long ea)
{
	if(vect == EXTERNAL_IRQ) {
		isr();
	} else {
		/* Unhandled exception */
		for(;;);
	}
}
#endif
