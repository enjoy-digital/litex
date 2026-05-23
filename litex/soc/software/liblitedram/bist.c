// This file is Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#include <generated/csr.h>

#if (defined(CSR_SDRAM_GENERATOR_BASE)  && defined(CSR_SDRAM_CHECKER_BASE))  || \
    (defined(CSR_SDRAM1_GENERATOR_BASE) && defined(CSR_SDRAM1_CHECKER_BASE)) || \
    (defined(CSR_SDRAM2_GENERATOR_BASE) && defined(CSR_SDRAM2_CHECKER_BASE)) || \
    (defined(CSR_SDRAM3_GENERATOR_BASE) && defined(CSR_SDRAM3_CHECKER_BASE))

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <uart.h>
#include <time.h>
#include <console.h>
#include <inttypes.h>
#include <stdint.h>

#include <generated/mem.h>
#include <generated/sdram_phy.h>
#include <liblitedram/bist.h>
#include <liblitedram/utils.h>

#define SDRAM_TEST_BASE 0x00000000
#define SDRAM_TEST_DATA_BYTES (SDRAM_PHY_DFI_DATABITS / 8 * SDRAM_PHY_PHASES)
#define ARRAY_SIZE(array) (sizeof(array) / sizeof((array)[0]))

#ifdef DDRAM_MAIN_CHANNEL
#define SDRAM_BIST_MAIN_CHANNEL DDRAM_MAIN_CHANNEL
#else
#define SDRAM_BIST_MAIN_CHANNEL 0
#endif

#ifdef MAIN_RAM_SIZE
#define SDRAM_BIST_MAIN_SIZE MAIN_RAM_SIZE
#else
#define SDRAM_BIST_MAIN_SIZE 0
#endif

#ifdef DDRAM1_SIZE
#define SDRAM_BIST_DDRAM1_SIZE DDRAM1_SIZE
#else
#define SDRAM_BIST_DDRAM1_SIZE 0
#endif

#ifdef DDRAM2_SIZE
#define SDRAM_BIST_DDRAM2_SIZE DDRAM2_SIZE
#else
#define SDRAM_BIST_DDRAM2_SIZE 0
#endif

#ifdef DDRAM3_SIZE
#define SDRAM_BIST_DDRAM3_SIZE DDRAM3_SIZE
#else
#define SDRAM_BIST_DDRAM3_SIZE 0
#endif

typedef void (*sdram_bist_write_csr)(uint32_t value);
typedef uint32_t (*sdram_bist_read_csr)(void);

struct sdram_bist_target {
	const char *name;
	uint32_t channel;
	uint64_t size;
	uint32_t data_bytes;

	sdram_bist_write_csr generator_reset_write;
	sdram_bist_write_csr generator_start_write;
	sdram_bist_write_csr generator_random_write;
	sdram_bist_write_csr generator_base_write;
	sdram_bist_write_csr generator_end_write;
	sdram_bist_write_csr generator_length_write;
	sdram_bist_read_csr  generator_done_read;
	sdram_bist_read_csr  generator_ticks_read;

	sdram_bist_write_csr checker_reset_write;
	sdram_bist_write_csr checker_start_write;
	sdram_bist_write_csr checker_random_write;
	sdram_bist_write_csr checker_base_write;
	sdram_bist_write_csr checker_end_write;
	sdram_bist_write_csr checker_length_write;
	sdram_bist_read_csr  checker_done_read;
	sdram_bist_read_csr  checker_ticks_read;
	sdram_bist_read_csr  checker_errors_read;
};

struct sdram_bist_stats {
	uint64_t wr_ticks;
	uint64_t wr_length;
	uint64_t rd_ticks;
	uint64_t rd_length;
	uint64_t rd_errors;
};

#define SDRAM_BIST_TARGET(prefix, label, channel_id, memory_size) { \
	.name                   = label, \
	.channel                = channel_id, \
	.size                   = memory_size, \
	.data_bytes             = SDRAM_TEST_DATA_BYTES, \
	.generator_reset_write  = prefix##_generator_reset_write, \
	.generator_start_write  = prefix##_generator_start_write, \
	.generator_random_write = prefix##_generator_random_write, \
	.generator_base_write   = prefix##_generator_base_write, \
	.generator_end_write    = prefix##_generator_end_write, \
	.generator_length_write = prefix##_generator_length_write, \
	.generator_done_read    = prefix##_generator_done_read, \
	.generator_ticks_read   = prefix##_generator_ticks_read, \
	.checker_reset_write    = prefix##_checker_reset_write, \
	.checker_start_write    = prefix##_checker_start_write, \
	.checker_random_write   = prefix##_checker_random_write, \
	.checker_base_write     = prefix##_checker_base_write, \
	.checker_end_write      = prefix##_checker_end_write, \
	.checker_length_write   = prefix##_checker_length_write, \
	.checker_done_read      = prefix##_checker_done_read, \
	.checker_ticks_read     = prefix##_checker_ticks_read, \
	.checker_errors_read    = prefix##_checker_errors_read, \
}

static const struct sdram_bist_target sdram_bist_targets[] = {
#if defined(CSR_SDRAM_GENERATOR_BASE) && defined(CSR_SDRAM_CHECKER_BASE)
	SDRAM_BIST_TARGET(sdram,  "sdram",  SDRAM_BIST_MAIN_CHANNEL, SDRAM_BIST_MAIN_SIZE),
#endif
#if defined(CSR_SDRAM1_GENERATOR_BASE) && defined(CSR_SDRAM1_CHECKER_BASE)
	SDRAM_BIST_TARGET(sdram1, "sdram1", 1,                       SDRAM_BIST_DDRAM1_SIZE),
#endif
#if defined(CSR_SDRAM2_GENERATOR_BASE) && defined(CSR_SDRAM2_CHECKER_BASE)
	SDRAM_BIST_TARGET(sdram2, "sdram2", 2,                       SDRAM_BIST_DDRAM2_SIZE),
#endif
#if defined(CSR_SDRAM3_GENERATOR_BASE) && defined(CSR_SDRAM3_CHECKER_BASE)
	SDRAM_BIST_TARGET(sdram3, "sdram3", 3,                       SDRAM_BIST_DDRAM3_SIZE),
#endif
};

static uint32_t pseudo_random_bases[128] = {
	0x000e4018,0x0003338d,0x00233429,0x001f589d,
	0x001c922b,0x0011dc60,0x000d1e8f,0x000b20cf,
	0x00360188,0x00041174,0x0003d065,0x000bfe34,
	0x001bfc54,0x001dc7d5,0x00036587,0x00197383,
	0x0035b2d3,0x001c3765,0x00397fae,0x00239bc0,
	0x0000d4f3,0x00146fb7,0x0036183a,0x002b8d54,
	0x00239149,0x0013e6c0,0x001b8f66,0x002b1587,
	0x000d1539,0x000bdf18,0x0030a175,0x000c6133,
	0x002df309,0x002c06bd,0x0021dbd1,0x00058fc8,
	0x003ace6f,0x000ffa4d,0x003073d0,0x000a161f,
	0x002586dd,0x002e4a0e,0x00189ce9,0x0008e72e,
	0x0005dd92,0x001d2bc5,0x00250aaa,0x000a369f,
	0x001dcc17,0x000ced9d,0x0030a7f9,0x002394a3,
	0x003a0959,0x002eb2d2,0x0014d1d9,0x002f6217,
	0x002d7982,0x001ad120,0x00222c54,0x000923b7,
	0x0015e7df,0x001f55f6,0x0014ea5f,0x003b2b57,
	0x003091fe,0x00228da6,0x001c1c59,0x00298218,
	0x000728f9,0x001d5172,0x00041bdc,0x002860c3,
	0x0033595e,0x00224555,0x000878de,0x001b017c,
	0x0028475d,0x001b3758,0x003fe6cf,0x0032a410,
	0x003abba8,0x0012499d,0x0021e797,0x0011df68,
	0x001f917d,0x0021a184,0x0036d6eb,0x00331f8e,
	0x002e55e6,0x001c12b3,0x0011b4da,0x003f2b86,
	0x000ba2eb,0x000607e8,0x000e08fb,0x0013904d,
	0x00147a4a,0x00360956,0x000821ad,0x0031400e,
	0x0030d8e6,0x003be90f,0x00202e56,0x00017835,
	0x000ea9a1,0x00222753,0x002b8ade,0x000e4757,
	0x00259169,0x0037a663,0x00143e83,0x003a139e,
	0x00006a57,0x0021b6bb,0x0016de10,0x000d9ede,
	0x00263370,0x001975eb,0x0013903c,0x002fdc68,
	0x0014ada3,0x000012bd,0x00297df2,0x003e8aa1,
	0x00027e36,0x000e51ae,0x002e7627,0x00275c9f,
};

static uint64_t sdram_bist_target_size(const struct sdram_bist_target *target)
{
	if (target->size != 0)
		return target->size;
	return sdram_get_supported_memory();
}

static uint64_t align_down(uint64_t value, uint32_t alignment)
{
	return value & ~((uint64_t)alignment - 1);
}

static int sdram_bist_add_errors(int errors, int new_errors)
{
	if (new_errors < 0)
		return new_errors;
	if (INT32_MAX - errors < new_errors)
		return INT32_MAX;
	return errors + new_errors;
}

static const struct sdram_bist_target *sdram_bist_find_target(const char *name)
{
	char *c;
	uint32_t channel;

	if (name == NULL)
		return &sdram_bist_targets[0];

	for (unsigned int i = 0; i < ARRAY_SIZE(sdram_bist_targets); i++) {
		if (strcmp(name, sdram_bist_targets[i].name) == 0)
			return &sdram_bist_targets[i];
	}

	if (strncmp(name, "sdram", 5) == 0 && name[5] != '\0')
		name += 5;

	channel = strtoul(name, &c, 0);
	if (*c != 0)
		return NULL;

	for (unsigned int i = 0; i < ARRAY_SIZE(sdram_bist_targets); i++) {
		if (channel == sdram_bist_targets[i].channel)
			return &sdram_bist_targets[i];
	}

	return NULL;
}

void sdram_bist_print_targets(void)
{
	printf("Available SDRAM BIST controllers:");
	for (unsigned int i = 0; i < ARRAY_SIZE(sdram_bist_targets); i++)
		printf(" %s(channel=%" PRIu32 ")", sdram_bist_targets[i].name, sdram_bist_targets[i].channel);
	printf(" all\n");
}

static void sdram_bist_write(const struct sdram_bist_target *target, uint32_t base, uint32_t length)
{
	/* Prepare write. */
	target->generator_reset_write(1);
	target->generator_random_write(1); /* Random data. */
	target->generator_base_write(base);
	target->generator_end_write(base + length);
	target->generator_length_write(length);

	/* Start write. */
	target->generator_start_write(1);

	/* Wait write. */
	while (target->generator_done_read() == 0);
}

static void sdram_bist_read(const struct sdram_bist_target *target, uint32_t base, uint32_t length)
{
	/* Prepare read. */
	target->checker_reset_write(1);
	target->checker_random_write(1); /* Random data. */
	target->checker_base_write(base);
	target->checker_end_write(base + length);
	target->checker_length_write(length);

	/* Start read. */
	target->checker_start_write(1);

	/* Wait read. */
	while (target->checker_done_read() == 0);
}

static void sdram_bist_loop(const struct sdram_bist_target *target,
	uint32_t loop, uint32_t burst_length, uint32_t random, struct sdram_bist_stats *stats)
{
	uint32_t base;
	uint32_t length;
	uint64_t length64;
	uint64_t max_base;
	uint64_t target_size = sdram_bist_target_size(target);

	length64 = (uint64_t)burst_length * target->data_bytes;
	if (length64 > target_size)
		length64 = align_down(target_size, target->data_bytes);
	if (length64 > UINT32_MAX)
		length64 = align_down(UINT32_MAX, target->data_bytes);
	if (length64 == 0)
		return;
	length = length64;

	for (int i = 0; i < 128; i++) {
		if (random)
			base = SDRAM_TEST_BASE + pseudo_random_bases[(i + loop) % 128] * target->data_bytes;
		else
			base = SDRAM_TEST_BASE + ((i + loop) % 128) * target->data_bytes;

		max_base = target_size - length;
		if (max_base == 0)
			base = 0;
		else if (base > max_base)
			base = align_down(base % max_base, target->data_bytes);

		sdram_bist_write(target, base, length);
		stats->wr_length += length;
		stats->wr_ticks  += target->generator_ticks_read();

		sdram_bist_read(target, base, length);
		stats->rd_length += length;
		stats->rd_ticks  += target->checker_ticks_read();
		stats->rd_errors += target->checker_errors_read();
	}
}

static uint64_t compute_speed_mibs(uint64_t length, uint64_t ticks)
{
	if (ticks == 0)
		return 0;
	return length * (uint64_t)CONFIG_CLOCK_FREQUENCY / (1024 * 1024) / ticks;
}

static void sdram_bist_print_header(void)
{
	printf("CTRL       WR-SPEED(MiB/s) RD-SPEED(MiB/s)  TESTED(MiB)       ERRORS\n");
}

static void sdram_bist_print_stats(const struct sdram_bist_target *target,
	const struct sdram_bist_stats *stats, uint64_t total_length, uint64_t total_errors)
{
	printf("%-8s %15" PRIu64 " %15" PRIu64 "%12" PRIu64 "%12" PRIu64 "\n",
		target->name,
		compute_speed_mibs(stats->wr_length, stats->wr_ticks),
		compute_speed_mibs(stats->rd_length, stats->rd_ticks),
		total_length / (1024 * 1024),
		total_errors);
}

static int sdram_bist_run_target(const struct sdram_bist_target *target,
	uint32_t burst_length, uint32_t random, uint32_t loops)
{
	uint64_t total_length = 0;
	uint64_t total_errors = 0;
	uint32_t report_period = 100;
	struct sdram_bist_stats stats = {0};

	if (loops != 0 && loops < report_period)
		report_period = loops;

	printf("Starting SDRAM BIST on %s/channel %" PRIu32 " with burst_length=%" PRIu32 ", random=%" PRIu32 ", loops=%" PRIu32 "\n",
		target->name, target->channel, burst_length, random, loops);
	sdram_bist_print_header();

	for (uint32_t i = 0; loops == 0 || i < loops; i++) {
		if (readchar_nonblock())
			break;

		sdram_bist_loop(target, i, burst_length, random, &stats);

		if (((i + 1) % report_period) == 0) {
			total_length += stats.wr_length;
			total_errors += stats.rd_errors;
			sdram_bist_print_stats(target, &stats, total_length, total_errors);
			memset(&stats, 0, sizeof(stats));
		}
	}

	if (stats.wr_length != 0) {
		total_length += stats.wr_length;
		total_errors += stats.rd_errors;
		sdram_bist_print_stats(target, &stats, total_length, total_errors);
	}

	if (total_errors > INT32_MAX)
		return INT32_MAX;
	return total_errors;
}

static int sdram_bist_run_all(uint32_t burst_length, uint32_t random, uint32_t loops)
{
	int errors = 0;

	for (unsigned int i = 0; i < ARRAY_SIZE(sdram_bist_targets); i++) {
		int target_errors = sdram_bist_run_target(&sdram_bist_targets[i], burst_length, random, loops);
		if (target_errors < 0)
			return target_errors;
		errors = sdram_bist_add_errors(errors, target_errors);
	}

	printf("SDRAM BIST total errors: %d\n", errors);
	return errors;
}

void sdram_bist(uint32_t burst_length, uint32_t random)
{
	sdram_bist_controller(NULL, burst_length, random, 0);
}

int sdram_bist_controller(const char *controller, uint32_t burst_length, uint32_t random, uint32_t loops)
{
	const struct sdram_bist_target *target;

	if (controller != NULL && strcmp(controller, "all") == 0) {
		if (loops == 0)
			loops = 100;
		return sdram_bist_run_all(burst_length, random, loops);
	}

	target = sdram_bist_find_target(controller);
	if (target == NULL) {
		printf("Unknown SDRAM BIST controller: %s\n", controller);
		return -1;
	}

	return sdram_bist_run_target(target, burst_length, random, loops);
}

static int sdram_hw_test_target(const struct sdram_bist_target *target,
	uint64_t origin, uint64_t size, uint64_t burst_length)
{
	uint64_t burst_size;
	uint64_t supported_memory = sdram_bist_target_size(target);
	uint64_t end;
	int errors = 0;

	if (burst_length > UINT64_MAX / target->data_bytes) {
		printf("Burst size is too large\n");
		return -1;
	}

	burst_size = target->data_bytes * burst_length;
	if (burst_size < target->data_bytes) {
		printf("Burst size is too small\n");
		return -1;
	}
	if (burst_size > UINT32_MAX) {
		printf("Burst size is too large\n");
		return -1;
	}

	if (origin >= supported_memory) {
		printf("Selected origin out of memory bounds for %s. Supported memory: ", target->name);
		print_size(supported_memory);
		printf("\n");
		return -1;
	}

	if (size > supported_memory - origin) {
		printf("Test would go out of %s bounds. Clipping size to memory end: ", target->name);
		print_size(supported_memory);
		printf("\n");
		size = supported_memory - origin;
	}

	end = origin + size;
	printf("Starting SDRAM HW test on %s/channel %" PRIu32 ": 0x%" PRIx64 "-0x%" PRIx64 "\n",
		target->name, target->channel, origin, end);

	for (uint64_t address = origin; address < end; address += burst_size) {
		uint64_t current_burst_size = burst_size;

		if (address + current_burst_size > end)
			current_burst_size = end - address;
		current_burst_size = align_down(current_burst_size, target->data_bytes);
		if (current_burst_size < target->data_bytes)
			break;

		sdram_bist_write(target, address, current_burst_size);
		sdram_bist_read(target, address, current_burst_size);
		errors += target->checker_errors_read();

		print_progress("  SDRAM HW test:", origin, address - origin + current_burst_size);
	}

	printf("\n");

	return errors;
}

int sdram_hw_test(uint64_t origin, uint64_t size, uint64_t burst_length)
{
	return sdram_hw_test_controller(NULL, origin, size, burst_length);
}

int sdram_hw_test_controller(const char *controller, uint64_t origin, uint64_t size, uint64_t burst_length)
{
	const struct sdram_bist_target *target;
	int total_errors = 0;

	if (controller != NULL && strcmp(controller, "all") == 0) {
		for (unsigned int i = 0; i < ARRAY_SIZE(sdram_bist_targets); i++) {
			int errors = sdram_hw_test_target(&sdram_bist_targets[i], origin, size, burst_length);
			if (errors < 0)
				return errors;
			total_errors = sdram_bist_add_errors(total_errors, errors);
		}
		return total_errors;
	}

	target = sdram_bist_find_target(controller);
	if (target == NULL) {
		printf("Unknown SDRAM BIST controller: %s\n", controller);
		return -1;
	}

	return sdram_hw_test_target(target, origin, size, burst_length);
}

#endif
