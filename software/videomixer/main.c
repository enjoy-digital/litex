#include <stdio.h>
#include <stdlib.h>

#include <irq.h>
#include <uart.h>
#include <hw/csr.h>
#include <hw/flags.h>
#include <console.h>

#include "time.h"
#include "dvisampler0.h"
#include "dvisampler1.h"

static int scale_pot(int raw, int range)
{
	int pot_min = 54000;
	int pot_max = 105400;
	int scaled;

	scaled = range*(raw - pot_min)/(pot_max - pot_min);
	if(scaled < 0)
		scaled = 0;
	if(scaled > range)
		scaled = range;
	return scaled;
}

static void pots_service(void)
{
	static int last_event;
	int blackout;
	int crossfade;

	if(elapsed(&last_event, identifier_frequency_read()/32)) {
		pots_start_busy_write(1);
		while(pots_start_busy_read());
		blackout = scale_pot(pots_res0_read(), 256);
		crossfade = scale_pot(pots_res1_read(), 255);

		fb_blender_f0_write(crossfade*blackout >> 8);
		fb_blender_f1_write((255-crossfade)*blackout >> 8);	
	}
}

static void fb_service(void)
{
	int c;

	if(readchar_nonblock()) {
		c = readchar();
		if(c == '1') {
			fb_enable_write(1);
			printf("Framebuffer is ON\n");
		} else if(c == '0') {
			fb_enable_write(0);
			printf("Framebuffer is OFF\n");
		}
	}
}

int main(void)
{
	irq_setmask(0);
	irq_setie(1);
	uart_init();
	
	puts("Minimal video mixer software built "__DATE__" "__TIME__"\n");
	
	time_init();
	dvisampler0_init_video();
	dvisampler1_init_video();
	fb_enable_write(1);

	while(1) {
		dvisampler0_service();
		dvisampler1_service();
		pots_service();
		fb_service();
	}
	
	return 0;
}
