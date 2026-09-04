// This file is Copyright (c) 2026 Scott Torborg <scott@quadraturecat.com>
// License: BSD

/*
 * RollBall SFP transceiver management.
 *
 * Copper SFP+ modules built around a Marvell Alaska PHY (88X3310, 88E2110 and relatives) expose
 * the PHY's Clause 45 MDIO through the module's SFF-8472 I2C interface: address 0x51, page 3,
 * a 0xffffffff password at offset 123, then a command window at offsets 0x80-0x85. This is the
 * "RollBall" protocol implemented by drivers/net/mdio/mdio-i2c.c in Linux.
 *
 * These modules default to pinning the host serdes at 10.3125Gb/s and rate-adapting whatever
 * the copper negotiated. The PHY can instead be told to follow the copper speed on the host
 * side ("MACTYPE"), which at 5GBASE-T means presenting 5GBASE-R.
 *
 * The setting is volatile: a module power cycle restores the factory default, so the
 * BIOS re-applies it at boot when CONFIG_SFP_ROLLBALL_MACTYPE is defined.
 *
 * All functions use the currently selected libbase I2C device (see sfp_rollball_select).
 * Cages behind a PCA954x-style I2C mux are supported: select the channel with
 * sfp_rollball_select_mux, or configure it (below) and use sfp_rollball_open.
 *
 * SoC configuration (add_config):
 *   SFP_ROLLBALL_I2C         name of the I2C master reaching the cage (enables this module)
 *   SFP_ROLLBALL_MUX_ADDR    optional: address of a PCA954x mux in front of the cage
 *   SFP_ROLLBALL_MUX_CHANNEL optional: its channel (0-7) for the cage
 *   SFP_ROLLBALL_MACTYPE     optional: host mode to apply at boot
 */

#ifndef __LIBLITEETH_SFP_ROLLBALL_H
#define __LIBLITEETH_SFP_ROLLBALL_H

#include <stdbool.h>
#include <stdint.h>

#define SFP_ROLLBALL_I2C_ADDR 0x51

/* Marvell Alaska MACTYPE values shared by the 88X3310 and 88E2110 families. */
#define SFP_ROLLBALL_MACTYPE_FOLLOW_COPPER 4   /* 10GBASE-R/5GBASE-R/2500BASE-X/SGMII follow copper speed */
#define SFP_ROLLBALL_MACTYPE_10G_RATE_MATCH 6  /* factory default: host pinned at 10GBASE-R */

/* Select the libbase I2C device by its CSR name (e.g. "sfp_i2c"). Returns false if unknown. */
bool sfp_rollball_select(const char *i2c_dev_name);

/* Route a PCA954x mux (single control-register byte) to the given channel. */
bool sfp_rollball_select_mux(uint8_t mux_addr, int channel);

/* Apply the configured device and mux (CONFIG_SFP_ROLLBALL_*). */
bool sfp_rollball_open(void);

/* True if a module answers at the RollBall address. */
bool sfp_rollball_present(void);

/* Send the RollBall password. Must precede any MDIO access after module power-up or reset. */
bool sfp_rollball_unlock(void);

/* Clause 45 access through the module. mdio_read returns -1 on failure. */
int  sfp_rollball_mdio_read(uint8_t mmd, uint16_t reg);
bool sfp_rollball_mdio_write(uint8_t mmd, uint16_t reg, uint16_t val);

/* MMD 1 device identifier, 0 on failure. */
uint32_t sfp_rollball_phy_id(void);

/* Host-interface mode ("MACTYPE", low 3 bits of the vendor port-control register).
 * get returns -1 on failure or unsupported PHY. set writes the mode, issues the PHY software
 * reset that applies it, and verifies the readback once the PHY is back. */
int  sfp_rollball_get_mactype(void);
bool sfp_rollball_set_mactype(int mactype);

/* Boot-time initialisation: apply CONFIG_SFP_ROLLBALL_MACTYPE on CONFIG_SFP_ROLLBALL_I2C,
 * retrying while the module boots. No-op unless both are defined. */
void sfp_rollball_init(void);

#endif /* __LIBLITEETH_SFP_ROLLBALL_H */
