#include <stdio.h>

#include "dataflow.h"

void print_isd_info(unsigned int baseaddr)
{
	volatile unsigned int *regs;
	int neps;
	int nbytes;
	int i, j;
	int offset;
	unsigned int ack_count, nack_count, cur_status;
	
	regs = (unsigned int *)baseaddr;
	if((regs[0] != 0x6a) || (regs[1] != 0xb4)) {
		printf("Incorrect magic number\n");
		return;
	}
	neps = regs[2];
	nbytes = (regs[3] + 7)/8;
	
	regs[4] = 1; // freeze
	offset = 6; // regs[5] is reset
	for(i=0;i<neps;i++) {
		ack_count = 0;
		for(j=0;j<nbytes;j++) {
			ack_count <<= 8;
			ack_count |= regs[offset++];
		}
		nack_count = 0;
		for(j=0;j<nbytes;j++) {
			nack_count <<= 8;
			nack_count |= regs[offset++];
		}
		cur_status = regs[offset++];
		printf("#%d: ACK_CNT:%10u   NAK_CNT:%10u %s %s\n",
			i, ack_count, nack_count,
			cur_status & 1 ? "stb" : "   ",
			cur_status & 2 ? "ack" : "   ");
	}
	regs[4] = 0; // unfreeze
}
