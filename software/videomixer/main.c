#include <stdio.h>
#include <stdlib.h>

#include <irq.h>
#include <uart.h>
#include <time.h>
#include <generated/csr.h>
#include <hw/flags.h>
#include <console.h>

#include "config.h"
#include "ci.h"
#include "processor.h"

#ifdef POTS_BASE
static int scale_pot(int raw, int range)
{
	int pot_min = 64000;
	int pot_max = 103000;
	int scaled;

	scaled = range*(raw - pot_min)/(pot_max - pot_min);
	if(scaled < 0)
		scaled = 0;
	if(scaled > range)
		scaled = range;
	return scaled;
}

static void regular_blend(int p0, int p1)
{
	int blackout;
	int crossfade;

	blackout = scale_pot(p0, 256);
	crossfade = scale_pot(p1, 255);

	fb_blender_f0_write(crossfade*blackout >> 8);
	fb_blender_f1_write((255-crossfade)*blackout >> 8);	
}

static void additive_blend(int p0, int p1)
{
	fb_blender_f0_write(scale_pot(p0, 255));
	fb_blender_f1_write(scale_pot(p1, 255));
}

static void ui_service(void)
{
	static int last_event;
	static int additive_blend_enabled;
	static int old_btn;
	int btn;
	int p0, p1;

	if(elapsed(&last_event, identifier_frequency_read()/32)) {
		btn = buttons_in_read() & 0x1;
		if(btn && !old_btn) {
			additive_blend_enabled = !additive_blend_enabled;
			if(additive_blend_enabled)
				leds_out_write(leds_out_read() | 0x1);
			else
				leds_out_write(leds_out_read() & ~0x1);
		}
		old_btn = btn;

		pots_start_busy_write(1);
		while(pots_start_busy_read());
		p0 = pots_res0_read();
		p1 = pots_res1_read();
		if(!additive_blend_enabled)
			regular_blend(p0, p1);
		else
			additive_blend(p0, p1);
	}
}

#else

static void ui_service(void)
{
	fb_blender_f0_write(0xff);
	fb_blender_f1_write(0xff);
}

#endif

int main(void)
{
	irq_setmask(0);
	irq_setie(1);
	uart_init();
	
	printf("Mixxeo software rev. %08x built "__DATE__" "__TIME__"\n\n", GIT_ID);
	
	config_init();
	time_init();
	processor_start(config_get(CONFIG_KEY_RESOLUTION));

	while(1) {
		processor_service();
		ui_service();
		ci_service();
	}
	
	return 0;
}
