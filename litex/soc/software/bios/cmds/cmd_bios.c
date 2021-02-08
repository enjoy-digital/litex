// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>
#include <id.h>
#include <crc.h>
#include <system.h>
#include <sim_debug.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include "../command.h"
#include "../helpers.h"


#define DOT_VAL	0x80

static unsigned char hex_pos[8] = {
	0x01,
	0x02,
	0x04,
	0x08,
	0x10,
	0x20,
	0x40,
	0x80
};

static unsigned char hex_val[16]  = {
	(0x01 | 0x02 | 0x04 | 0x08 | 0x10 | 0x20),        // 0
	(0x02 | 0x04),                                    // 1
	(0x01 | 0x02 | 0x40 | 0x10 | 0x08),               // 2
	(0x01 | 0x02 | 0x04 | 0x08 | 0x40),               // 3
	(0x02 | 0x04 | 0x20 | 0x40),                      // 4
	(0x01 | 0x04 | 0x20 | 0x40 | 0x08),               // 5
	(0x01 | 0x04 | 0x08 | 0x10 | 0x20 | 0x40),        // 6
	(0x20 | 0x01 | 0x02 | 0x04),                      // 7
	(0x01 | 0x02 | 0x04 | 0x08 | 0x10 | 0x20 | 0x40), // 8
	(0x01 | 0x02 | 0x04 | 0x08 | 0x20 | 0x40),        // 9
	(0x01 | 0x02 | 0x04 | 0x10 | 0x20 | 0x40),        // A
	(0x04 | 0x08 | 0x10 | 0x20 | 0x40),               // B
	(0x01 | 0x08 | 0x10 | 0x20),                      // C
	(0x02 | 0x04 | 0x08 | 0x10 | 0x40),               // D
	(0x01 | 0x08 | 0x10 | 0x20 | 0x40),               // E
	(0x01 | 0x10 | 0x20 | 0x40),                      // F
};

volatile uint32_t ticks_per_delay = 8;
volatile uint32_t ticks_per_us = 100;

static void delay(unsigned int counts) {	// ticks based
	unsigned int i = counts;
	while(i--) {__asm__ volatile("nop");}
}

static void delay_ms(unsigned int counts) {	// mini second based
	unsigned int i = (1000 * counts * ticks_per_delay) / ticks_per_us;
	while(i--) {__asm__ volatile("nop");}
}

static void delay_us(unsigned int counts) {	// micro second based
	unsigned int i = (counts * ticks_per_delay) / ticks_per_us;
	while(i--) {__asm__ volatile("nop");}
}

/**
 * Command "help"
 *
 * Print a list of available commands with their help text
 *
 */
static void help_handler(int nb_params, char **params)
{
	struct command_struct * const *cmd;
	int i, not_empty;

	puts("\nLiteX BIOS, available commands:\n");

	for (i = 0; i < NB_OF_GROUPS; i++) {
		not_empty = 0;
		for (cmd = __bios_cmd_start; cmd != __bios_cmd_end; cmd++) {
			if ((*cmd)->group == i) {
				printf("%-24s - %s\n", (*cmd)->name, (*cmd)->help ? (*cmd)->help : "-");
				not_empty = 1;
			}
		}
		if (not_empty)
			printf("\n");
	}
}

define_command(help, help_handler, "Print this help", SYSTEM_CMDS);

/**
 * Command "ident"
 *
 * Identifier of the system
 *
 */
static void ident_handler(int nb_params, char **params)
{
	char buffer[IDENT_SIZE];

	get_ident(buffer);
	printf("Ident: %s", *buffer ? buffer : "-");
}

define_command(ident, ident_handler, "Identifier of the system", SYSTEM_CMDS);

static void delay_time_handler(int nb_params, char **params)
{
	char *c = NULL;
	volatile uint32_t start =0;
	volatile uint32_t end = 0;
	volatile uint32_t delay_counts = 0;
	volatile uint32_t tick_counts = 0;


	if (nb_params < 1) {
		printf("delay_time <value>");
		return;
	}

	delay_counts = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	timer0_en_write(0);
	timer0_reload_write(0);
	timer0_load_write(0xffffffff);
	timer0_en_write(1);

	timer0_update_value_write(1);
	start = timer0_value_read();

	delay(delay_counts);

	timer0_update_value_write(1);
	end = timer0_value_read();

	tick_counts = start - end;
	ticks_per_delay = tick_counts / delay_counts;
	ticks_per_us = CONFIG_CLOCK_FREQUENCY / 1000000;

	printf("CONFIG_CLOCK_FREQUENCY: %u\r\n", CONFIG_CLOCK_FREQUENCY);
	printf("delay time: %u\r\n", delay_counts);
	printf("start: %u\r\n", start);
	printf("end:   %u\r\n", end);
	printf("elapsed ticks: %u\r\n", tick_counts);
	printf("ticks per delay: %u\r\n", ticks_per_delay);
	printf("ticks per microsecond: %u\r\n", ticks_per_us);
}

define_command(delay_time, delay_time_handler, "delay time of the system", SYSTEM_CMDS);



/**
 * Command "uptime"
 *
 * Uptime of the system
 *
 */
#ifdef CSR_TIMER0_UPTIME_CYCLES_ADDR
static void uptime_handler(int nb_params, char **params)
{
	unsigned long uptime;

	timer0_uptime_latch_write(1);
	uptime = timer0_uptime_cycles_read();
	printf("Uptime: %ld sys_clk cycles / %ld seconds",
		uptime,
		uptime/CONFIG_CLOCK_FREQUENCY
	);
}

define_command(uptime, uptime_handler, "Uptime of the system since power-up", SYSTEM_CMDS);
#endif

/**
 * Command "crc"
 *
 * Compute CRC32 over an address range
 *
 */
static void crc_handler(int nb_params, char **params)
{
	char *c;
	uintptr_t addr;
	size_t length;

	if (nb_params < 2) {
		printf("crc <address> <length>");
		return;
	}

	addr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}

	length = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect length");
		return;
	}

	printf("CRC32: %08x", crc32((unsigned char *)addr, length));
}

define_command(crc, crc_handler, "Compute CRC32 of a part of the address space", SYSTEM_CMDS);

/**
 * Command "flush_cpu_dcache"
 *
 * Flush CPU data cache
 *
 */

define_command(flush_cpu_dcache, flush_cpu_dcache, "Flush CPU data cache", SYSTEM_CMDS);

/**
 * Command "flush_l2_cache"
 *
 * Flush L2 cache
 *
 */
#ifdef CONFIG_L2_SIZE
define_command(flush_l2_cache, flush_l2_cache, "Flush L2 cache", SYSTEM_CMDS);
#endif

/**
 * Command "leds"
 *
 * Set Leds value
 *
 */
#ifdef CSR_LEDS_BASE
static void leds_handler(int nb_params, char **params)
{
	char *c;
	unsigned int value;

	if (nb_params < 1) {
		printf("leds <value>");
		return;
	}

	value = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	printf("Settings Leds to 0x%x", value);
	leds_out_write(value);
}

define_command(leds, leds_handler, "Set Leds value", SYSTEM_CMDS);
#endif

#ifdef CSR_SEVEN_SEG_BASE
static void seven_seg_handler(int nb_params, char **params)
{
	char *c;
	volatile unsigned int seg_pos = 0;
	volatile unsigned int seg_val = 0;

	if (nb_params < 2) {
		printf("seven_seg <seg_pos> <seg_val>");
		return;
	}

	seg_pos = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}
	seg_pos = seg_pos & 0x07;
	seven_seg_ctl_out_write(hex_pos[seg_pos]);

	seg_val = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}
	seg_val = seg_val & 0x0f;
	seg_val = (seg_pos < 4) ? (hex_val[seg_val]) : ((hex_val[seg_val]) << 8);
	seven_seg_out_write(seg_val);

	printf("Settings Seg@%d to 0x%x", seg_pos, seg_val);
}

define_command(seven_seg, seven_seg_handler, "Set Seven Seg Leds value", SYSTEM_CMDS);

static void seven_seg_counter_handler(int nb_params, char **params)
{
	char *c;
	char count_str[8] = {0};
	volatile unsigned int i = 0;
	volatile unsigned int j = 0;
	volatile unsigned int val_start = 0;
	volatile unsigned int val_stop = 0;
	volatile unsigned int val_inc = 0;
	volatile unsigned int delay_ticks = 0;
	volatile unsigned int tmp_val = 0;
	volatile unsigned int count_dir = 0;
	volatile unsigned int count_val = 0;

	if (nb_params < 3) {
		printf("seven_seg <0 ==> count down, 1 ==> count up> <count_val> <delay_ticks>");
		return;
	}

	count_dir = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	count_val = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	delay_ticks = strtoul(params[2], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	delay_ticks = (delay_ticks > 1000000) ? 1000000 : delay_ticks;
	delay_ticks = (delay_ticks == 0) ? 10000 : delay_ticks;
	count_val = (count_val > 99999999) ? 99999999 : count_val;
	printf("Settings counter %s, value: %d, delay_ticks: %d\r\n\r\n", (count_dir == 0) ? "down" : "up", count_val, delay_ticks);

	if(count_dir == 0) {
		val_start = count_val;
		val_stop = 0;
		val_inc = 1;
		for(j = val_start; j > val_stop; j = j - val_inc) {
			sprintf(count_str, "%8d", j);
			for(i = 0; i < 8; i++) {
				if(count_str[i] != ' ') {
					tmp_val = count_str[i] - '0';
					tmp_val = (i < 4) ? (hex_val[tmp_val]) : ((hex_val[tmp_val]) << 8);
					seven_seg_ctl_out_write(hex_pos[i]);
					seven_seg_out_write(tmp_val);
					delay(delay_ticks);
				}
			}
		}
	} else {
		val_start = 0;
		val_stop = count_val;
		val_inc = 1;
		for(j = val_start; j <= val_stop; j = j + val_inc) {
			sprintf(count_str, "%8d", j);
			for(i = 0; i < 8; i++) {
				if(count_str[i] != ' ') {
					tmp_val = count_str[i] - '0';
					tmp_val = (i < 4) ? (hex_val[tmp_val]) : ((hex_val[tmp_val]) << 8);
					seven_seg_ctl_out_write(hex_pos[i]);
					seven_seg_out_write(tmp_val);
					delay(delay_ticks);
				}
			}
		}
	}
}

define_command(seven_seg_counter, seven_seg_counter_handler, "Seven Seg Leds Counter", SYSTEM_CMDS);
#endif

/**
 * Command "trace"
 *
 * Start/stop simulation trace dump.
 *
 */
#ifdef CSR_SIM_TRACE_BASE
static void cmd_sim_trace_handler(int nb_params, char **params)
{
  sim_trace(!sim_trace_enable_read());
}
define_command(trace, cmd_sim_trace_handler, "Toggle simulation tracing", SYSTEM_CMDS);
#endif

/**
 * Command "finish"
 *
 * Finish simulation.
 *
 */
#ifdef CSR_SIM_FINISH_BASE
static void cmd_sim_finish_handler(int nb_params, char **params)
{
  sim_finish();
}
define_command(finish, cmd_sim_finish_handler, "Finish simulation", SYSTEM_CMDS);
#endif

/**
 * Command "mark"
 *
 * Set a debug marker value
 *
 */
#ifdef CSR_SIM_MARKER_BASE
static void cmd_sim_mark_handler(int nb_params, char **params)
{
  // cannot use param[1] as it is not a const string
  sim_mark(NULL);
}
define_command(mark, cmd_sim_mark_handler, "Set a debug simulation marker", SYSTEM_CMDS);
#endif

#ifdef TERMINAL_BASE
static void vga_test_handler(int nb_params, char **params)
{
	char *c = NULL;
	volatile uint8_t input_val = 0;
	volatile uint8_t color_fg = 0;
	volatile uint8_t color_bg = 0;
	volatile uint8_t color = 0;
	volatile uint8_t* vga = (volatile uint32_t*)(TERMINAL_BASE);

	if (nb_params < 3) {
		printf("vga_test <ascii hex code> <foreground color> <background color>");
		return;
	}

	input_val = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	color_fg = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	color_bg = strtoul(params[2], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	color = ((color_bg & 0xF) << 4) | (color_fg & 0xF);

	for (int y = 0; y < 30; y++) {
		for (int x = 0; x < 80; x++) {
			vga[0] = (input_val & 0xFF);
			vga[1] = color;
			vga += 2;
		}
	}
}
define_command(vga_test, vga_test_handler, "VGA Test", SYSTEM_CMDS);
#endif

