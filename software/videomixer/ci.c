#include <stdio.h>

#include <console.h>
#include <generated/csr.h>

#include "config.h"
#include "dvisampler0.h"
#include "dvisampler1.h"
#include "processor.h"
#include "pll.h"
#include "ci.h"

static void print_mem_bandwidth(void)
{
	unsigned long long int nr, nw;
	unsigned long long int f;
	unsigned int rdb, wrb;

	lasmicon_bandwidth_update_write(1);
	nr = lasmicon_bandwidth_nreads_read();
	nw = lasmicon_bandwidth_nwrites_read();
	f = identifier_frequency_read();
	rdb = (nr*f >> (24 - 7))/1000000ULL;
	wrb = (nw*f >> (24 - 7))/1000000ULL;
	printf("read:%5dMbps  write:%5dMbps  all:%5dMbps\n", rdb, wrb, rdb + wrb);
}

static void list_video_modes(void)
{
	char mode_descriptors[PROCESSOR_MODE_COUNT*PROCESSOR_MODE_DESCLEN];
	int i;

	processor_list_modes(mode_descriptors);
	printf("==== Available video modes ====\n");
	for(i=0;i<PROCESSOR_MODE_COUNT;i++)
		printf(" %d: %s\n", i, &mode_descriptors[i*PROCESSOR_MODE_DESCLEN]);
	printf("===============================\n");
}

void ci_service(void)
{
	int c;

	if(readchar_nonblock()) {
		c = readchar();
		if((c >= '0') && (c <= '9')) {
			int m;

			m = c - '0';
			if(m < PROCESSOR_MODE_COUNT) {
				config_set(CONFIG_KEY_RESOLUTION, m);
				processor_start(m);
			}
		}
		switch(c) {
			case 'l':
				list_video_modes();
				break;
			case 'D':
				dvisampler0_debug = dvisampler1_debug = 1;
				printf("DVI sampler debug is ON\n");
				break;
			case 'd':
				dvisampler0_debug = dvisampler1_debug = 0;
				printf("DVI sampler debug is OFF\n");
				break;
			case 'F':
				fb_fi_enable_write(1);
				printf("framebuffer is ON\n");
				break;
			case 'f':
				fb_fi_enable_write(0);
				printf("framebuffer is OFF\n");
				break;
			case 'm':
				print_mem_bandwidth();
				break;
			case 'p':
				pll_dump();
				break;
		}
	}
}
