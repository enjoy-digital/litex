// This file is Copyright (c) 2026 Scott Torborg <scott@quadraturecat.com>
// License: BSD

/*
 * Copper SFP+ transceiver host-interface management.
 *
 * A 10GBASE-T copper SFP+ module contains a twisted-pair PHY that negotiates a copper speed and
 * presents a serdes link on the SFP+ (host) side. By default nearly all of them pin the host at
 * 10.3125Gb/s and rate-adapt slower copper speeds up to it. It may be desirable to set a slower
 * host-side rate, e.g. for compatibility with slower transceivers or for clocking purposes. Some
 * transceivers have interfaces to change the PHY configuration over I2C, but compatibility is
 * limited and the details are vendor-specific.
 *
 * These SFP management functions attempt to abstract away the vendor differences and accomplish
 * a desired configuration. It is generally expected that these functions will not be called
 * directly, and will instead be configured for a given board using config definitions.
 *
 * Currently supported PHY families:
 *      Marvell Alaska M: e.g. 88X3310, 88E2110
 *      Aquantia AQR113C
 *
 * Not yet supported, but may be in the future:
 *      Broadcom BCM8489x
 *      Marvell CUX3610
 *
 * Everything set here is volatile: a module power cycle restores the factory default, so the
 * BIOS re-applies it at boot.
 *
 * A board declares each cage with two settings, plus two more if it sits behind an I2C mux:
 *
 *   self.add_config("SFP_0_I2C",         "sfp0_i2c")   # I2C master reaching the cage
 *   self.add_config("SFP_0_HOST_MODE",   "5GBASER")    # desired host interface
 *
 *   self.add_config("SFP_1_I2C",         "sfp1_i2c")
 *   self.add_config("SFP_1_HOST_MODE",   "2500BASEX")
 *   self.add_config("SFP_1_MUX_ADDR",    0x74)         # optional: PCA954x in front of the cage
 *   self.add_config("SFP_1_MUX_CHANNEL", 4)            # optional: its channel
 *
 * Available host modes:
 *      AUTO (default)
 *      10GBASER
 *      5GBASER
 *      5000BASEX
 *      2500BASEX
 *      1000BASEX
 *
 * Ommitting the HOST_MODE configures the SFP entry but leaves the module alone at boot.
 */

#ifndef __LIBLITEETH_SFP_H
#define __LIBLITEETH_SFP_H

#include <stdbool.h>
#include <stdint.h>

#define SFP_HOST_AUTO       0   /* leave default */
#define SFP_HOST_10GBASER   1
#define SFP_HOST_5GBASER    2
#define SFP_HOST_2500BASEX  3
#define SFP_HOST_1000BASEX  4
#define SFP_HOST_5000BASEX  5

/* Supported PHY families */
#define SFP_PHY_UNKNOWN  0
#define SFP_PHY_MARVELL  1   /* 88X3310, 88E2110 and relatives */
#define SFP_PHY_AQUANTIA 2   /* AQR113C and relatives */
#define SFP_PHY_BROADCOM 3   /* BCM84891L and relatives */

/* One SFP+ cage, built from the SFP_<n>_* configuration above. Boards do not write C. */
struct sfp_cage {
	const char *i2c_dev;     /* libbase I2C device name */
	uint8_t     mux_addr;    /* PCA954x address, 0 for none */
	uint8_t     mux_channel; /* its channel */
	const char *host_mode;   /* wanted mode, by name */
};

extern const struct sfp_cage sfp_cages[];
extern const unsigned int    sfp_cage_count;

/* Apply every cage's configured host mode. Called by the BIOS at boot. */
void sfp_init(void);

/* Identify the fitted PHY, and unlock it for the calls below. Either pointer may be NULL. */
bool sfp_probe(const struct sfp_cage *cage, uint32_t *phy_id, int *family);

/* Put the cage's host side into `mode`, by whatever means the fitted PHY requires. Also
 * constrains the copper advertisement, since the host rate follows the copper rate. */
bool sfp_set_host_mode(const struct sfp_cage *cage, int mode);

/* Clause 45 access through the module. Call sfp_probe() first. read returns -1 on failure. */
int  sfp_mdio_read(const struct sfp_cage *cage, uint8_t mmd, uint16_t reg);
bool sfp_mdio_write(const struct sfp_cage *cage, uint8_t mmd, uint16_t reg, uint16_t val);

/* Name <-> SFP_HOST_* mapping. from_name() returns -1 for an unknown name. */
int         sfp_host_mode_from_name(const char *name);
const char *sfp_host_mode_name(int mode);
const char *sfp_family_name(int family);

#endif /* __LIBLITEETH_SFP_H */
