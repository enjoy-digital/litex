#include <stdio.h>
#include <stdlib.h>

#include <irq.h>
#include <uart.h>
#include <hw/dvisampler.h>

static int d0, d1, d2;

static void print_status(void)
{
	printf("Ph: %4d %4d %4d // %d%d%d [%d %d %d] // %d // %dx%d // %d\n", d0, d1, d2,
		CSR_DVISAMPLER0_D0_CHAR_SYNCED,
		CSR_DVISAMPLER0_D1_CHAR_SYNCED,
		CSR_DVISAMPLER0_D2_CHAR_SYNCED,
		CSR_DVISAMPLER0_D0_CTL_POS,
		CSR_DVISAMPLER0_D1_CTL_POS,
		CSR_DVISAMPLER0_D2_CTL_POS,
		CSR_DVISAMPLER0_CHAN_SYNCED,
		(CSR_DVISAMPLER0_HRESH << 8) | CSR_DVISAMPLER0_HRESL,
		(CSR_DVISAMPLER0_VRESH << 8) | CSR_DVISAMPLER0_VRESL,
		(CSR_DVISAMPLER0_DECNT2 << 16) | (CSR_DVISAMPLER0_DECNT1 << 8) |  CSR_DVISAMPLER0_DECNT0);
}

static void calibrate_delays(void)
{
	CSR_DVISAMPLER0_D0_DELAY_CTL = DVISAMPLER_DELAY_CAL;
	CSR_DVISAMPLER0_D1_DELAY_CTL = DVISAMPLER_DELAY_CAL;
	CSR_DVISAMPLER0_D2_DELAY_CTL = DVISAMPLER_DELAY_CAL;
	while(CSR_DVISAMPLER0_D0_DELAY_BUSY || CSR_DVISAMPLER0_D1_DELAY_BUSY || CSR_DVISAMPLER0_D2_DELAY_BUSY);
	CSR_DVISAMPLER0_D0_DELAY_CTL = DVISAMPLER_DELAY_RST;
	CSR_DVISAMPLER0_D1_DELAY_CTL = DVISAMPLER_DELAY_RST;
	CSR_DVISAMPLER0_D2_DELAY_CTL = DVISAMPLER_DELAY_RST;
	CSR_DVISAMPLER0_D0_PHASE_RESET = 1;
	CSR_DVISAMPLER0_D1_PHASE_RESET = 1;
	CSR_DVISAMPLER0_D2_PHASE_RESET = 1;
	d0 = d1 = d2 = 0;
	printf("Delays calibrated\n");
}

static void adjust_phase(void)
{
	switch(CSR_DVISAMPLER0_D0_PHASE) {
		case DVISAMPLER_TOO_LATE:
			CSR_DVISAMPLER0_D0_DELAY_CTL = DVISAMPLER_DELAY_DEC;
			d0--;
			CSR_DVISAMPLER0_D0_PHASE_RESET = 1;
			break;
		case DVISAMPLER_TOO_EARLY:
			CSR_DVISAMPLER0_D0_DELAY_CTL = DVISAMPLER_DELAY_INC;
			d0++;
			CSR_DVISAMPLER0_D0_PHASE_RESET = 1;
			break;
	}
	switch(CSR_DVISAMPLER0_D1_PHASE) {
		case DVISAMPLER_TOO_LATE:
			CSR_DVISAMPLER0_D1_DELAY_CTL = DVISAMPLER_DELAY_DEC;
			d1--;
			CSR_DVISAMPLER0_D1_PHASE_RESET = 1;
			break;
		case DVISAMPLER_TOO_EARLY:
			CSR_DVISAMPLER0_D1_DELAY_CTL = DVISAMPLER_DELAY_INC;
			d1++;
			CSR_DVISAMPLER0_D1_PHASE_RESET = 1;
			break;
	}
	switch(CSR_DVISAMPLER0_D2_PHASE) {
		case DVISAMPLER_TOO_LATE:
			CSR_DVISAMPLER0_D2_DELAY_CTL = DVISAMPLER_DELAY_DEC;
			d2--;
			CSR_DVISAMPLER0_D2_PHASE_RESET = 1;
			break;
		case DVISAMPLER_TOO_EARLY:
			CSR_DVISAMPLER0_D2_DELAY_CTL = DVISAMPLER_DELAY_INC;
			d2++;
			CSR_DVISAMPLER0_D2_PHASE_RESET = 1;
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
		while(!CSR_DVISAMPLER0_PLL_LOCKED);
		printf("PLL locked\n");
		calibrate_delays();
		if(init_phase())
			printf("Phase init OK\n");
		else
			printf("Phase did not settle\n");
		print_status();

		counter = 0;
		while(CSR_DVISAMPLER0_PLL_LOCKED) {
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
