// SPDX-License-Identifier: BSD-2-Clause

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <system.h>
#include <libbase/i2c.h>

#include "../init.h"
#include "audio_controls.h"

#ifdef CONFIG_SSM2603_I2C_BUS
static int ssm2603_bus(void)
{
	const struct i2c_dev *devices = get_i2c_devs();

	for (int i = 0; i < get_i2c_devs_count(); i++)
		if (!strcmp(devices[i].name, CONFIG_SSM2603_I2C_BUS))
			return i;
	return -1;
}

static bool ssm2603_write_register(unsigned int reg, unsigned int value)
{
	uint8_t data = value & 0xff;

	return i2c_write(CONFIG_SSM2603_I2C_ADDRESS, (reg << 1) | (value >> 8), &data, 1, 1);
}

static bool ssm2603_initialized;

static bool ssm2603_start(void)
{
	static const struct {
		unsigned int reg, value, delay_us;
	} sequence[] = {
		{ 5, 0x008, 2000 }, /* Mute DAC before disabling output. */
		{ 6, 0x012, 0 },
		{ 9, 0x000, 0 },
		{ 0, 0x017, 0 },
		{ 1, 0x017, 0 },
		{ 2, CONFIG_SSM2603_OUTPUT_GAIN, 0 },
		{ 3, CONFIG_SSM2603_OUTPUT_GAIN, 0 },
		{ 4, 0x012, 0 },
		{ 7, CONFIG_SSM2603_INTERFACE, 0 },
		{ 8, CONFIG_SSM2603_SAMPLING, CONFIG_SSM2603_VMID_DELAY_US },
		{ 9, 0x001, 0 },
		{ 6, 0x002, 10000 }, /* Let the output settle before unmuting. */
		{ 5, 0x000, 0 },
	};
	int bus = ssm2603_bus();
	if (bus < 0)
		return false;

	int previous = get_i2c_active_dev();
	bool ok = true;

	set_i2c_active_dev(bus);
	for (unsigned int i = 0; i < sizeof(sequence) / sizeof(sequence[0]); i++) {
		if (!ssm2603_write_register(sequence[i].reg, sequence[i].value)) {
			ok = false;
			break;
		}
		if (sequence[i].delay_us)
			busy_wait_us(sequence[i].delay_us);
	}
	set_i2c_active_dev(previous);
	ssm2603_initialized = ok;
	return ok;
}

static void ssm2603_init(void)
{
	if (!ssm2603_start())
		puts("SSM2603 initialization failed.");
}
define_init_func(ssm2603_init);

#ifndef BIOS_CONSOLE_DISABLE
static bool ssm2603_write(unsigned int reg, unsigned int value)
{
	int bus = ssm2603_bus();
	if (bus < 0)
		return false;

	int previous = get_i2c_active_dev();
	set_i2c_active_dev(bus);
	bool ok = ssm2603_write_register(reg, value);
	set_i2c_active_dev(previous);
	return ok;
}

static void ssm2603_volume(char **args)
{
	char *end;
	bool negative = args[0][0] == '-';
	const char *digits = args[0] + (negative || args[0][0] == '+');
	unsigned long magnitude = strtoul(digits, &end, 10);

	if (*digits < '0' || *digits > '9' || *end || magnitude > (negative ? 73 : 6)) {
		puts("Volume must be an integer from -73 to +6 dB.");
		return;
	}
	int db = negative ? -(int)magnitude : (int)magnitude;
	/* Bit 8 applies the left output gain to both channels. */
	if (ssm2603_write(2, 0x100 | (0x79 + db)))
		printf("Output gain set to %d dB.\n", db);
	else
		puts("Codec volume write failed.");
}

static void ssm2603_set_mute(bool mute)
{
	if (ssm2603_write(5, mute ? 0x08 : 0))
		puts(mute ? "Audio muted." : "Audio unmuted.");
	else
		puts("Codec mute write failed.");
}

static void ssm2603_mute(char **args)
{
	ssm2603_set_mute(true);
}

static void ssm2603_unmute(char **args)
{
	ssm2603_set_mute(false);
}

static bool ssm2603_restart_playback(void)
{
	/* A warm restart leaves the analog bias and serial interface running.
	 * Cycling them is needed at power-up and can create a transient. */
	if (!ssm2603_initialized)
		return ssm2603_start();

	int bus = ssm2603_bus();
	if (bus < 0)
		return false;

	int previous = get_i2c_active_dev();
	set_i2c_active_dev(bus);
	bool ok = ssm2603_write_register(5, 0x008);
	if (ok) {
		busy_wait_us(2000);
		ok = ssm2603_write_register(2, 0x100 | CONFIG_SSM2603_OUTPUT_GAIN);
	}
	if (ok)
		ok = ssm2603_write_register(5, 0x000);
	set_i2c_active_dev(previous);
	return ok;
}

static void ssm2603_restart(char **args)
{
	if (ssm2603_restart_playback())
		puts("Codec restarted with the design's default gain.");
	else
		puts("Codec restart failed.");
}

const struct audio_control audio_ssm2603_controls[] = {
	{ "volume", "<dB>", "Set both output channels (-73 to +6 dB).", 1, ssm2603_volume },
	{ "mute", "", "Soft-mute the DAC.", 0, ssm2603_mute },
	{ "unmute", "", "Unmute the DAC.", 0, ssm2603_unmute },
	{ "restart", "", "Restart playback at the default gain.", 0, ssm2603_restart },
	{ 0 },
};
#endif
#endif
