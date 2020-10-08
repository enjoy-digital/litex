#include "memtest.h"

#include <stdio.h>
#include <lfsr.h>
#include <system.h>

#include <generated/soc.h>
#include <generated/csr.h>

// #define MEMTEST_BUS_DEBUG
// #define MEMTEST_DATA_DEBUG
// #define MEMTEST_ADDR_DEBUG

#define KIB 1024
#define MIB (KIB*1024)
#define GIB (MIB*1024)

#define ONEZERO 0xAAAAAAAA
#define ZEROONE 0x55555555

#ifndef MEMTEST_BUS_SIZE
#define MEMTEST_BUS_SIZE (512)
#endif

#define MEMTEST_DATA_RANDOM 1

#ifndef MEMTEST_ADDR_SIZE
#define MEMTEST_ADDR_SIZE (32*1024)
#endif
#define MEMTEST_ADDR_RANDOM 0

static unsigned int seed_to_data_32(unsigned int seed, int random)
{
	return random ? lfsr(32, seed) : seed + 1;
}

static unsigned short seed_to_data_16(unsigned short seed, int random)
{
	return random ? lfsr(16, seed) : seed + 1;
}

int memtest_bus(unsigned int *addr, unsigned long size)
{
	volatile unsigned int *array = addr;
	int i, errors;
	unsigned int rdata;

	errors = 0;

	for(i = 0; i < size/4;i++) {
		array[i] = ONEZERO;
	}
	flush_cpu_dcache();
#ifdef CONFIG_L2_SIZE
	flush_l2_cache();
#endif
	for(i = 0; i < size/4; i++) {
		rdata = array[i];
		if(rdata != ONEZERO) {
			errors++;
#ifdef MEMTEST_BUS_DEBUG
			printf("[bus: 0x%0x]: 0x%08x vs 0x%08x\n", i, rdata, ONEZERO);
#endif
		}
	}

	for(i = 0; i < size/4; i++) {
		array[i] = ZEROONE;
	}
	flush_cpu_dcache();
#ifdef CONFIG_L2_SIZE
	flush_l2_cache();
#endif
	for(i = 0; i < size/4; i++) {
		rdata = array[i];
		if(rdata != ZEROONE) {
			errors++;
#ifdef MEMTEST_BUS_DEBUG
			printf("[bus 0x%0x]: 0x%08x vs 0x%08x\n", i, rdata, ZEROONE);
#endif
		}
	}

	return errors;
}

int memtest_addr(unsigned int *addr, unsigned long size, int random)
{
	volatile unsigned int *array = addr;
	int i, errors;
	unsigned short seed_16;
	unsigned short rdata;

	errors = 0;
	seed_16 = 1;

	for(i = 0; i < size/4; i++) {
		seed_16 = seed_to_data_16(seed_16, random);
		array[(unsigned int) seed_16] = i;
	}

	seed_16 = 1;
	flush_cpu_dcache();
#ifdef CONFIG_L2_SIZE
	flush_l2_cache();
#endif
	for(i = 0; i < size/4; i++) {
		seed_16 = seed_to_data_16(seed_16, random);
		rdata = array[(unsigned int) seed_16];
		if(rdata != i) {
			errors++;
#ifdef MEMTEST_ADDR_DEBUG
			printf("[addr 0x%0x]: 0x%08x vs 0x%08x\n", i, rdata, i);
#endif
		}
	}

	return errors;
}

static void print_size(unsigned long size) {
	if (size < KIB)
		printf("%luB", size);
	else if (size < MIB)
		printf("%luKiB", size/KIB);
	else if (size < GIB)
		printf("%luMiB", size/MIB);
	else
		printf("%luGiB", size/GIB);
}

static void print_speed(unsigned long speed) {
	print_size(speed);
	printf("/s");
}

static void print_progress(const char * header, unsigned int offset, unsigned int addr)
{
	printf("%s 0x%x-0x%x ", header, offset, offset + addr);
	print_size(addr);
	printf("   \r");
}

int memtest_data(unsigned int *addr, unsigned long size, int random)
{
	volatile unsigned int *array = addr;
	int i, errors;
	unsigned int seed_32;
	unsigned int rdata;

	errors = 0;
	seed_32 = 1;

	for(i = 0; i < size/4; i++) {
		seed_32 = seed_to_data_32(seed_32, random);
		array[i] = seed_32;
		if (i%0x8000 == 0)
			print_progress("  Write:", (unsigned long)addr, 4*i);
	}
	print_progress("  Write:", (unsigned long)addr, 4*i);
	printf("\n");

	seed_32 = 1;
	flush_cpu_dcache();
#ifdef CONFIG_L2_SIZE
	flush_l2_cache();
#endif
	for(i = 0; i < size/4; i++) {
		seed_32 = seed_to_data_32(seed_32, random);
		rdata = array[i];
		if(rdata != seed_32) {
			errors++;
#ifdef MEMTEST_DATA_DEBUG
			printf("[data 0x%0x]: 0x%08x vs 0x%08x\n", i, rdata, seed_32);
#endif
		}
		if (i%0x8000 == 0)
			print_progress("   Read:", (unsigned long)addr, 4*i);
	}
	print_progress("   Read:", (unsigned long)addr, 4*i);
	printf("\n");

	return errors;
}

void memspeed(unsigned int *addr, unsigned long size, bool read_only)
{
	volatile unsigned long *array = (unsigned long *)addr;
	int i;
	uint32_t start, end;
	unsigned long write_speed = 0;
	unsigned long read_speed;
	__attribute__((unused)) unsigned long data;
	const unsigned int sz = sizeof(unsigned long);

	printf("Memspeed at 0x%p (", addr);
	print_size(size);
	printf(")...\n");

	/* init timer */
	timer0_en_write(0);
	timer0_reload_write(0);
	timer0_load_write(0xffffffff);
	timer0_en_write(1);

	/* write speed */
	if (!read_only) {
		timer0_update_value_write(1);
		start = timer0_value_read();
		for(i = 0; i < size/sz; i++) {
			array[i] = -1ul;
		}
		timer0_update_value_write(1);
		end = timer0_value_read();
		uint64_t numerator   = ((uint64_t)size)*((uint64_t)CONFIG_CLOCK_FREQUENCY);
		uint64_t denominator = ((uint64_t)start - (uint64_t)end);
		write_speed = numerator/denominator;
		printf("  Write speed: ");
		print_speed(write_speed);
		printf("\n");
	}

	/* flush CPU and L2 caches */
	flush_cpu_dcache();
#ifdef CONFIG_L2_SIZE
	flush_l2_cache();
#endif

	/* read speed */
	timer0_en_write(1);
	timer0_update_value_write(1);
	start = timer0_value_read();
	for(i = 0; i < size/sz; i++) {
		data = array[i];
	}
	timer0_update_value_write(1);
	end = timer0_value_read();
	uint64_t numerator   = ((uint64_t)size)*((uint64_t)CONFIG_CLOCK_FREQUENCY);
	uint64_t denominator = ((uint64_t)start - (uint64_t)end);
	read_speed = numerator/denominator;
	printf("   Read speed: ");
	print_speed(read_speed);
	printf("\n");
}

int memtest(unsigned int *addr, unsigned long maxsize)
{
	int bus_errors, data_errors, addr_errors;
	unsigned long bus_size  = MEMTEST_BUS_SIZE < maxsize ? MEMTEST_BUS_SIZE : maxsize;
	unsigned long addr_size = MEMTEST_ADDR_SIZE < maxsize ? MEMTEST_ADDR_SIZE : maxsize;
	unsigned long data_size = maxsize;

	printf("Memtest at 0x%p (", addr);
	print_size(data_size);
	printf(")...\n");

	bus_errors  = memtest_bus(addr, bus_size);
	addr_errors = memtest_addr(addr, addr_size, MEMTEST_ADDR_RANDOM);
	data_errors = memtest_data(addr, data_size, MEMTEST_DATA_RANDOM);

	if(bus_errors + addr_errors + data_errors != 0) {
		printf("  bus errors:  %d/%ld\n", bus_errors,  2*bus_size/4);
		printf("  addr errors: %d/%ld\n", addr_errors, addr_size/4);
		printf("  data errors: %d/%ld\n", data_errors, data_size/4);
		printf("Memtest KO\n");
		return 0;
	}
	printf("Memtest OK\n");
	return 1;
}
