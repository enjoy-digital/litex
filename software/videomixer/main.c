#include <stdio.h>
#include <stdlib.h>

#include <irq.h>
#include <uart.h>
#include <hw/csr.h>
#include <hw/flags.h>

#include "dvisampler0.h"
#include "dvisampler1.h"

int main(void)
{
	irq_setmask(0);
	irq_setie(1);
	uart_init();
	
	puts("Minimal video mixer software built "__DATE__" "__TIME__"\n");
	
	timer0_reload_write(2*identifier_frequency_read());
	timer0_en_write(1);

	dvisampler0_init_video();
	dvisampler1_init_video();
	fb_enable_write(1);
	fb_blender_f0_write(127);
	fb_blender_f1_write(127);
	while(1) {
		dvisampler0_service();
		dvisampler1_service();
	}
	
	return 0;
}
