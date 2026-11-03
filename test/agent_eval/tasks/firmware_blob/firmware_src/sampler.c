// Sampler firmware of the firmware_blob task (hidden from the agent, shipped prebuilt as
// workspace/firmware/sampler.bin). Built against the reference SoC (ADC channel field at bits 9:8)
// by make_firmware.py.

#include <stdio.h>

#include <irq.h>
#include <libbase/uart.h>
#include <generated/csr.h>

#define ADC_CHANNELS 4

static unsigned int adc_read(int channel)
{
	adc_control_write((channel << CSR_ADC_CONTROL_CHANNEL_OFFSET) |
	                  (1 << CSR_ADC_CONTROL_START_OFFSET));
	while (!(adc_status_read() & (1 << CSR_ADC_STATUS_DONE_OFFSET)));
	return adc_data_read();
}

static void delay(int n)
{
	for (volatile int i = 0; i < n; i++);
}

int main(void)
{
	unsigned int values[ADC_CHANNELS];
	unsigned int pass;
	int i, j, ok;

#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(1);
#endif
	uart_init();

	printf("\nsampler v2.3\n");
	for (pass = 0;; pass++) {
		for (i = 0; i < ADC_CHANNELS; i++)
			values[i] = adc_read(i);
		ok = 1;
		for (i = 0; i < ADC_CHANNELS; i++)
			for (j = i + 1; j < ADC_CHANNELS; j++)
				if (values[i] == values[j])
					ok = 0;
		printf("pass %u: ch0=0x%03x ch1=0x%03x ch2=0x%03x ch3=0x%03x channel check: %s\n",
			pass, values[0], values[1], values[2], values[3], ok ? "OK" : "FAIL");
		delay(2000);
	}
	return 0;
}
