// This file is Copyright (c) 2020 Franck Jullien <franck.jullien@gmail.com>

// SPDX-License-Identifier: BSD-Source-Code

#ifndef __COMMAND_H__
#define __COMMAND_H__

#define MAX_PARAM	8

#define HIST_DEPTH	10	/* Used in string list, complete.c */

#define MISC_CMDS	0
#define SYSTEM_CMDS	1
#define CACHE_CMDS	2
#define BOOT_CMDS	3
#define DRAM_CMDS	4
#define MDIO_CMDS	5
#define MEM_CMDS	6
#define SD_CMDS		7
#define SPIFLASH_CMDS	8
#define DDR_CMDS	9
#define NB_OF_GROUPS	10

typedef void (*cmd_handler)(int nb_params, char **params);

struct command_struct {
	void (*func)(int nb_params, char **params);
	const char *name;
	const char *help;
	int group;
};

extern struct command_struct *const __bios_cmd_start[];
extern struct command_struct *const __bios_cmd_end[];

#define define_command(cmd_name, handler, help_txt, group_id) \
	struct command_struct s_##cmd_name = {					     \
		.func = (cmd_handler)handler,					     \
		.name = #cmd_name,						     \
		.help = help_txt,						     \
		.group = group_id,						     \
	};									     \
	const struct command_struct *__bios_cmd_##cmd_name __attribute__((__used__)) \
	__attribute__((__section__(".bios_cmd"))) = &s_##cmd_name


struct command_struct *command_dispatcher(char *command, int nb_params, char **params);

#endif
