#include <stdio.h>
#include <stdlib.h>

#include <irq.h>
#include <uart.h>
#include <hw/csr.h>
#include <hw/flags.h>

static int d0, d1, d2;

static void print_status(void)
{
	printf("Ph: %4d %4d %4d // %d%d%d [%d %d %d] // %d // %dx%d // %d\n", d0, d1, d2,
		dvisampler0_data0_charsync_char_synced_read(),
		dvisampler0_data1_charsync_char_synced_read(),
		dvisampler0_data2_charsync_char_synced_read(),
		dvisampler0_data0_charsync_ctl_pos_read(),
		dvisampler0_data1_charsync_ctl_pos_read(),
		dvisampler0_data2_charsync_ctl_pos_read(),
		dvisampler0_chansync_channels_synced_read(),
		dvisampler0_resdetection_hres_read(),
		dvisampler0_resdetection_vres_read(),
		dvisampler0_resdetection_de_cycles_read());
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
	d0 = d1 = d2 = 0;
	printf("Delays calibrated\n");
}

static void adjust_phase(void)
{
	switch(dvisampler0_data0_cap_phase_read()) {
		case DVISAMPLER_TOO_LATE:
			dvisampler0_data0_cap_dly_ctl_write(DVISAMPLER_DELAY_DEC);
			d0--;
			dvisampler0_data0_cap_phase_reset_write(1);
			break;
		case DVISAMPLER_TOO_EARLY:
			dvisampler0_data0_cap_dly_ctl_write(DVISAMPLER_DELAY_INC);
			d0++;
			dvisampler0_data0_cap_phase_reset_write(1);
			break;
	}
	switch(dvisampler0_data1_cap_phase_read()) {
		case DVISAMPLER_TOO_LATE:
			dvisampler0_data1_cap_dly_ctl_write(DVISAMPLER_DELAY_DEC);
			d1--;
			dvisampler0_data1_cap_phase_reset_write(1);
			break;
		case DVISAMPLER_TOO_EARLY:
			dvisampler0_data1_cap_dly_ctl_write(DVISAMPLER_DELAY_INC);
			d1++;
			dvisampler0_data1_cap_phase_reset_write(1);
			break;
	}
	switch(dvisampler0_data2_cap_phase_read()) {
		case DVISAMPLER_TOO_LATE:
			dvisampler0_data2_cap_dly_ctl_write(DVISAMPLER_DELAY_DEC);
			d2--;
			dvisampler0_data2_cap_phase_reset_write(1);
			break;
		case DVISAMPLER_TOO_EARLY:
			dvisampler0_data2_cap_dly_ctl_write(DVISAMPLER_DELAY_INC);
			d2++;
			dvisampler0_data2_cap_phase_reset_write(1);
			break;
	}
}

static int init_phase(void)
{
	int od0, od1, od2; 
	int i, j;

	for(i=0;i<100;i++) {
		od0 = d0;
		od1 = d1;
		od2 = d2;
		for(j=0;j<1000;j++)
			adjust_phase();
		if((abs(d0 - od0) < 4) && (abs(d1 - od1) < 4) && (abs(d2 - od2) < 4))
			return 1;
	}
	return 0;
}

static void vmix(void)
{
	int i;
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
				//adjust_phase();
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
	
	vmix();
	
	return 0;
}
