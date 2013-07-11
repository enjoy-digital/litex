#include <stdio.h>
#include <stdlib.h>

#include <irq.h>
#include <uart.h>
#include <time.h>
#include <hw/csr.h>
#include <hw/flags.h>
#include <console.h>

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
		rdb = nr*f >> (24 - 7);
		wrb = nw*f >> (24 - 7);
		printf("read:%4dMbps  write:%4dMbps  all:%4dMbps\n", rdb/1000000, wrb/1000000, (rdb + wrb)/1000000);
	}
}

int main(void)
{
	irq_setmask(0);
	irq_setie(1);
	uart_init();
	
	puts("Memory testing software built "__DATE__" "__TIME__"\n");
	
	time_init();

	while(1) {
		membw_service();
	}
	
	return 0;
}
