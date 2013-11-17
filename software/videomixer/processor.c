#include <stdio.h>
#include <stdlib.h>

#include <hw/csr.h>
#include <hw/flags.h>

#include "dvisampler0.h"
#include "dvisampler1.h"
#include "edid.h"
#include "processor.h"

/* reference: http://martin.hinner.info/vga/timing.html */
static const struct video_timing video_modes[PROCESSOR_MODE_COUNT] = {
	{
		.pixel_clock = 3150,

		.h_active = 640,
		.h_blanking = 192,
		.h_sync_offset = 24,
		.h_sync_width = 40,

		.v_active = 480,
		.v_blanking = 40,
		.v_sync_offset = 9,
		.v_sync_width = 3,

		.established_timing = 0x0800
	},
	{
		.pixel_clock = 3150,

		.h_active = 640,
		.h_blanking = 200,
		.h_sync_offset = 16,
		.h_sync_width = 64,

		.v_active = 480,
		.v_blanking = 20,
		.v_sync_offset = 1,
		.v_sync_width = 3,

		.established_timing = 0x0400
	},
	{
		.pixel_clock = 3600,

		.h_active = 800,
		.h_blanking = 224,
		.h_sync_offset = 24,
		.h_sync_width = 72,

		.v_active = 600,
		.v_blanking = 25,
		.v_sync_offset = 1,
		.v_sync_width = 2,

		.established_timing = 0x0200
	},
	{
		.pixel_clock = 4000,

		.h_active = 800,
		.h_blanking = 256,
		.h_sync_offset = 40,
		.h_sync_width = 128,

		.v_active = 600,
		.v_blanking = 28,
		.v_sync_offset = 1,
		.v_sync_width = 4,

		.established_timing = 0x0100
	},
	{
		.pixel_clock = 5000,

		.h_active = 800,
		.h_blanking = 240,
		.h_sync_offset = 56,
		.h_sync_width = 120,

		.v_active = 600,
		.v_blanking = 66,
		.v_sync_offset = 37,
		.v_sync_width = 6,

		.established_timing = 0x0080
	},
	{
		.pixel_clock = 4950,

		.h_active = 800,
		.h_blanking = 256,
		.h_sync_offset = 16,
		.h_sync_width = 80,

		.v_active = 600,
		.v_blanking = 25,
		.v_sync_offset = 1,
		.v_sync_width = 3,

		.established_timing = 0x0040
	},
	{
		.pixel_clock = 6500,

		.h_active = 1024,
		.h_blanking = 320,
		.h_sync_offset = 24,
		.h_sync_width = 136,

		.v_active = 768,
		.v_blanking = 38,
		.v_sync_offset = 3,
		.v_sync_width = 6,

		.established_timing = 0x0008
	},
	{
		.pixel_clock = 7500,

		.h_active = 1024,
		.h_blanking = 304,
		.h_sync_offset = 24,
		.h_sync_width = 136,

		.v_active = 768,
		.v_blanking = 38,
		.v_sync_offset = 3,
		.v_sync_width = 6,

		.established_timing = 0x0004
	},
	{
		.pixel_clock = 7880,

		.h_active = 1024,
		.h_blanking = 288,
		.h_sync_offset = 16,
		.h_sync_width = 96,

		.v_active = 768,
		.v_blanking = 32,
		.v_sync_offset = 1,
		.v_sync_width = 3,

		.established_timing = 0x0002
	},
	{
		.pixel_clock = 7425,

		.h_active = 1280,
		.h_blanking = 370,
		.h_sync_offset = 220,
		.h_sync_width = 40,

		.v_active = 720,
		.v_blanking = 30,
		.v_sync_offset = 20,
		.v_sync_width = 5
	}
};

void processor_list_modes(char *mode_descriptors)
{
	int i;
	unsigned int refresh_span;
	unsigned int refresh_rate;

	for(i=0;i<PROCESSOR_MODE_COUNT;i++) {
		refresh_span = (video_modes[i].h_active + video_modes[i].h_blanking)*(video_modes[i].v_active + video_modes[i].v_blanking);
		refresh_rate = video_modes[i].pixel_clock*10000/refresh_span;
		sprintf(&mode_descriptors[PROCESSOR_MODE_DESCLEN*i],
			"%ux%u @%uHz", video_modes[i].h_active, video_modes[i].v_active, refresh_rate);
	}
}

static void fb_clkgen_write(int cmd, int data)
{
	int word;

	word = (data << 2) | cmd;
	fb_driver_clocking_cmd_data_write(word);
	fb_driver_clocking_send_cmd_data_write(1);
	while(fb_driver_clocking_status_read() & CLKGEN_STATUS_BUSY);
}

static void fb_get_clock_md(unsigned int pixel_clock, unsigned int *best_m, unsigned int *best_d)
{
	unsigned int ideal_m, ideal_d;
	unsigned int bm, bd;
	unsigned int m, d;
	unsigned int diff_current;
	unsigned int diff_tested;

	ideal_m = pixel_clock;
	ideal_d = 5000;

	bm = 1;
	bd = 0;
	for(d=1;d<=256;d++)
		for(m=2;m<=256;m++) {
			/* common denominator is d*bd*ideal_d */
			diff_current = abs(d*ideal_d*bm - d*bd*ideal_m);
			diff_tested = abs(bd*ideal_d*m - d*bd*ideal_m);
			if(diff_tested < diff_current) {
				bm = m;
				bd = d;
			}
		}
	*best_m = bm;
	*best_d = bd;
}

static void fb_set_mode(const struct video_timing *mode)
{
	unsigned int clock_m, clock_d;

	fb_get_clock_md(mode->pixel_clock, &clock_m, &clock_d);

	fb_fi_hres_write(mode->h_active);
	fb_fi_hsync_start_write(mode->h_active + mode->h_sync_offset);
	fb_fi_hsync_end_write(mode->h_active + mode->h_sync_offset + mode->h_sync_width);
	fb_fi_hscan_write(mode->h_active + mode->h_blanking);
	fb_fi_vres_write(mode->v_active);
	fb_fi_vsync_start_write(mode->v_active + mode->v_sync_offset);
	fb_fi_vsync_end_write(mode->v_active + mode->v_sync_offset + mode->v_sync_width);
	fb_fi_vscan_write(mode->v_active + mode->v_blanking);
	
	fb_dma0_length_write(mode->h_active*mode->v_active*4);
	fb_dma1_length_write(mode->h_active*mode->v_active*4);

	fb_clkgen_write(0x1, clock_d-1);
	fb_clkgen_write(0x3, clock_m-1);
	fb_driver_clocking_send_go_write(1);
	while(!(fb_driver_clocking_status_read() & CLKGEN_STATUS_PROGDONE));
	while(!(fb_driver_clocking_status_read() & CLKGEN_STATUS_LOCKED));
}

static void edid_set_mode(const struct video_timing *mode)
{
	unsigned char edid[128];
	int i;

	generate_edid(&edid, "OHW", "MX", 2013, "Mixxeo ch.A", mode);
	for(i=0;i<sizeof(edid);i++)
		MMPTR(DVISAMPLER0_EDID_MEM_BASE+4*i) = edid[i];
	generate_edid(&edid, "OHW", "MX", 2013, "Mixxeo ch.B", mode);
	for(i=0;i<sizeof(edid);i++)
		MMPTR(DVISAMPLER1_EDID_MEM_BASE+4*i) = edid[i];
}

void processor_start(int mode)
{
	const struct video_timing *m = &video_modes[mode];

	fb_enable_write(0);
	dvisampler0_edid_hpd_en_write(0);
	dvisampler1_edid_hpd_en_write(0);

	dvisampler0_disable();
	dvisampler1_disable();
	dvisampler0_clear_framebuffers();
	dvisampler1_clear_framebuffers();

	fb_set_mode(m);
	edid_set_mode(m);
	dvisampler0_init_video(m->h_active, m->v_active);
	dvisampler1_init_video(m->h_active, m->v_active);

	fb_enable_write(1);
	dvisampler0_edid_hpd_en_write(1);
	dvisampler1_edid_hpd_en_write(1);
}

void processor_service(void)
{
	dvisampler0_service();
	dvisampler1_service();
}
