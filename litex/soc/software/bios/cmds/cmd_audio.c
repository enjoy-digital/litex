// SPDX-License-Identifier: BSD-2-Clause

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#include <generated/csr.h>
#include <generated/soc.h>

#include <libbase/ssm2603.h>

#include "../command.h"
#include "../init.h"

/* PCM playback from the BIOS needs the PCM core named "audio" and its sample rate. */
#if defined(CONFIG_AUDIO_PCM_RATE) && defined(CSR_AUDIO_SAMPLE_ADDR) && defined(CSR_AUDIO_READY_ADDR)
#define AUDIO_HAS_PCM
#endif

/**
 * SSM2603 initialization
 *
 * Configure the codec at startup.
 *
 */
#ifdef CONFIG_SSM2603_I2C_BUS
static void ssm2603_init_handler(void)
{
	if (!ssm2603_init())
		puts("SSM2603 initialization failed.");
}
define_init_func(ssm2603_init_handler);
#endif

#if (defined(AUDIO_HAS_PCM) || defined(CONFIG_SSM2603_I2C_BUS)) && !defined(BIOS_CONSOLE_DISABLE)

/**
 * Control "tone"
 *
 * Play a triangle-wave tone through the PCM playback FIFO.
 *
 */
#ifdef AUDIO_HAS_PCM

#define AUDIO_MAX_TONE_MS 10000

static bool audio_pcm_write(uint64_t frame)
{
	unsigned int retries;

	/* Bound the wait if the audio clock or FIFO stops. */
	for (retries = 0; retries < 100000; retries++) {
		if (audio_ready_read()) {
			audio_sample_write(frame);
			return true;
		}
	}
	return false;
}

static unsigned long audio_tone_arg(const char *arg)
{
	char *end;
	unsigned long value = strtoul(arg, &end, 10);

	return *arg >= '0' && *arg <= '9' && !*end ? value : 0;
}

static void audio_tone_handler(char **params)
{
	unsigned long hz = audio_tone_arg(params[0]);
	unsigned long ms = audio_tone_arg(params[1]);
	uint32_t count;
	uint32_t fade;
	uint32_t step;
	uint32_t phase = 0;
	uint32_t i;
	uint32_t edge;
	int32_t position;
	int32_t sample;
	int64_t scaled;
	uint64_t word;
	uint64_t mask;
	unsigned int width = 16;

	if (hz < 20 || hz > CONFIG_AUDIO_PCM_RATE / 4 || ms < 1 || ms > AUDIO_MAX_TONE_MS) {
		printf("Use %u-%u Hz and 1-%u ms.\n", 20u, CONFIG_AUDIO_PCM_RATE / 4u,
			AUDIO_MAX_TONE_MS);
		return;
	}

#ifdef CSR_AUDIO_PLAYBACK_DMA_ENABLE_ADDR
	if (audio_playback_dma_enable_read()) {
		puts("Disable playback DMA before playing a BIOS tone.");
		return;
	}
#endif

	count = ms * CONFIG_AUDIO_PCM_RATE / 1000;
	fade  = CONFIG_AUDIO_PCM_RATE / 200;
	if (fade > count / 2)
		fade = count / 2;
	step = ((uint64_t)hz << 32) / CONFIG_AUDIO_PCM_RATE;
#ifdef CSR_AUDIO_WORD_SIZE_ADDR
	width = audio_word_size_read();
#endif
	mask = (UINT64_C(1) << width) - 1;

#ifdef CSR_AUDIO_TONE_ADDR
	audio_tone_write(0);
#endif
#ifdef CSR_AUDIO_LOOPBACK_ADDR
	audio_loopback_write(0);
#endif
	for (i = 0; i < count; i++, phase += step) {
		/* Triangle from the 12 upper bits of the phase, with a linear fade in/out. */
		position = phase >> 20;
		sample   = (position < 2048 ? position : 4095 - position) - 1024;
		edge     = i < count - 1 - i ? i : count - 1 - i;
		if (edge < fade)
			sample = sample * (int32_t)edge / (int32_t)fade;
		/* Scale the signed triangle to the configured PCM word width. */
		scaled = width >= 14 ? (int64_t)sample * (1 << (width - 14))
				     : sample >> (14 - width);
		word   = (uint64_t)scaled & mask;
		if (!audio_pcm_write((word << width) | word)) {
			puts("Audio PCM FIFO timed out.");
			return;
		}
	}
	printf("Queued %lu Hz for %lu ms.\n", hz, ms);
}
#endif

#ifdef CONFIG_SSM2603_I2C_BUS
/**
 * Control "volume"
 *
 * Set the output gain of both channels, in dB.
 *
 */
static void audio_volume_handler(char **params)
{
	char *end;
	bool negative = params[0][0] == '-';
	const char *digits = params[0] + (negative || params[0][0] == '+');
	unsigned long magnitude = strtoul(digits, &end, 10);
	int db;

	if (*digits < '0' || *digits > '9' || *end ||
	    magnitude > (negative ? -SSM2603_DAC_VOLUME_MIN_DB : SSM2603_DAC_VOLUME_MAX_DB)) {
		puts("Volume must be an integer from -73 to +6 dB.");
		return;
	}
	db = negative ? -(int)magnitude : (int)magnitude;
	if (ssm2603_set_volume(db))
		printf("Output gain set to %d dB.\n", db);
	else
		puts("Codec volume write failed.");
}

/**
 * Controls "mute" and "unmute"
 *
 * Soft-mute or unmute the DAC.
 *
 */
static void audio_set_mute(bool mute)
{
	if (ssm2603_set_mute(mute))
		puts(mute ? "Audio muted." : "Audio unmuted.");
	else
		puts("Codec mute write failed.");
}

static void audio_mute_handler(char **params)
{
	audio_set_mute(true);
}

static void audio_unmute_handler(char **params)
{
	audio_set_mute(false);
}

/**
 * Control "restart"
 *
 * Restart playback at the default gain.
 *
 */
static void audio_restart_handler(char **params)
{
	if (ssm2603_restart())
		puts("Codec restarted with the design's default gain.");
	else
		puts("Codec restart failed.");
}
#endif

/**
 * Command "audio"
 *
 * Control audio playback and codec settings, list the available controls without argument.
 *
 */
struct audio_control {
	const char *name;
	const char *arguments;
	const char *help;
	unsigned int argc;
	void (*run)(char **params);
};

/* Controls of the cores present in the design. */
static const struct audio_control audio_controls[] = {
#ifdef AUDIO_HAS_PCM
	{ "tone",    "<Hz> <ms>", "Play a triangle-wave tone.",               2, audio_tone_handler    },
#endif
#ifdef CONFIG_SSM2603_I2C_BUS
	{ "volume",  "<dB>",      "Set both output channels (-73 to +6 dB).", 1, audio_volume_handler  },
	{ "mute",    "",          "Soft-mute the DAC.",                       0, audio_mute_handler    },
	{ "unmute",  "",          "Unmute the DAC.",                          0, audio_unmute_handler  },
	{ "restart", "",          "Restart playback at the default gain.",    0, audio_restart_handler },
#endif
	{ 0 },
};

/* List the controls with their arguments, help aligned on the longest one. */
static void audio_help(void)
{
	const struct audio_control *control;
	const char *separator;
	size_t width = 0;
	size_t length;

	for (control = audio_controls; control->name; control++) {
		length = strlen(control->name) + strlen(control->arguments) + !!*control->arguments;
		if (length > width)
			width = length;
	}

	for (control = audio_controls; control->name; control++) {
		separator = *control->arguments ? " " : "";
		length    = strlen(control->name) + strlen(separator) + strlen(control->arguments);
		printf("audio %s%s%s%*s%s\n", control->name, separator, control->arguments,
			(int)(width - length + 2), "", control->help);
	}
}

static void audio_handler(int nb_params, char **params)
{
	const struct audio_control *control;

	if (nb_params == 0) {
		audio_help();
		return;
	}

	for (control = audio_controls; control->name; control++) {
		if (!strcmp(params[0], control->name)) {
			if (nb_params - 1 == control->argc)
				control->run(params + 1);
			else
				printf("Usage: audio %s%s%s\n", control->name,
					*control->arguments ? " " : "", control->arguments);
			return;
		}
	}
	puts("Unsupported audio control. Run audio to list available controls.");
}
define_command_args(audio, audio_handler, "Control audio playback and codec settings",
	"audio [control [arguments]]", 0, MAX_PARAM, SYSTEM_CMDS);

#endif /* (AUDIO_HAS_PCM || CONFIG_SSM2603_I2C_BUS) && !BIOS_CONSOLE_DISABLE */
