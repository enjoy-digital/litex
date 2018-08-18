#include <generated/csr.h>
#ifdef CSR_SDRAM_BASE

#include <stdio.h>
#include <stdlib.h>

#include <generated/sdram_phy.h>
#include <generated/mem.h>
#include <hw/flags.h>
#include <system.h>

#include "sdram.h"

static void cdelay(int i)
{
	while(i > 0) {
#if defined (__lm32__)
		__asm__ volatile("nop");
#elif defined (__or1k__)
		__asm__ volatile("l.nop");
#elif defined (__picorv32__)
		__asm__ volatile("nop");
#elif defined (__vexriscv__)
		__asm__ volatile("nop");
#else
#error Unsupported architecture
#endif
		i--;
	}
}

void sdrsw(void)
{
	sdram_dfii_control_write(DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
	printf("SDRAM now under software control\n");
}

void sdrhw(void)
{
	sdram_dfii_control_write(DFII_CONTROL_SEL);
	printf("SDRAM now under hardware control\n");
}

void sdrrow(char *_row)
{
	char *c;
	unsigned int row;

	if(*_row == 0) {
		sdram_dfii_pi0_address_write(0x0000);
		sdram_dfii_pi0_baddress_write(0);
		command_p0(DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
		cdelay(15);
		printf("Precharged\n");
	} else {
		row = strtoul(_row, &c, 0);
		if(*c != 0) {
			printf("incorrect row\n");
			return;
		}
		sdram_dfii_pi0_address_write(row);
		sdram_dfii_pi0_baddress_write(0);
		command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CS);
		cdelay(15);
		printf("Activated row %d\n", row);
	}
}

void sdrrdbuf(int dq)
{
	int i, p;
	int first_byte, step;

	if(dq < 0) {
		first_byte = 0;
		step = 1;
	} else {
		first_byte = DFII_PIX_DATA_SIZE/2 - 1 - dq;
		step = DFII_PIX_DATA_SIZE/2;
	}

	for(p=0;p<DFII_NPHASES;p++)
		for(i=first_byte;i<DFII_PIX_DATA_SIZE;i+=step)
			printf("%02x", MMPTR(sdram_dfii_pix_rddata_addr[p]+4*i));
	printf("\n");
}

void sdrrd(char *startaddr, char *dq)
{
	char *c;
	unsigned int addr;
	int _dq;

	if(*startaddr == 0) {
		printf("sdrrd <address>\n");
		return;
	}
	addr = strtoul(startaddr, &c, 0);
	if(*c != 0) {
		printf("incorrect address\n");
		return;
	}
	if(*dq == 0)
		_dq = -1;
	else {
		_dq = strtoul(dq, &c, 0);
		if(*c != 0) {
			printf("incorrect DQ\n");
			return;
		}
	}

	sdram_dfii_pird_address_write(addr);
	sdram_dfii_pird_baddress_write(0);
	command_prd(DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA);
	cdelay(15);
	sdrrdbuf(_dq);
}

void sdrrderr(char *count)
{
	int addr;
	char *c;
	int _count;
	int i, j, p;
	unsigned char prev_data[DFII_NPHASES*DFII_PIX_DATA_SIZE];
	unsigned char errs[DFII_NPHASES*DFII_PIX_DATA_SIZE];

	if(*count == 0) {
		printf("sdrrderr <count>\n");
		return;
	}
	_count = strtoul(count, &c, 0);
	if(*c != 0) {
		printf("incorrect count\n");
		return;
	}

	for(i=0;i<DFII_NPHASES*DFII_PIX_DATA_SIZE;i++)
			errs[i] = 0;
	for(addr=0;addr<16;addr++) {
		sdram_dfii_pird_address_write(addr*8);
		sdram_dfii_pird_baddress_write(0);
		command_prd(DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA);
		cdelay(15);
		for(p=0;p<DFII_NPHASES;p++)
			for(i=0;i<DFII_PIX_DATA_SIZE;i++)
				prev_data[p*DFII_PIX_DATA_SIZE+i] = MMPTR(sdram_dfii_pix_rddata_addr[p]+4*i);

		for(j=0;j<_count;j++) {
			command_prd(DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA);
			cdelay(15);
			for(p=0;p<DFII_NPHASES;p++)
				for(i=0;i<DFII_PIX_DATA_SIZE;i++) {
					unsigned char new_data;

					new_data = MMPTR(sdram_dfii_pix_rddata_addr[p]+4*i);
					errs[p*DFII_PIX_DATA_SIZE+i] |= prev_data[p*DFII_PIX_DATA_SIZE+i] ^ new_data;
					prev_data[p*DFII_PIX_DATA_SIZE+i] = new_data;
				}
		}
	}

	for(i=0;i<DFII_NPHASES*DFII_PIX_DATA_SIZE;i++)
		printf("%02x", errs[i]);
	printf("\n");
	for(p=0;p<DFII_NPHASES;p++)
		for(i=0;i<DFII_PIX_DATA_SIZE;i++)
			printf("%2x", DFII_PIX_DATA_SIZE/2 - 1 - (i % (DFII_PIX_DATA_SIZE/2)));
	printf("\n");
}

void sdrwr(char *startaddr)
{
	char *c;
	unsigned int addr;
	int i;
	int p;

	if(*startaddr == 0) {
		printf("sdrrd <address>\n");
		return;
	}
	addr = strtoul(startaddr, &c, 0);
	if(*c != 0) {
		printf("incorrect address\n");
		return;
	}

	for(p=0;p<DFII_NPHASES;p++)
		for(i=0;i<DFII_PIX_DATA_SIZE;i++)
			MMPTR(sdram_dfii_pix_wrdata_addr[p]+4*i) = 0x10*p + i;

	sdram_dfii_piwr_address_write(addr);
	sdram_dfii_piwr_baddress_write(0);
	command_pwr(DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS|DFII_COMMAND_WRDATA);
}

#ifdef CSR_DDRPHY_BASE

#ifdef KUSDDRPHY
#define ERR_DDRPHY_DELAY 512
#else
#define ERR_DDRPHY_DELAY 32
#endif
#define ERR_DDRPHY_BITSLIP 8

#ifdef CSR_DDRPHY_WLEVEL_EN_ADDR

void sdrwlon(void)
{
	sdram_dfii_pi0_address_write(DDR3_MR1 | (1 << 7));
	sdram_dfii_pi0_baddress_write(1);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
	ddrphy_wlevel_en_write(1);
}

void sdrwloff(void)
{
	sdram_dfii_pi0_address_write(DDR3_MR1);
	sdram_dfii_pi0_baddress_write(1);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
	ddrphy_wlevel_en_write(0);
}

static void write_level_scan(void)
{
	int i, j;
	int dq_address;
	unsigned char dq;

	printf("Write leveling scan:\n");

	sdrwlon();
	cdelay(100);
	for(i=0;i<DFII_PIX_DATA_SIZE/2;i++) {
		printf("m%d: ", i);
	    dq_address = sdram_dfii_pix_rddata_addr[0]+4*(DFII_PIX_DATA_SIZE/2-1-i);
		ddrphy_dly_sel_write(1 << i);
		ddrphy_wdly_dq_rst_write(1);
		ddrphy_wdly_dqs_rst_write(1);
		for(j=0;j<ERR_DDRPHY_DELAY - ddrphy_half_sys8x_taps_read();j++) {
			ddrphy_wlevel_strobe_write(1);
			cdelay(10);
			dq = MMPTR(dq_address);
			printf("%d", dq != 0);
			ddrphy_wdly_dq_inc_write(1);
			ddrphy_wdly_dqs_inc_write(1);
			cdelay(10);
		}
		printf("\n");
	}
	sdrwloff();
}

static int write_level(int *delay, int *high_skew)
{
	int i;
	int dq_address;
	unsigned char dq;
	int err_ddrphy_wdly;
	int ok;

	err_ddrphy_wdly = ERR_DDRPHY_DELAY - ddrphy_half_sys8x_taps_read();

	printf("Write leveling: ");

	sdrwlon();
	cdelay(100);
	for(i=0;i<DFII_PIX_DATA_SIZE/2;i++) {
		dq_address = sdram_dfii_pix_rddata_addr[0]+4*(DFII_PIX_DATA_SIZE/2-1-i);
		ddrphy_dly_sel_write(1 << i);
		ddrphy_wdly_dq_rst_write(1);
		ddrphy_wdly_dqs_rst_write(1);
#ifdef KUSDDRPHY /* Need to init manually on Ultrascale */
		int j;
		for(j=0; j<ddrphy_wdly_dqs_taps_read(); j++)
			ddrphy_wdly_dqs_inc_write(1);
#endif

		delay[i] = 0;

		ddrphy_wlevel_strobe_write(1);
		cdelay(10);
		dq = MMPTR(dq_address);
		if(dq != 0) {
			/*
			 * Assume this DQ group has between 1 and 2 bit times of skew.
			 * Bring DQS into the CK=0 zone before continuing leveling.
			 */
#ifndef DDRPHY_HIGH_SKEW_DISABLE
			high_skew[i] = 1;
			while(dq != 0) {
				delay[i]++;
				if(delay[i] >= err_ddrphy_wdly)
					break;
				ddrphy_wdly_dq_inc_write(1);
				ddrphy_wdly_dqs_inc_write(1);
				ddrphy_wlevel_strobe_write(1);
				cdelay(10);
				dq = MMPTR(dq_address);
			 }
#else
			high_skew[i] = 0;
#endif
		} else
			high_skew[i] = 0;

		while(dq == 0) {
			delay[i]++;
			if(delay[i] >= err_ddrphy_wdly)
				break;
			ddrphy_wdly_dq_inc_write(1);
			ddrphy_wdly_dqs_inc_write(1);

			ddrphy_wlevel_strobe_write(1);
			cdelay(10);
			dq = MMPTR(dq_address);
		}
	}
	sdrwloff();

	ok = 1;
	for(i=DFII_PIX_DATA_SIZE/2-1;i>=0;i--) {
		printf("%2d%c ", delay[i], high_skew[i] ? '*' : ' ');
		if(delay[i] >= err_ddrphy_wdly)
			ok = 0;
	}

	if(ok)
		printf("completed\n");
	else
		printf("failed\n");

	return ok;
}

#endif /* CSR_DDRPHY_WLEVEL_EN_ADDR */

static void read_bitslip_inc(char m)
{
		ddrphy_dly_sel_write(1 << m);
#ifdef KUSDDRPHY
		ddrphy_rdly_dq_bitslip_write(1);
#else
		/* 7-series SERDES in DDR mode needs 3 pulses for 1 bitslip */
		ddrphy_rdly_dq_bitslip_write(1);
		ddrphy_rdly_dq_bitslip_write(1);
		ddrphy_rdly_dq_bitslip_write(1);
#endif
}

static void read_bitslip(int *delay, int *high_skew)
{
	int bitslip_thr;
	int i;

	bitslip_thr = 0x7fffffff;
	for(i=0;i<DFII_PIX_DATA_SIZE/2;i++)
		if(high_skew[i] && (delay[i] < bitslip_thr))
			bitslip_thr = delay[i];
	if(bitslip_thr == 0x7fffffff)
		return;
	bitslip_thr = bitslip_thr/2;

	printf("Read bitslip: ");
	for(i=DFII_PIX_DATA_SIZE/2-1;i>=0;i--)
		if(delay[i] > bitslip_thr) {
			read_bitslip_inc(i);
			printf("%d ", i);
		}
	printf("\n");
}

static int read_level_scan(int silent)
{
	unsigned int prv;
	unsigned char prs[DFII_NPHASES*DFII_PIX_DATA_SIZE];
	int p, i, j;
	int working;
	int working_delays;
	int optimal;

	if (!silent)
		printf("Read delays scan:\n");

	/* Generate pseudo-random sequence */
	prv = 42;
	for(i=0;i<DFII_NPHASES*DFII_PIX_DATA_SIZE;i++) {
		prv = 1664525*prv + 1013904223;
		prs[i] = prv;
	}

	/* Activate */
	sdram_dfii_pi0_address_write(0);
	sdram_dfii_pi0_baddress_write(0);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CS);
	cdelay(15);

	/* Write test pattern */
	for(p=0;p<DFII_NPHASES;p++)
		for(i=0;i<DFII_PIX_DATA_SIZE;i++)
			MMPTR(sdram_dfii_pix_wrdata_addr[p]+4*i) = prs[DFII_PIX_DATA_SIZE*p+i];
	sdram_dfii_piwr_address_write(0);
	sdram_dfii_piwr_baddress_write(0);
	command_pwr(DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS|DFII_COMMAND_WRDATA);

	/* Calibrate each DQ in turn */
	sdram_dfii_pird_address_write(0);
	sdram_dfii_pird_baddress_write(0);
	working = 0;
	working_delays = 0;
	optimal = 1;
	for(i=DFII_PIX_DATA_SIZE/2-1;i>=0;i--) {
		if (!silent)
			printf("m%d: ", (DFII_PIX_DATA_SIZE/2-i-1));
		ddrphy_dly_sel_write(1 << (DFII_PIX_DATA_SIZE/2-i-1));
		ddrphy_rdly_dq_rst_write(1);
		for(j=0; j<ERR_DDRPHY_DELAY;j++) {
			int working_delay;
			command_prd(DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA);
			cdelay(15);
			working_delay = 1;
			for(p=0;p<DFII_NPHASES;p++) {
				if(MMPTR(sdram_dfii_pix_rddata_addr[p]+4*i) != prs[DFII_PIX_DATA_SIZE*p+i])
					working_delay = 0;
				if(MMPTR(sdram_dfii_pix_rddata_addr[p]+4*(i+DFII_PIX_DATA_SIZE/2)) != prs[DFII_PIX_DATA_SIZE*p+i+DFII_PIX_DATA_SIZE/2])
					working_delay = 0;
			}
			working |= working_delay;
			working_delays += working_delay;
			if ((j == 0) || (j == (ERR_DDRPHY_DELAY-1)))
				/* to have an optimal scan, first tap and last tap should not be working */
				optimal &= (working_delay == 0);
			if (!silent)
				printf("%d", working_delay);
			ddrphy_rdly_dq_inc_write(1);
		}
		if (!silent)
			printf("\n");
	}

	/* Precharge */
	sdram_dfii_pi0_address_write(0);
	sdram_dfii_pi0_baddress_write(0);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
	cdelay(15);

	/* Successful if working and optimal or number of working delays > 3/4 of the taps */
	return working & (optimal | working_delays > 3*(DFII_PIX_DATA_SIZE/2)*ERR_DDRPHY_DELAY/4);
}

static void read_level(void)
{
	unsigned int prv;
	unsigned char prs[DFII_NPHASES*DFII_PIX_DATA_SIZE];
	int p, i, j;
	int working;
	int delay, delay_min, delay_max;

	printf("Read delays: ");

	/* Generate pseudo-random sequence */
	prv = 42;
	for(i=0;i<DFII_NPHASES*DFII_PIX_DATA_SIZE;i++) {
		prv = 1664525*prv + 1013904223;
		prs[i] = prv;
	}

	/* Activate */
	sdram_dfii_pi0_address_write(0);
	sdram_dfii_pi0_baddress_write(0);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CS);
	cdelay(15);

	/* Write test pattern */
	for(p=0;p<DFII_NPHASES;p++)
		for(i=0;i<DFII_PIX_DATA_SIZE;i++)
			MMPTR(sdram_dfii_pix_wrdata_addr[p]+4*i) = prs[DFII_PIX_DATA_SIZE*p+i];
	sdram_dfii_piwr_address_write(0);
	sdram_dfii_piwr_baddress_write(0);
	command_pwr(DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS|DFII_COMMAND_WRDATA);

	/* Calibrate each DQ in turn */
	sdram_dfii_pird_address_write(0);
	sdram_dfii_pird_baddress_write(0);
	for(i=0;i<DFII_PIX_DATA_SIZE/2;i++) {
		ddrphy_dly_sel_write(1 << (DFII_PIX_DATA_SIZE/2-i-1));
		delay = 0;

		/* Find smallest working delay */
		ddrphy_rdly_dq_rst_write(1);
		while(1) {
			command_prd(DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA);
			cdelay(15);
			working = 1;
			for(p=0;p<DFII_NPHASES;p++) {
				if(MMPTR(sdram_dfii_pix_rddata_addr[p]+4*i) != prs[DFII_PIX_DATA_SIZE*p+i])
					working = 0;
				if(MMPTR(sdram_dfii_pix_rddata_addr[p]+4*(i+DFII_PIX_DATA_SIZE/2)) != prs[DFII_PIX_DATA_SIZE*p+i+DFII_PIX_DATA_SIZE/2])
					working = 0;
			}
			if(working)
				break;
			delay++;
			if(delay >= ERR_DDRPHY_DELAY)
				break;
			ddrphy_rdly_dq_inc_write(1);
		}
		delay_min = delay;

		/* Get a bit further into the working zone */
#ifdef KUSDDRPHY
		for(j=0;j<16;j++) {
			delay += 1;
			ddrphy_rdly_dq_inc_write(1);
		}
#else
		delay++;
		ddrphy_rdly_dq_inc_write(1);
#endif

		/* Find largest working delay */
		while(1) {
			command_prd(DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA);
			cdelay(15);
			working = 1;
			for(p=0;p<DFII_NPHASES;p++) {
				if(MMPTR(sdram_dfii_pix_rddata_addr[p]+4*i) != prs[DFII_PIX_DATA_SIZE*p+i])
					working = 0;
				if(MMPTR(sdram_dfii_pix_rddata_addr[p]+4*(i+DFII_PIX_DATA_SIZE/2)) != prs[DFII_PIX_DATA_SIZE*p+i+DFII_PIX_DATA_SIZE/2])
					working = 0;
			}
			if(!working)
				break;
			delay++;
			if(delay >= ERR_DDRPHY_DELAY)
				break;
			ddrphy_rdly_dq_inc_write(1);
		}
		delay_max = delay;

		printf("%d:%02d-%02d  ", DFII_PIX_DATA_SIZE/2-i-1, delay_min, delay_max);

		/* Set delay to the middle */
		ddrphy_rdly_dq_rst_write(1);
		for(j=0;j<(delay_min+delay_max)/2;j++)
			ddrphy_rdly_dq_inc_write(1);
	}

	/* Precharge */
	sdram_dfii_pi0_address_write(0);
	sdram_dfii_pi0_baddress_write(0);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
	cdelay(15);

	printf("completed\n");
}
#endif /* CSR_DDRPHY_BASE */

static unsigned int seed_to_data_32(unsigned int seed, int random)
{
	if (random)
		return 1664525*seed + 1013904223;
	else
		return seed + 1;
}

static unsigned short seed_to_data_16(unsigned short seed, int random)
{
	if (random)
		return 25173*seed + 13849;
	else
		return seed + 1;
}

#define ONEZERO 0xAAAAAAAA
#define ZEROONE 0x55555555

#ifndef MEMTEST_BUS_SIZE
#define MEMTEST_BUS_SIZE (512)
#endif

//#define MEMTEST_BUS_DEBUG

static int memtest_bus(void)
{
	volatile unsigned int *array = (unsigned int *)MAIN_RAM_BASE;
	int i, errors;
	unsigned int rdata;

	errors = 0;

	for(i=0;i<MEMTEST_BUS_SIZE/4;i++) {
		array[i] = ONEZERO;
	}
	flush_cpu_dcache();
	flush_l2_cache();
	for(i=0;i<MEMTEST_BUS_SIZE/4;i++) {
		rdata = array[i];
		if(rdata != ONEZERO) {
			errors++;
#ifdef MEMTEST_BUS_DEBUG
			printf("[bus: %0x]: %08x vs %08x\n", i, rdata, ONEZERO);
#endif
		}
	}

	for(i=0;i<MEMTEST_BUS_SIZE/4;i++) {
		array[i] = ZEROONE;
	}
	flush_cpu_dcache();
	flush_l2_cache();
	for(i=0;i<MEMTEST_BUS_SIZE/4;i++) {
		rdata = array[i];
		if(rdata != ZEROONE) {
			errors++;
#ifdef MEMTEST_BUS_DEBUG
			printf("[bus %0x]: %08x vs %08x\n", i, rdata, ZEROONE);
#endif
		}
	}

	return errors;
}

#ifndef MEMTEST_DATA_SIZE
#define MEMTEST_DATA_SIZE (2*1024*1024)
#endif
#define MEMTEST_DATA_RANDOM 1

//#define MEMTEST_DATA_DEBUG

static int memtest_data(void)
{
	volatile unsigned int *array = (unsigned int *)MAIN_RAM_BASE;
	int i, errors;
	unsigned int seed_32;
	unsigned int rdata;

	errors = 0;
	seed_32 = 0;

	for(i=0;i<MEMTEST_DATA_SIZE/4;i++) {
		seed_32 = seed_to_data_32(seed_32, MEMTEST_DATA_RANDOM);
		array[i] = seed_32;
	}

	seed_32 = 0;
	flush_cpu_dcache();
	flush_l2_cache();
	for(i=0;i<MEMTEST_DATA_SIZE/4;i++) {
		seed_32 = seed_to_data_32(seed_32, MEMTEST_DATA_RANDOM);
		rdata = array[i];
		if(rdata != seed_32) {
			errors++;
#ifdef MEMTEST_DATA_DEBUG
			printf("[data %0x]: %08x vs %08x\n", i, rdata, seed_32);
#endif
		}
	}

	return errors;
}
#ifndef MEMTEST_ADDR_SIZE
#define MEMTEST_ADDR_SIZE (32*1024)
#endif
#define MEMTEST_ADDR_RANDOM 0

//#define MEMTEST_ADDR_DEBUG

static int memtest_addr(void)
{
	volatile unsigned int *array = (unsigned int *)MAIN_RAM_BASE;
	int i, errors;
	unsigned short seed_16;
	unsigned short rdata;

	errors = 0;
	seed_16 = 0;

	for(i=0;i<MEMTEST_ADDR_SIZE/4;i++) {
		seed_16 = seed_to_data_16(seed_16, MEMTEST_ADDR_RANDOM);
		array[(unsigned int) seed_16] = i;
	}

	seed_16 = 0;
	flush_cpu_dcache();
	flush_l2_cache();
	for(i=0;i<MEMTEST_ADDR_SIZE/4;i++) {
		seed_16 = seed_to_data_16(seed_16, MEMTEST_ADDR_RANDOM);
		rdata = array[(unsigned int) seed_16];
		if(rdata != i) {
			errors++;
#ifdef MEMTEST_ADDR_DEBUG
			printf("[addr %0x]: %08x vs %08x\n", i, rdata, i);
#endif
		}
	}

	return errors;
}

int memtest(void)
{
	int bus_errors, data_errors, addr_errors;

	bus_errors = memtest_bus();
	if(bus_errors != 0)
		printf("Memtest bus failed: %d/%d errors\n", bus_errors, 2*128);

	data_errors = memtest_data();
	if(data_errors != 0)
		printf("Memtest data failed: %d/%d errors\n", data_errors, MEMTEST_DATA_SIZE/4);

	addr_errors = memtest_addr();
	if(addr_errors != 0)
		printf("Memtest addr failed: %d/%d errors\n", addr_errors, MEMTEST_ADDR_SIZE/4);

	if(bus_errors + data_errors + addr_errors != 0)
		return 0;
	else {
		printf("Memtest OK\n");
		return 1;
	}
}

#ifdef CSR_DDRPHY_BASE
int sdrlevel(void)
{
	int delay[DFII_PIX_DATA_SIZE/2];
	int high_skew[DFII_PIX_DATA_SIZE/2];
	int i, j;

	for(i=0; i<DFII_PIX_DATA_SIZE/2; i++) {
		ddrphy_dly_sel_write(1<<i);
		ddrphy_rdly_dq_rst_write(1);
		ddrphy_rdly_dq_bitslip_rst_write(1);
	}

#ifndef CSR_DDRPHY_WLEVEL_EN_ADDR
	for(i=0; i<DFII_PIX_DATA_SIZE/2; i++) {
		delay[i] = 0;
		high_skew[i] = 0;
	}
#else
	write_level_scan();
	if(!write_level(delay, high_skew))
		return 0;
#endif
	/* check for optimal read leveling window */
	for(i=0; i<ERR_DDRPHY_BITSLIP; i++) {
		/* scan */
		if (read_level_scan(1))
			break;
		if (i == ERR_DDRPHY_BITSLIP-1)
			return 0;
		/* increment bitslip */
		for(j=0; j<DFII_PIX_DATA_SIZE/2; j++)
			read_bitslip_inc(j);
	}
	/* show bitslip and scan */
	printf("Read bitslip: %d\n", i);
    read_level_scan(0);
	read_level();

	return 1;
}
#endif

int sdrinit(void)
{
	printf("Initializing SDRAM...\n");

	init_sequence();
#ifdef CSR_DDRPHY_BASE
#if CSR_DDRPHY_EN_VTC_ADDR
	ddrphy_en_vtc_write(0);
#endif
	sdrlevel();
#if CSR_DDRPHY_EN_VTC_ADDR
	ddrphy_en_vtc_write(1);
#endif
#endif
	sdram_dfii_control_write(DFII_CONTROL_SEL);
	if(!memtest())
		return 0;

	return 1;
}

#endif
