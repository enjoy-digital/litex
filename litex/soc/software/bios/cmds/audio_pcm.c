// SPDX-License-Identifier: BSD-2-Clause

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include <generated/csr.h>
#include <generated/soc.h>

#include "audio_controls.h"

#if defined(AUDIO_HAS_PCM) && !defined(BIOS_CONSOLE_DISABLE)

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

static unsigned long tone_arg(const char *arg)
{
	char *end;
	unsigned long value = strtoul(arg, &end, 10);

	return *arg >= '0' && *arg <= '9' && !*end ? value : 0;
}

/**
 * Control "tone"
 *
 * Play a triangle-wave tone through the PCM playback FIFO.
 *
 */
static void audio_tone(char **args)
{
	unsigned long hz = tone_arg(args[0]);
	unsigned long ms = tone_arg(args[1]);
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

const struct audio_control audio_pcm_controls[] = {
	{ "tone", "<Hz> <ms>", "Play a triangle-wave tone.", 2, audio_tone },
	{ 0 },
};

#endif /* AUDIO_HAS_PCM && !BIOS_CONSOLE_DISABLE */
