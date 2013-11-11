#include <stdio.h>
#include <stdlib.h>

#include <irq.h>
#include <uart.h>
#include <time.h>
#include <hw/csr.h>
#include <hw/flags.h>

#include "dvisamplerX.h"

int dvisamplerX_debug;

#define FRAMEBUFFER_COUNT 4
#define FRAMEBUFFER_MASK (FRAMEBUFFER_COUNT - 1)

static unsigned int dvisamplerX_framebuffers[FRAMEBUFFER_COUNT][1280*720] __attribute__((aligned(16)));
static int dvisamplerX_fb_slot_indexes[2];
static int dvisamplerX_next_fb_index;

void dvisamplerX_isr(void)
{
	int fb_index = -1;

	if(dvisamplerX_dma_slot0_status_read() == DVISAMPLER_SLOT_PENDING) {
		fb_index = dvisamplerX_fb_slot_indexes[0];
		dvisamplerX_fb_slot_indexes[0] = dvisamplerX_next_fb_index;
		dvisamplerX_dma_slot0_address_write((unsigned int)dvisamplerX_framebuffers[dvisamplerX_next_fb_index]);
		dvisamplerX_dma_slot0_status_write(DVISAMPLER_SLOT_LOADED);
		dvisamplerX_next_fb_index = (dvisamplerX_next_fb_index + 1) & FRAMEBUFFER_MASK;
	}
	if(dvisamplerX_dma_slot1_status_read() == DVISAMPLER_SLOT_PENDING) {
		fb_index = dvisamplerX_fb_slot_indexes[1];
		dvisamplerX_fb_slot_indexes[1] = dvisamplerX_next_fb_index;
		dvisamplerX_dma_slot1_address_write((unsigned int)dvisamplerX_framebuffers[dvisamplerX_next_fb_index]);
		dvisamplerX_dma_slot1_status_write(DVISAMPLER_SLOT_LOADED);
		dvisamplerX_next_fb_index = (dvisamplerX_next_fb_index + 1) & FRAMEBUFFER_MASK;
	}

	if(fb_index != -1)
		fb_dmaX_base_write((unsigned int)dvisamplerX_framebuffers[fb_index]);
}

static int dvisamplerX_connected;
static int dvisamplerX_locked;

void dvisamplerX_init_video(int hres, int vres)
{
	unsigned int mask;

	dvisamplerX_clocking_pll_reset_write(1);
	dvisamplerX_connected = dvisamplerX_locked = 0;

	dvisamplerX_dma_ev_pending_write(dvisamplerX_dma_ev_pending_read());
	dvisamplerX_dma_ev_enable_write(0x3);
	mask = irq_getmask();
	mask |= 1 << DVISAMPLERX_INTERRUPT;
	irq_setmask(mask);

	dvisamplerX_dma_frame_size_write(hres*vres*4);
	dvisamplerX_fb_slot_indexes[0] = 0;
	dvisamplerX_dma_slot0_address_write((unsigned int)dvisamplerX_framebuffers[0]);
	dvisamplerX_dma_slot0_status_write(DVISAMPLER_SLOT_LOADED);
	dvisamplerX_fb_slot_indexes[1] = 1;
	dvisamplerX_dma_slot1_address_write((unsigned int)dvisamplerX_framebuffers[1]);
	dvisamplerX_dma_slot1_status_write(DVISAMPLER_SLOT_LOADED);
	dvisamplerX_next_fb_index = 2;

	fb_dmaX_base_write((unsigned int)dvisamplerX_framebuffers[3]);
}

static int dvisamplerX_d0, dvisamplerX_d1, dvisamplerX_d2;

void dvisamplerX_print_status(void)
{
	dvisamplerX_data0_wer_update_write(1);
	dvisamplerX_data1_wer_update_write(1);
	dvisamplerX_data2_wer_update_write(1);
	printf("dvisamplerX: ph:%4d %4d %4d // charsync:%d%d%d [%d %d %d] // WER:%3d %3d %3d // chansync:%d // res:%dx%d\n",
		dvisamplerX_d0, dvisamplerX_d1, dvisamplerX_d2,
		dvisamplerX_data0_charsync_char_synced_read(),
		dvisamplerX_data1_charsync_char_synced_read(),
		dvisamplerX_data2_charsync_char_synced_read(),
		dvisamplerX_data0_charsync_ctl_pos_read(),
		dvisamplerX_data1_charsync_ctl_pos_read(),
		dvisamplerX_data2_charsync_ctl_pos_read(),
		dvisamplerX_data0_wer_value_read(),
		dvisamplerX_data1_wer_value_read(),
		dvisamplerX_data2_wer_value_read(),
		dvisamplerX_chansync_channels_synced_read(),
		dvisamplerX_resdetection_hres_read(),
		dvisamplerX_resdetection_vres_read());
}

static int wait_idelays(void)
{
	int ev;

	ev = 0;
	elapsed(&ev, 1);
	while(dvisamplerX_data0_cap_dly_busy_read()
	  || dvisamplerX_data1_cap_dly_busy_read()
	  || dvisamplerX_data2_cap_dly_busy_read()) {
		if(elapsed(&ev, identifier_frequency_read() >> 6) == 0) {
			printf("dvisamplerX: IDELAY busy timeout\n");
			return 0;
		}
	}
	return 1;
}

int dvisamplerX_calibrate_delays(void)
{
	dvisamplerX_data0_cap_dly_ctl_write(DVISAMPLER_DELAY_MASTER_CAL|DVISAMPLER_DELAY_SLAVE_CAL);
	dvisamplerX_data1_cap_dly_ctl_write(DVISAMPLER_DELAY_MASTER_CAL|DVISAMPLER_DELAY_SLAVE_CAL);
	dvisamplerX_data2_cap_dly_ctl_write(DVISAMPLER_DELAY_MASTER_CAL|DVISAMPLER_DELAY_SLAVE_CAL);
	if(!wait_idelays())
		return 0;
	dvisamplerX_data0_cap_dly_ctl_write(DVISAMPLER_DELAY_MASTER_RST|DVISAMPLER_DELAY_SLAVE_RST);
	dvisamplerX_data1_cap_dly_ctl_write(DVISAMPLER_DELAY_MASTER_RST|DVISAMPLER_DELAY_SLAVE_RST);
	dvisamplerX_data2_cap_dly_ctl_write(DVISAMPLER_DELAY_MASTER_RST|DVISAMPLER_DELAY_SLAVE_RST);
	dvisamplerX_data0_cap_phase_reset_write(1);
	dvisamplerX_data1_cap_phase_reset_write(1);
	dvisamplerX_data2_cap_phase_reset_write(1);
	dvisamplerX_d0 = dvisamplerX_d1 = dvisamplerX_d2 = 0;
	return 1;
}

int dvisamplerX_adjust_phase(void)
{
	switch(dvisamplerX_data0_cap_phase_read()) {
		case DVISAMPLER_TOO_LATE:
			dvisamplerX_data0_cap_dly_ctl_write(DVISAMPLER_DELAY_DEC);
			if(!wait_idelays())
				return 0;
			dvisamplerX_d0--;
			dvisamplerX_data0_cap_phase_reset_write(1);
			break;
		case DVISAMPLER_TOO_EARLY:
			dvisamplerX_data0_cap_dly_ctl_write(DVISAMPLER_DELAY_INC);
			if(!wait_idelays())
				return 0;
			dvisamplerX_d0++;
			dvisamplerX_data0_cap_phase_reset_write(1);
			break;
	}
	switch(dvisamplerX_data1_cap_phase_read()) {
		case DVISAMPLER_TOO_LATE:
			dvisamplerX_data1_cap_dly_ctl_write(DVISAMPLER_DELAY_DEC);
			if(!wait_idelays())
				return 0;
			dvisamplerX_d1--;
			dvisamplerX_data1_cap_phase_reset_write(1);
			break;
		case DVISAMPLER_TOO_EARLY:
			dvisamplerX_data1_cap_dly_ctl_write(DVISAMPLER_DELAY_INC);
			if(!wait_idelays())
				return 0;
			dvisamplerX_d1++;
			dvisamplerX_data1_cap_phase_reset_write(1);
			break;
	}
	switch(dvisamplerX_data2_cap_phase_read()) {
		case DVISAMPLER_TOO_LATE:
			dvisamplerX_data2_cap_dly_ctl_write(DVISAMPLER_DELAY_DEC);
			if(!wait_idelays())
				return 0;
			dvisamplerX_d2--;
			dvisamplerX_data2_cap_phase_reset_write(1);
			break;
		case DVISAMPLER_TOO_EARLY:
			dvisamplerX_data2_cap_dly_ctl_write(DVISAMPLER_DELAY_INC);
			if(!wait_idelays())
				return 0;
			dvisamplerX_d2++;
			dvisamplerX_data2_cap_phase_reset_write(1);
			break;
	}
	return 1;
}

int dvisamplerX_init_phase(void)
{
	int o_d0, o_d1, o_d2; 
	int i, j;

	for(i=0;i<100;i++) {
		o_d0 = dvisamplerX_d0;
		o_d1 = dvisamplerX_d1;
		o_d2 = dvisamplerX_d2;
		for(j=0;j<1000;j++) {
			if(!dvisamplerX_adjust_phase())
				return 0;
		}
		if((abs(dvisamplerX_d0 - o_d0) < 4) && (abs(dvisamplerX_d1 - o_d1) < 4) && (abs(dvisamplerX_d2 - o_d2) < 4))
			return 1;
	}
	return 0;
}

int dvisamplerX_phase_startup(void)
{
	int ret;
	int attempts;

	attempts = 0;
	while(1) {
		attempts++;
		dvisamplerX_calibrate_delays();
		if(dvisamplerX_debug)
			printf("dvisamplerX: delays calibrated\n");
		ret = dvisamplerX_init_phase();
		if(ret) {
			if(dvisamplerX_debug)
				printf("dvisamplerX: phase init OK\n");
			return 1;
		} else {
			printf("dvisamplerX: phase init failed\n");
			if(attempts > 3) {
				printf("dvisamplerX: giving up\n");
				dvisamplerX_calibrate_delays();
				return 0;
			}
		}
	}
}

static void dvisamplerX_check_overflow(void)
{
	if(dvisamplerX_frame_overflow_read()) {
		printf("dvisamplerX: FIFO overflow\n");
		dvisamplerX_frame_overflow_write(1);
	}
}

static int dvisamplerX_last_event;

void dvisamplerX_service(void)
{
	if(dvisamplerX_connected) {
		if(!dvisamplerX_edid_hpd_notif_read()) {
			if(dvisamplerX_debug)
				printf("dvisamplerX: disconnected\n");
			dvisamplerX_connected = 0;
			dvisamplerX_locked = 0;
			dvisamplerX_clocking_pll_reset_write(1);
		} else {
			if(dvisamplerX_locked) {
				if(dvisamplerX_clocking_locked_read()) {
					if(elapsed(&dvisamplerX_last_event, identifier_frequency_read()/2)) {
						dvisamplerX_adjust_phase();
						if(dvisamplerX_debug)
							dvisamplerX_print_status();
					}
				} else {
					if(dvisamplerX_debug)
						printf("dvisamplerX: lost PLL lock\n");
					dvisamplerX_locked = 0;
				}
			} else {
				if(dvisamplerX_clocking_locked_read()) {
					if(dvisamplerX_debug)
						printf("dvisamplerX: PLL locked\n");
					dvisamplerX_phase_startup();
					if(dvisamplerX_debug)
						dvisamplerX_print_status();
					dvisamplerX_locked = 1;
				}
			}
		}
	} else {
		if(dvisamplerX_edid_hpd_notif_read()) {
			if(dvisamplerX_debug)
				printf("dvisamplerX: connected\n");
			dvisamplerX_connected = 1;
			dvisamplerX_clocking_pll_reset_write(0);
		}
	}
	dvisamplerX_check_overflow();
}
