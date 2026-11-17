// SPDX-License-Identifier: BSD-2-Clause

#include <stdio.h>
#include <string.h>

#include "../command.h"
#include "audio_controls.h"

#if (defined(AUDIO_HAS_PCM) || defined(CONFIG_SSM2603_I2C_BUS)) && !defined(BIOS_CONSOLE_DISABLE)

/* Controls of the cores present in the design. */
static const struct audio_control *const audio_providers[] = {
#ifdef AUDIO_HAS_PCM
	audio_pcm_controls,
#endif
#ifdef CONFIG_SSM2603_I2C_BUS
	audio_ssm2603_controls,
#endif
};

#define AUDIO_PROVIDERS_COUNT (sizeof(audio_providers) / sizeof(audio_providers[0]))

/* List the controls with their arguments, help aligned on the longest one. */
static void audio_help(void)
{
	const struct audio_control *control;
	const char *separator;
	size_t width = 0;
	size_t length;
	unsigned int i;

	for (i = 0; i < AUDIO_PROVIDERS_COUNT; i++) {
		for (control = audio_providers[i]; control->name; control++) {
			length = strlen(control->name) + strlen(control->arguments) + !!*control->arguments;
			if (length > width)
				width = length;
		}
	}

	for (i = 0; i < AUDIO_PROVIDERS_COUNT; i++) {
		for (control = audio_providers[i]; control->name; control++) {
			separator = *control->arguments ? " " : "";
			length    = strlen(control->name) + strlen(separator) + strlen(control->arguments);
			printf("audio %s%s%s%*s%s\n", control->name, separator, control->arguments,
				(int)(width - length + 2), "", control->help);
		}
	}
}

/**
 * Command "audio"
 *
 * Control audio playback and codec settings, list the available controls without argument.
 *
 */
static void audio_handler(int nb_params, char **params)
{
	const struct audio_control *control;
	unsigned int i;

	if (nb_params == 0) {
		audio_help();
		return;
	}

	for (i = 0; i < AUDIO_PROVIDERS_COUNT; i++) {
		for (control = audio_providers[i]; control->name; control++) {
			if (!strcmp(params[0], control->name)) {
				if (nb_params - 1 == control->argc)
					control->run(params + 1);
				else
					printf("Usage: audio %s%s%s\n", control->name,
						*control->arguments ? " " : "", control->arguments);
				return;
			}
		}
	}
	puts("Unsupported audio control. Run audio to list available controls.");
}
define_command_args(audio, audio_handler, "Control audio playback and codec settings",
	"audio [control [arguments]]", 0, MAX_PARAM, SYSTEM_CMDS);

#endif /* (AUDIO_HAS_PCM || CONFIG_SSM2603_I2C_BUS) && !BIOS_CONSOLE_DISABLE */
