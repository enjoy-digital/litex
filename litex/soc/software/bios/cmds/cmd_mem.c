// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "mr"
 *
 * Memory read
 *
 */
static void mr(int nb_params, char **params)
{
	char *c;
	unsigned int *addr;
	unsigned int length;

	if (nb_params < 1) {
		printf("mr <address> [length]");
		return;
	}
	addr = (unsigned int *)strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}
	if (nb_params == 1) {
		length = 4;
	} else {
		length = strtoul(params[1], &c, 0);
		if(*c != 0) {
			printf("\nIncorrect length");
			return;
		}
	}

	dump_bytes(addr, length, (unsigned long)addr);
}

define_command(mr, mr, "Read address space", MEM_CMDS);

/**
 * Command "mw"
 *
 * Memory write
 *
 */
static void mw(int nb_params, char **params)
{
	char *c;
	unsigned int *addr;
	unsigned int value;
	unsigned int count;
	unsigned int i;

	if (nb_params < 2) {
		printf("mw <address> <value> [count]");
		return;
	}

	addr = (unsigned int *)strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}

	value = strtoul(params[1], &c, 0);
	if(*c != 0) {
		printf("Incorrect value");
		return;
	}

	if (nb_params == 2) {
		count = 1;
	} else {
		count = strtoul(params[2], &c, 0);
		if(*c != 0) {
			printf("Incorrect count");
			return;
		}
	}

	for (i = 0; i < count; i++)
		*addr++ = value;
}

define_command(mw, mw, "Write address space", MEM_CMDS);

/**
 * Command "mc"
 *
 * Memory copy
 *
 */
static void mc(int nb_params, char **params)
{
	char *c;
	unsigned int *dstaddr;
	unsigned int *srcaddr;
	unsigned int count;
	unsigned int i;

	if (nb_params < 2) {
		printf("mc <dst> <src> [count]");
		return;
	}

	dstaddr = (unsigned int *)strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect destination address");
		return;
	}

	srcaddr = (unsigned int *)strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect source address");
		return;
	}

	if (nb_params == 2) {
		count = 1;
	} else {
		count = strtoul(params[2], &c, 0);
		if (*c != 0) {
			printf("Incorrect count");
			return;
		}
	}

	for (i = 0; i < count; i++)
		*dstaddr++ = *srcaddr++;
}

define_command(mc, mc, "Copy address space", MEM_CMDS);
