// SPDX-License-Identifier: BSD-2-Clause

#ifndef __BIOS_AUDIO_CONTROLS_H
#define __BIOS_AUDIO_CONTROLS_H

#include <generated/csr.h>
#include <generated/soc.h>

#if defined(CONFIG_AUDIO_PCM_RATE) && defined(CSR_AUDIO_SAMPLE_ADDR) && defined(CSR_AUDIO_READY_ADDR)
#define AUDIO_HAS_PCM
#endif

struct audio_control {
	const char *name;
	const char *arguments;
	const char *help;
	unsigned int argc;
	void (*run)(char **args);
};

extern const struct audio_control audio_pcm_controls[];
extern const struct audio_control audio_ssm2603_controls[];

#endif
