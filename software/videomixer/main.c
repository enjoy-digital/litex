#include <stdio.h>
#include <stdlib.h>

#include <irq.h>
#include <uart.h>
#include <console.h>
#include <hw/csr.h>
#include <hw/flags.h>

static int dvisampler0_d0, dvisampler0_d1, dvisampler0_d2;

static void print_status(void)
{
	printf("dvisampler0 ph: %4d %4d %4d // %d%d%d [%d %d %d] // %d // %dx%d\n", dvisampler0_d0, dvisampler0_d1, dvisampler0_d2,
		dvisampler0_data0_charsync_char_synced_read(),
		dvisampler0_data1_charsync_char_synced_read(),
		dvisampler0_data2_charsync_char_synced_read(),
		dvisampler0_data0_charsync_ctl_pos_read(),
		dvisampler0_data1_charsync_ctl_pos_read(),
		dvisampler0_data2_charsync_ctl_pos_read(),
		dvisampler0_chansync_channels_synced_read(),
		dvisampler0_resdetection_hres_read(),
		dvisampler0_resdetection_vres_read());
}

static void calibrate_delays(void)
{
	dvisampler0_data0_cap_dly_ctl_write(DVISAMPLER_DELAY_CAL);
	dvisampler0_data1_cap_dly_ctl_write(DVISAMPLER_DELAY_CAL);
	dvisampler0_data2_cap_dly_ctl_write(DVISAMPLER_DELAY_CAL);
	while(dvisampler0_data0_cap_dly_busy_read()
		|| dvisampler0_data1_cap_dly_busy_read()
		|| dvisampler0_data2_cap_dly_busy_read());
	dvisampler0_data0_cap_dly_ctl_write(DVISAMPLER_DELAY_RST);
	dvisampler0_data1_cap_dly_ctl_write(DVISAMPLER_DELAY_RST);
	dvisampler0_data2_cap_dly_ctl_write(DVISAMPLER_DELAY_RST);
	dvisampler0_data0_cap_phase_reset_write(1);
	dvisampler0_data1_cap_phase_reset_write(1);
	dvisampler0_data2_cap_phase_reset_write(1);
	dvisampler0_d0 = dvisampler0_d1 = dvisampler0_d2 = 0;
	printf("Delays calibrated\n");
}

static void adjust_phase(void)
{
	switch(dvisampler0_data0_cap_phase_read()) {
		case DVISAMPLER_TOO_LATE:
			dvisampler0_data0_cap_dly_ctl_write(DVISAMPLER_DELAY_DEC);
			dvisampler0_d0--;
			dvisampler0_data0_cap_phase_reset_write(1);
			break;
		case DVISAMPLER_TOO_EARLY:
			dvisampler0_data0_cap_dly_ctl_write(DVISAMPLER_DELAY_INC);
			dvisampler0_d0++;
			dvisampler0_data0_cap_phase_reset_write(1);
			break;
	}
	switch(dvisampler0_data1_cap_phase_read()) {
		case DVISAMPLER_TOO_LATE:
			dvisampler0_data1_cap_dly_ctl_write(DVISAMPLER_DELAY_DEC);
			dvisampler0_d1--;
			dvisampler0_data1_cap_phase_reset_write(1);
			break;
		case DVISAMPLER_TOO_EARLY:
			dvisampler0_data1_cap_dly_ctl_write(DVISAMPLER_DELAY_INC);
			dvisampler0_d1++;
			dvisampler0_data1_cap_phase_reset_write(1);
			break;
	}
	switch(dvisampler0_data2_cap_phase_read()) {
		case DVISAMPLER_TOO_LATE:
			dvisampler0_data2_cap_dly_ctl_write(DVISAMPLER_DELAY_DEC);
			dvisampler0_d2--;
			dvisampler0_data2_cap_phase_reset_write(1);
			break;
		case DVISAMPLER_TOO_EARLY:
			dvisampler0_data2_cap_dly_ctl_write(DVISAMPLER_DELAY_INC);
			dvisampler0_d2++;
			dvisampler0_data2_cap_phase_reset_write(1);
			break;
	}
}

static int init_phase(void)
{
	int o_d0, o_d1, o_d2; 
	int i, j;

	for(i=0;i<100;i++) {
		o_d0 = dvisampler0_d0;
		o_d1 = dvisampler0_d1;
		o_d2 = dvisampler0_d2;
		for(j=0;j<1000;j++)
			adjust_phase();
		if((abs(dvisampler0_d0 - o_d0) < 4) && (abs(dvisampler0_d1 - o_d1) < 4) && (abs(dvisampler0_d2 - o_d2) < 4))
			return 1;
	}
	return 0;
}

#define FRAMEBUFFER_COUNT 4
#define FRAMEBUFFER_MASK (FRAMEBUFFER_COUNT - 1)

static unsigned int dvisampler0_framebuffers[FRAMEBUFFER_COUNT][640*480] __attribute__((aligned(16)));
static int dvisampler0_fb_slot_indexes[2];
static int dvisampler0_next_fb_index;

static void dvisampler0_init_video(void)
{
	unsigned int mask;

	dvisampler0_dma_ev_pending_write(dvisampler0_dma_ev_pending_read());
	dvisampler0_dma_ev_enable_write(0x3);
	mask = irq_getmask();
	mask |= 1 << DVISAMPLER0_INTERRUPT;
	irq_setmask(mask);

	dvisampler0_dma_frame_size_write(sizeof(dvisampler0_framebuffers[0]));
	dvisampler0_fb_slot_indexes[0] = 0;
	dvisampler0_dma_slot0_address_write((unsigned int)dvisampler0_framebuffers[0]);
	dvisampler0_dma_slot0_status_write(DVISAMPLER_SLOT_LOADED);
	dvisampler0_fb_slot_indexes[1] = 1;
	dvisampler0_dma_slot1_address_write((unsigned int)dvisampler0_framebuffers[1]);
	dvisampler0_dma_slot1_status_write(DVISAMPLER_SLOT_LOADED);
	dvisampler0_next_fb_index = 2;

	fb_base_write((unsigned int)dvisampler0_framebuffers[0]);
}

void dvisampler0_isr(void)
{
	int fb_index = -1;

	if(dvisampler0_dma_slot0_status_read() == DVISAMPLER_SLOT_PENDING) {
		fb_index = dvisampler0_fb_slot_indexes[0];
		dvisampler0_fb_slot_indexes[0] = dvisampler0_next_fb_index;
		dvisampler0_dma_slot0_address_write((unsigned int)dvisampler0_framebuffers[dvisampler0_next_fb_index]);
		dvisampler0_dma_slot0_status_write(DVISAMPLER_SLOT_LOADED);
		dvisampler0_next_fb_index = (dvisampler0_next_fb_index + 1) & FRAMEBUFFER_MASK;
	}
	if(dvisampler0_dma_slot1_status_read() == DVISAMPLER_SLOT_PENDING) {
		fb_index = dvisampler0_fb_slot_indexes[1];
		dvisampler0_fb_slot_indexes[1] = dvisampler0_next_fb_index;
		dvisampler0_dma_slot1_address_write((unsigned int)dvisampler0_framebuffers[dvisampler0_next_fb_index]);
		dvisampler0_dma_slot1_status_write(DVISAMPLER_SLOT_LOADED);
		dvisampler0_next_fb_index = (dvisampler0_next_fb_index + 1) & FRAMEBUFFER_MASK;
	}

	if(fb_index != -1)
		fb_base_write((unsigned int)dvisampler0_framebuffers[fb_index]);
}

static void vmix(void)
{
	unsigned int counter;

	while(1) {
		while(!dvisampler0_clocking_locked_read());
		printf("PLL locked\n");
		calibrate_delays();
		if(init_phase())
			printf("Phase init OK\n");
		else
			printf("Phase did not settle\n");
		print_status();

		counter = 0;
		while(dvisampler0_clocking_locked_read()) {
			counter++;
			if(counter == 2000000) {
				print_status();
				adjust_phase();
				counter = 0;
			}
		}
		printf("PLL unlocked\n");
	}
}

int main(void)
{
	irq_setmask(0);
	irq_setie(1);
	uart_init();
	
	puts("Minimal video mixer software built "__DATE__" "__TIME__"\n");
	
	dvisampler0_init_video();
	fb_enable_write(1);
	vmix();
	
	return 0;
}
