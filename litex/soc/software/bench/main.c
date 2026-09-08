/* CPU/memory microbenchmarks for LiteX Sim. SPDX-License-Identifier: BSD-2-Clause */
#include <stdint.h>
#include <stdio.h>
#include <irq.h>
#include <system.h>
#include <generated/csr.h>
#include <generated/mem.h>
#include <libbase/uart.h>
#ifdef CSR_SDRAM_BASE
#include <liblitedram/sdram.h>
#endif

#define WORDS (64*1024/sizeof(uint32_t))
#define ROUNDS 3
/* Keep the test data outside flush_l2_cache()'s eviction buffer at the start
   of main RAM, including when testing a larger L2. */
#if MAIN_RAM_SIZE < 128*1024
#error "The benchmark requires at least 128 KiB of main RAM"
#endif
#if defined(CONFIG_L2_SIZE) && 2*CONFIG_L2_SIZE > MAIN_RAM_SIZE - 64*1024
#error "The L2 eviction buffer overlaps the benchmark data"
#endif
static volatile uint32_t * const buffer =
	(volatile uint32_t *)(MAIN_RAM_BASE + MAIN_RAM_SIZE - 64*1024);
static volatile uint32_t result;

static inline uint32_t cycles(void)
{
	/* Some VexRiscv variants do not expose mcycle. Use the same system-clock
	   counter for every configuration and report the sampling overhead. */
	__asm__ volatile("fence iorw, iorw" ::: "memory");
	bench_latch_write(1);
	return bench_cycles_read();
}

static void report(const char *name, unsigned int bytes, unsigned int iterations,
	uint32_t elapsed, uint32_t checksum)
{
	printf("BENCH,%s,%u,%u,%u,%08x\n", name, bytes, iterations,
		(unsigned int)elapsed, (unsigned int)checksum);
}

static void sequential(unsigned int words)
{
	uint32_t start, elapsed, sum;

	flush_cpu_dcache();
	flush_l2_cache();
	start = cycles();
	for (unsigned int i = 0; i < words; i += 8) {
		buffer[i+0] = 0x12345678; buffer[i+1] = 0x12345678;
		buffer[i+2] = 0x12345678; buffer[i+3] = 0x12345678;
		buffer[i+4] = 0x12345678; buffer[i+5] = 0x12345678;
		buffer[i+6] = 0x12345678; buffer[i+7] = 0x12345678;
	}
	elapsed = cycles() - start;
	report("write", words*4, words, elapsed, 0);
	flush_cpu_dcache();
	flush_l2_cache();
	for (unsigned int pass = 0; pass < 2; pass++) {
		sum = 0;
		start = cycles();
		for (unsigned int i = 0; i < words; i += 8) {
			sum += buffer[i+0]; sum += buffer[i+1];
			sum += buffer[i+2]; sum += buffer[i+3];
			sum += buffer[i+4]; sum += buffer[i+5];
			sum += buffer[i+6]; sum += buffer[i+7];
		}
		elapsed = cycles() - start;
		if (sum != (uint32_t)(words*0x12345678u)) {
			printf("BENCH_ERROR,read_checksum\n");
			return;
		}
		report(pass ? "read_repeat" : "read_cold", words*4, words, elapsed, sum);
	}
}

static void chase(unsigned int words)
{
	unsigned int nodes = words/16;
	uint32_t start, elapsed, index = 0;

	/* One dependent load per 64-byte node; odd stride visits every node. */
	for (unsigned int i = 0; i < nodes; i++)
		buffer[i*16] = ((i+17) & (nodes-1))*16;
	for (unsigned int i = 0; i < nodes; i++) {
		if (buffer[i*16] != ((i+17) & (nodes-1))*16) {
			printf("BENCH_ERROR,chase_setup\n");
			return;
		}
	}
	flush_cpu_dcache();
	flush_l2_cache();
	start = cycles();
	for (unsigned int i = 0; i < 8192; i++)
		index = buffer[index];
	elapsed = cycles() - start;
	result = index;
	if (index != 0)
		printf("BENCH_ERROR,chase_checksum\n");
	report("chase", words*4, 8192, elapsed, index);
}

int main(void)
{
	irq_setie(0);
	irq_setmask(0);
	uart_init();
#ifdef CSR_SDRAM_BASE
	if (!sdram_init()) {
		printf("BENCH_ERROR,sdram_init\n");
		goto done;
	}
#endif
	printf("BENCH_BEGIN\n");
	for (unsigned int round = 0; round < ROUNDS; round++) {
		uint32_t value = 1;
		uint32_t start = cycles();
		uint32_t elapsed = cycles() - start;
		report("overhead", 0, 0, elapsed, 0);
		start = cycles();
		for (unsigned int i = 0; i < 32768; i++) {
			__asm__ volatile("" : "+r"(value));
			value = value*1664525u + 1013904223u;
		}
		elapsed = cycles() - start;
		result = value;
		if (value != 0x1c348001)
			printf("BENCH_ERROR,compute_checksum\n");
		report("compute", 0, 32768, elapsed, value);
		sequential(256);
		sequential(WORDS);
		chase(256);
		chase(WORDS);
	}
	printf("BENCH_DONE\n");
#ifdef CSR_SDRAM_BASE
done:
#endif
	uart_sync();
	bench_finish_write(1);
	while (1);
	return 0;
}
