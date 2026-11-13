// SPDX-License-Identifier: BSD-2-Clause

#include <stdio.h>
#include <string.h>

#include "../command.h"
#include "audio_controls.h"

#if (defined(AUDIO_HAS_PCM) || defined(CONFIG_SSM2603_I2C_BUS)) && !defined(BIOS_CONSOLE_DISABLE)
static const struct audio_control *const audio_providers[] = {
#ifdef AUDIO_HAS_PCM
	audio_pcm_controls,
#endif
#ifdef CONFIG_SSM2603_I2C_BUS
	audio_ssm2603_controls,
#endif
};

static void audio_help(void)
{
	size_t width = 0;

	for (unsigned int i = 0; i < sizeof(audio_providers) / sizeof(audio_providers[0]); i++) {
		for (const struct audio_control *control = audio_providers[i]; control->name; control++) {
			size_t length = strlen(control->name) + strlen(control->arguments) + !!*control->arguments;
			if (length > width)
				width = length;
		}
	}

	for (unsigned int i = 0; i < sizeof(audio_providers) / sizeof(audio_providers[0]); i++) {
		for (const struct audio_control *control = audio_providers[i]; control->name; control++) {
			const char *separator = *control->arguments ? " " : "";
			size_t length = strlen(control->name) + strlen(separator) + strlen(control->arguments);
			printf("audio %s%s%s%*s%s\n", control->name, separator, control->arguments,
				(int)(width - length + 2), "", control->help);
		}
	}
}

static void audio_handler(int argc, char **argv)
{
	if (argc == 0) {
		audio_help();
		return;
	}

	for (unsigned int i = 0; i < sizeof(audio_providers) / sizeof(audio_providers[0]); i++) {
		for (const struct audio_control *control = audio_providers[i]; control->name; control++) {
			if (!strcmp(argv[0], control->name)) {
				if (argc - 1 == control->argc)
					control->run(argv + 1);
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
#endif
