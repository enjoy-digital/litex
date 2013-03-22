#include <stdio.h>

#include <irq.h>
#include <uart.h>
#include <hw/dvisampler.h>

static int d0, d1, d2;

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
	printf("Ph: %4d %4d %4d // %d%d%d // %d\n", d0, d1, d2,
		CSR_DVISAMPLER0_D0_CHAR_SYNCED,
		CSR_DVISAMPLER0_D1_CHAR_SYNCED,
		CSR_DVISAMPLER0_D2_CHAR_SYNCED,
		CSR_DVISAMPLER0_CHAN_SYNCED);
}

static void vmix(void)
{
	unsigned int counter;

	while(1) {
		while(!CSR_DVISAMPLER0_PLL_LOCKED);
		printf("PLL locked\n");
		calibrate_delays();
		adjust_phase();

		counter = 0;
		while(CSR_DVISAMPLER0_PLL_LOCKED) {
			counter++;
			if(counter == 200000) {
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
	
	vmix();
	
	return 0;
}
