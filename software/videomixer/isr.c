#include <hw/csr.h>
#include <irq.h>
#include <uart.h>

#include "dvisampler0.h"
#include "dvisampler1.h"

void isr(void);
void isr(void)
{
	unsigned int irqs;
	
	irqs = irq_pending() & irq_getmask();
	
	if(irqs & (1 << UART_INTERRUPT))
		uart_isr();
	if(irqs & (1 << DVISAMPLER0_INTERRUPT))
		dvisampler0_isr();
	if(irqs & (1 << DVISAMPLER1_INTERRUPT))
		dvisampler1_isr();
}
