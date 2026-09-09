// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>
#include <generated/soc.h>

#include <libliteeth/mdio.h>
#include <libliteeth/udp.h>
#include <libliteeth/sfp.h>

#include "../command.h"
#include "../helpers.h"
#include "../boot.h"

/**
 * Command "mdio_write"
 *
 * Write MDIO register
 *
 */
#ifdef CSR_ETHPHY_MDIO_W_ADDR
static void mdio_write_handler(int nb_params, char **params)
{
	char *c;
	unsigned int phyadr2;
	unsigned int reg2;
	unsigned int val2;

	if (nb_params < 3) {
		printf("mdio_write <phyadr> <reg> <value>\n");
		return;
	}

	phyadr2 = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid phyadr\n");
		return;
	}

	reg2 = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Error: invalid reg\n");
		return;
	}

	val2 = strtoul(params[2], &c, 0);
	if (*c != 0) {
		printf("Error: invalid value\n");
		return;
	}

	printf("MDIO write @0x%x: 0x%02x 0x%04x\n", phyadr2, reg2, val2);
	mdio_write(phyadr2, reg2, val2);
}

define_command(mdio_write, mdio_write_handler, "Write MDIO register", LITEETH_CMDS);
#endif

/**
 * Command "mdio_read"
 *
 * Read MDIO register
 *
 */
#ifdef CSR_ETHPHY_MDIO_W_ADDR
static void mdio_read_handler(int nb_params, char **params)
{
	char *c;
	unsigned int phyadr2;
	unsigned int reg2;
	unsigned int val;

	if (nb_params < 2) {
		printf("mdio_read <phyadr> <reg>\n");
		return;
	}

	phyadr2 = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid phyadr\n");
		return;
	}

	reg2 = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Error: invalid reg\n");
		return;
	}

	printf("MDIO read @0x%x:\n", phyadr2);
	val = mdio_read(phyadr2, reg2);
	printf("0x%02x 0x%04x\n", reg2, val);
}

define_command(mdio_read, mdio_read_handler, "Read MDIO register", LITEETH_CMDS);
#endif

/**
 * Command "mdio_dump"
 *
 * Dump MDIO registers
 *
 */
#ifdef CSR_ETHPHY_MDIO_W_ADDR
static void mdio_dump_handler(int nb_params, char **params)
{
	char *c;
	unsigned int phyadr;
	unsigned int count;
	unsigned int val;
	int i;

	if (nb_params < 2) {
		printf("mdio_dump <phyadr> <count>\n");
		return;
	}

	phyadr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid phyadr\n");
		return;
	}

	count = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Error: invalid count\n");
		return;
	}
	/* MDIO register space is 5-bit */
	if (count > 32) {
		printf("Clamping count to the 32-register MDIO space\n");
		count = 32;
	}

	printf("MDIO dump @0x%x:\n", phyadr);
	for (i = 0; i < count; i++) {
		val = mdio_read(phyadr, i);
		printf("0x%02x 0x%04x\n", i, val);
	}
}

define_command(mdio_dump, mdio_dump_handler, "Dump MDIO registers", LITEETH_CMDS);
#endif

/**
 * Command "eth_local_ip"
 *
 * Set local ip
 *
 */
#ifdef ETH_DYNAMIC_IP
static void eth_local_ip_handler(int nb_params, char **params)
{
	if (nb_params < 1) {
		printf("eth_local_ip <address>\n");
		return;
	}

	set_local_ip(params[0]);
}
define_command(eth_local_ip, eth_local_ip_handler, "Set the local IP address", LITEETH_CMDS);
#endif

/**
 * Command "eth_remote_ip"
 *
 * Set remote ip.
 *
 */
#ifdef ETH_DYNAMIC_IP
static void eth_remote_ip_handler(int nb_params, char **params)
{
	if (nb_params < 1) {
		printf("eth_remote_ip <address>\n");
		return;
	}

	set_remote_ip(params[0]);
}
define_command(eth_remote_ip, eth_remote_ip_handler, "Set the remote IP address", LITEETH_CMDS);
#endif

/**
 * Command "eth_mac_addr"
 *
 * Set mac address.
 *
 */
#ifdef ETH_DYNAMIC_IP
static void eth_mac_addr_handler(int nb_params, char **params)
{
	if (nb_params < 1) {
		printf("eth_mac_addr <address>\n");
		return;
	}

	set_mac_addr(params[0]);
}
define_command(eth_mac_addr, eth_mac_addr_handler, "Set the MAC address", LITEETH_CMDS);
#endif

#ifdef ETH_WITH_DHCP
static void eth_dhcp_handler(int nb_params, char **params)
{
	dhcp_get_ip();
}
define_command(eth_dhcp, eth_dhcp_handler, "Get local IP address from DHCP", LITEETH_CMDS);
#endif

#ifdef ETH_DYNAMIC_IP
static void eth_ping_handler(int nb_params, char **params)
{
	if (nb_params != 1) {
		printf("ping <address>\n");
		return;
	}

	unsigned ip_[4];
	unsigned ip = 0;
	if (parse_ip(params[0], ip_) != 0)
		return;
	ip = IPTOINT(ip_[0], ip_[1], ip_[2], ip_[3]);

	if (send_ping(ip, 32) < 0)
		printf("Error: failed to send ping request\n");
}
define_command(ping, eth_ping_handler, "Ping the given IP address", LITEETH_CMDS);
#endif

/**
 * Command "sfp"
 *
 * Show each configured SFP+ cage, or set one to a host-side interface.
 *
 */
#if defined(CONFIG_HAS_I2C) && (defined(CONFIG_SFP_0_I2C) || defined(CONFIG_SFP_ROLLBALL_I2C))

static const struct sfp_cage *sfp_cage_arg(const char *s)
{
	char *c;
	unsigned long n = strtoul(s, &c, 0);
	if (*c != 0 || n >= sfp_cage_count) {
		printf("Cage must be 0..%u\n", sfp_cage_count ? sfp_cage_count - 1 : 0);
		return NULL;
	}
	return &sfp_cages[n];
}

static void sfp_handler(int nb_params, char **params)
{
	const struct sfp_cage *cage;
	unsigned int c;
	uint32_t id;
	int family, mode;

	if (nb_params < 1) {
		for (c = 0; c < sfp_cage_count; c++) {
			cage = &sfp_cages[c];
			printf("%u: %-12s want %-9s ", c, cage->i2c_dev, cage->host_mode);
			if (sfp_probe(cage, &id, &family))
				printf("PHY 0x%08lx (%s)\n", (unsigned long)id,
				       sfp_family_name(family));
			else
				printf("no module\n");
		}
		printf("usage: sfp <cage> <mode>   modes: 10GBASER 5GBASER 5000BASEX 2500BASEX 1000BASEX\n");
		return;
	}
	cage = sfp_cage_arg(params[0]);
	if (cage == NULL)
		return;
	if (nb_params < 2) {
		printf("Specify a host mode\n");
		return;
	}
	mode = sfp_host_mode_from_name(params[1]);
	if (mode < 0) {
		printf("Unknown mode %s\n", params[1]);
		return;
	}
	printf("Setting %s to %s... ", cage->i2c_dev, sfp_host_mode_name(mode));
	printf(sfp_set_host_mode(cage, mode) ? "done\n" : "failed\n");
}
define_command(sfp, sfp_handler, "Show/set SFP+ cage host interface", LITEETH_CMDS);

/**
 * Command "sfp_mdio_read"
 *
 * Read a Clause 45 register through an SFP+ module.
 *
 */
static void sfp_mdio_read_handler(int nb_params, char **params)
{
	const struct sfp_cage *cage;
	char *c;
	unsigned int mmd, reg;
	int v;

	if (nb_params < 3) {
		printf("sfp_mdio_read <cage> <mmd> <reg>");
		return;
	}
	cage = sfp_cage_arg(params[0]);
	if (cage == NULL)
		return;
	mmd = strtoul(params[1], &c, 0);
	if (*c != 0) { printf("Incorrect mmd\n"); return; }
	reg = strtoul(params[2], &c, 0);
	if (*c != 0) { printf("Incorrect reg\n"); return; }
	if (!sfp_probe(cage, NULL, NULL)) { printf("No module\n"); return; }
	v = sfp_mdio_read(cage, mmd, reg);
	if (v < 0)
		printf("Read failed\n");
	else
		printf("%d.0x%04x = 0x%04x\n", mmd, reg, v);
}
define_command(sfp_mdio_read, sfp_mdio_read_handler, "Read Clause 45 register via SFP+", LITEETH_CMDS);

/**
 * Command "sfp_mdio_write"
 *
 * Write a Clause 45 register through an SFP+ module.
 *
 */
static void sfp_mdio_write_handler(int nb_params, char **params)
{
	const struct sfp_cage *cage;
	char *c;
	unsigned int mmd, reg, val;

	if (nb_params < 4) {
		printf("sfp_mdio_write <cage> <mmd> <reg> <value>");
		return;
	}
	cage = sfp_cage_arg(params[0]);
	if (cage == NULL)
		return;
	mmd = strtoul(params[1], &c, 0);
	if (*c != 0) { printf("Incorrect mmd\n"); return; }
	reg = strtoul(params[2], &c, 0);
	if (*c != 0) { printf("Incorrect reg\n"); return; }
	val = strtoul(params[3], &c, 0);
	if (*c != 0) { printf("Incorrect value\n"); return; }
	if (!sfp_probe(cage, NULL, NULL)) { printf("No module\n"); return; }
	printf(sfp_mdio_write(cage, mmd, reg, val) ? "OK\n" : "Write failed\n");
}
define_command(sfp_mdio_write, sfp_mdio_write_handler, "Write Clause 45 register via SFP+", LITEETH_CMDS);
#endif
