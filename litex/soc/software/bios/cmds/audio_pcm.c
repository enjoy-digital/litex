// SPDX-License-Identifier: BSD-2-Clause

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <generated/csr.h>
#include <generated/soc.h>

#include "audio_controls.h"

#if defined(AUDIO_HAS_PCM) && !defined(BIOS_CONSOLE_DISABLE)
#define AUDIO_MAX_TONE_MS 10000

static bool audio_pcm_write(uint64_t frame)
{
	/* Bound the wait if the audio clock or FIFO stops. */
	for (unsigned int retries = 0; retries < 100000; retries++) {
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

static void audio_tone(char **args)
{
	unsigned long hz = tone_arg(args[0]);
	unsigned long ms = tone_arg(args[1]);

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
	uint32_t count = ms * CONFIG_AUDIO_PCM_RATE / 1000;
	uint32_t fade = CONFIG_AUDIO_PCM_RATE / 200;
	if (fade > count / 2)
		fade = count / 2;
	uint32_t step = ((uint64_t)hz << 32) / CONFIG_AUDIO_PCM_RATE;
	uint32_t phase = 0;
	unsigned int width = 16;
#ifdef CSR_AUDIO_WORD_SIZE_ADDR
	width = audio_word_size_read();
#endif
	uint64_t mask = (UINT64_C(1) << width) - 1;

#ifdef CSR_AUDIO_TONE_ADDR
	audio_tone_write(0);
#endif
#ifdef CSR_AUDIO_LOOPBACK_ADDR
	audio_loopback_write(0);
#endif
	for (uint32_t i = 0; i < count; i++, phase += step) {
		int32_t position = phase >> 20;
		int32_t sample = (position < 2048 ? position : 4095 - position) - 1024;
		uint32_t edge = i < count - 1 - i ? i : count - 1 - i;
		if (edge < fade)
			sample = sample * (int32_t)edge / (int32_t)fade;
		/* Scale the signed triangle to the configured PCM word width. */
		int64_t scaled = width >= 14 ? (int64_t)sample * (1 << (width - 14))
					     : sample >> (14 - width);
		uint64_t word = (uint64_t)scaled & mask;
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
#endif
