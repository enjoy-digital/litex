// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>
#include <memtest.h>

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

/**
 * Command "memtest"
 *
 * Run a memory test
 *
 */
static void memtest_handler(int nb_params, char **params)
{
	char *c;
	unsigned int *addr;
	unsigned long maxsize = ~0uL;

	if (nb_params < 1) {
		printf("memtest <addr> [<maxsize>]");
		return;
	}

	addr = (unsigned int *)strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}

	if (nb_params >= 2) {
		maxsize = strtoul(params[1], &c, 0);
		if (*c != 0) {
			printf("Incorrect max size");
			return;
		}

	}

	memtest(addr, maxsize);
}
define_command(memtest, memtest_handler, "Run a memory test", MEM_CMDS);

/**
 * Command "memspeed"
 *
 * Run a memory speed test
 *
 */
static void memspeed_handler(int nb_params, char **params)
{
	char *c;
	unsigned int *addr;
	unsigned long size;
	bool read_only = false;

	if (nb_params < 1) {
		printf("memspeed <addr> <size> [<readonly>]");
		return;
	}

	addr = (unsigned int *)strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}

	size = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect size");
		return;
	}

	if (nb_params >= 3) {
		read_only = (bool) strtoul(params[2], &c, 0);
		if (*c != 0) {
			printf("Incorrect readonly value");
			return;
		}
	}

	memspeed(addr, size, read_only);
}
define_command(memspeed, memspeed_handler, "Run a memory speed test", MEM_CMDS);

#ifdef CSR_DEBUG_PRINTER
/**
 * Command "csrprint"
 *
 * Print CSR values
 *
 */
static void csrprint(int nb_params, char **params)
{
    print_csrs();
}
define_command(csrprint, csrprint, "Print CSR values", MEM_CMDS);
#endif


#ifdef CSR_WB_SOFTCONTROL_BASE
static void wbr(int nb_params, char **params)
{
	char *c;
	unsigned int *addr;
	unsigned int length;
    unsigned int i;

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

    for (i = 0; i < length; ++i) {
        wb_softcontrol_adr_write((unsigned long)(addr + i));
        wb_softcontrol_read_write(1);
        printf("0x%08x: 0x%08x\n", (unsigned long)(addr + i), wb_softcontrol_data_read());
    }
}
define_command(wbr, wbr, "Read using softcontrol wishbone controller", MEM_CMDS);

static void wbw(int nb_params, char **params)
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

    wb_softcontrol_data_write(value);
	for (i = 0; i < count; i++) {
        wb_softcontrol_adr_write((unsigned long)(addr + i));
        wb_softcontrol_write_write(1);
    }
}
define_command(wbw, wbw, "Write using softcontrol wishbone controller", MEM_CMDS);
#endif
