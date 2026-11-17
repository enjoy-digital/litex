// SPDX-License-Identifier: BSD-2-Clause

#include <stdint.h>
#include <string.h>

#include <generated/soc.h>

#include <system.h>

#include <libbase/i2c.h>
#include <libbase/ssm2603.h>

#ifdef CONFIG_SSM2603_I2C_BUS

static bool ssm2603_initialized;

/* Index of the I2C bus of the codec, -1 when not found. */
static int ssm2603_bus(void)
{
	const struct i2c_dev *devices = get_i2c_devs();
	int i;

	for (i = 0; i < get_i2c_devs_count(); i++)
		if (!strcmp(devices[i].name, CONFIG_SSM2603_I2C_BUS))
			return i;
	return -1;
}

/* Write a 9-bit register: 7-bit address then data, the I2C bus of the codec is active. */
static bool ssm2603_write_register(unsigned int reg, unsigned int value)
{
	uint8_t data = value & 0xff;

	return i2c_write(CONFIG_SSM2603_I2C_ADDRESS, (reg << 1) | (value >> 8), &data, 1, 1);
}

/* Write a register, selecting the I2C bus of the codec for the access. */
static bool ssm2603_write(unsigned int reg, unsigned int value)
{
	int bus = ssm2603_bus();
	int previous;
	bool ok;

	if (bus < 0)
		return false;

	previous = get_i2c_active_dev();
	set_i2c_active_dev(bus);
	ok = ssm2603_write_register(reg, value);
	set_i2c_active_dev(previous);
	return ok;
}

/* Power-up sequence of the codec. */
bool ssm2603_init(void)
{
	static const struct {
		unsigned int reg, value, delay_us;
	} sequence[] = {
		/* Mute DAC before disabling output. */
		{ SSM2603_DIGITAL_PATH_REG,     SSM2603_DIGITAL_PATH_DACMU, 2000 },
		{ SSM2603_POWER_REG,            0x012,                      0 },
		{ SSM2603_ACTIVE_REG,           0x000,                      0 },
		{ SSM2603_LEFT_ADC_VOLUME_REG,  0x017,                      0 },
		{ SSM2603_RIGHT_ADC_VOLUME_REG, 0x017,                      0 },
		{ SSM2603_LEFT_DAC_VOLUME_REG,  CONFIG_SSM2603_OUTPUT_GAIN, 0 },
		{ SSM2603_RIGHT_DAC_VOLUME_REG, CONFIG_SSM2603_OUTPUT_GAIN, 0 },
		{ SSM2603_ANALOG_PATH_REG,      0x012,                      0 },
		{ SSM2603_INTERFACE_REG,        CONFIG_SSM2603_INTERFACE,   0 },
		{ SSM2603_SAMPLING_REG,         CONFIG_SSM2603_SAMPLING,    CONFIG_SSM2603_VMID_DELAY_US },
		{ SSM2603_ACTIVE_REG,           0x001,                      0 },
		/* Let the output settle before unmuting. */
		{ SSM2603_POWER_REG,            0x002,                      10000 },
		{ SSM2603_DIGITAL_PATH_REG,     0x000,                      0 },
	};
	int bus = ssm2603_bus();
	int previous;
	unsigned int i;
	bool ok = true;

	if (bus < 0)
		return false;

	previous = get_i2c_active_dev();
	set_i2c_active_dev(bus);
	for (i = 0; i < sizeof(sequence) / sizeof(sequence[0]); i++) {
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

/* Restart playback at the default gain. */
bool ssm2603_restart(void)
{
	int bus;
	int previous;
	bool ok;

	/* A warm restart leaves the analog bias and serial interface running.
	 * Cycling them is needed at power-up and can create a transient. */
	if (!ssm2603_initialized)
		return ssm2603_init();

	bus = ssm2603_bus();
	if (bus < 0)
		return false;

	previous = get_i2c_active_dev();
	set_i2c_active_dev(bus);
	ok = ssm2603_write_register(SSM2603_DIGITAL_PATH_REG, SSM2603_DIGITAL_PATH_DACMU);
	if (ok) {
		busy_wait_us(2000);
		ok = ssm2603_write_register(SSM2603_LEFT_DAC_VOLUME_REG,
			SSM2603_DAC_VOLUME_BOTH | CONFIG_SSM2603_OUTPUT_GAIN);
	}
	if (ok)
		ok = ssm2603_write_register(SSM2603_DIGITAL_PATH_REG, 0x000);
	set_i2c_active_dev(previous);
	return ok;
}

/* Set the output gain of both channels, in dB (not checked against the range of the codec). */
bool ssm2603_set_volume(int db)
{
	return ssm2603_write(SSM2603_LEFT_DAC_VOLUME_REG,
		SSM2603_DAC_VOLUME_BOTH | (SSM2603_DAC_VOLUME_0DB + db));
}

/* Soft-mute or unmute the DAC. */
bool ssm2603_set_mute(bool mute)
{
	return ssm2603_write(SSM2603_DIGITAL_PATH_REG, mute ? SSM2603_DIGITAL_PATH_DACMU : 0);
}

#endif /* CONFIG_SSM2603_I2C_BUS */
