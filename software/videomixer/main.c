#include <stdio.h>
#include <stdlib.h>

#include <irq.h>
#include <uart.h>
#include <time.h>
#include <hw/csr.h>
#include <hw/flags.h>
#include <console.h>

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

static void membw_service(void)
{
	static int last_event;
	unsigned long long int nr, nw;
	unsigned long long int f;
	unsigned int rdb, wrb;

	if(elapsed(&last_event, identifier_frequency_read())) {
		lasmicon_bandwidth_update_write(1);
		nr = lasmicon_bandwidth_nreads_read();
		nw = lasmicon_bandwidth_nwrites_read();
		f = identifier_frequency_read();
		rdb = (nr*f >> (24 - 7))/1000000ULL;
		wrb = (nw*f >> (24 - 7))/1000000ULL;
		printf("read:%5dMbps  write:%5dMbps  all:%5dMbps\n", rdb, wrb, rdb + wrb);
	}
}

static void list_video_modes(void)
{
	char mode_descriptors[PROCESSOR_MODE_COUNT*PROCESSOR_MODE_DESCLEN];
	int i;

	processor_list_modes(mode_descriptors);
	for(i=0;i<PROCESSOR_MODE_COUNT;i++)
		printf("%d: %s\n", i, &mode_descriptors[i*PROCESSOR_MODE_DESCLEN]);
}

int main(void)
{
	irq_setmask(0);
	irq_setie(1);
	uart_init();
	
	printf("Mixxeo software rev. %08x built "__DATE__" "__TIME__"\n\n", GIT_ID);
	
	time_init();
	list_video_modes();
	processor_start(0);

	while(1) {
		processor_service();
		ui_service();
		fb_service();
		membw_service();
	}
	
	return 0;
}
