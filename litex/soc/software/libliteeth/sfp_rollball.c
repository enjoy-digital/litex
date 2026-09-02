// This file is Copyright (c) 2026 Scott Torborg <scott@quadraturecat.com>
// License: BSD

#include <generated/csr.h>
#include <generated/soc.h>

#if defined(CONFIG_HAS_I2C) && defined(CONFIG_SFP_ROLLBALL_I2C)

#include <stdio.h>
#include <string.h>

#include <libbase/i2c.h>
#include <libliteeth/sfp_rollball.h>

/* RollBall transport (Linux drivers/net/mdio/mdio-i2c.c). */
#define RB_ADDR      SFP_ROLLBALL_I2C_ADDR
#define RB_PASSWORD  123      /* SFP_VSL (120) + 3, four 0xff bytes */
#define RB_PAGE      127      /* SFP page select */
#define RB_PAGE_MDIO 3
#define RB_CMD       0x80
#define RB_DATA      0x81
#define RB_CMD_WRITE 0x01
#define RB_CMD_READ  0x02
#define RB_CMD_DONE  0x04
#define RB_POLL_MS   20
#define RB_POLL_MAX  50       /* Linux allows ~10 x 20ms; some modules need well over that */

/* Marvell Alaska port-control registers. */
#define MV_ID_MASK            0xfffffff0
#define MV_ID_88X3310         0x002b09a0
#define MV_ID_88E2110         0x002b09b0
#define MV_V2_PORT_CTRL_MMD   31
#define MV_V2_PORT_CTRL_REG   0xf001   /* 88X3310 family */
#define MV_PMA_PORT_CTRL_MMD  1
#define MV_PMA_PORT_CTRL_REG  0xc04a   /* 88E2110 family */
#define MV_PORT_CTRL_MACTYPE  0x0007
#define MV_PORT_CTRL_SWRST    0x8000

void busy_wait(unsigned int ms);

/* I2C helpers ------------------------------------------------------------------------------- */

static bool rb_wr(uint8_t offset, const uint8_t *data, unsigned int len)
{
	return i2c_write(RB_ADDR, offset, data, len, 1);
}

static bool rb_rd(uint8_t offset, uint8_t *data, unsigned int len)
{
	return i2c_read(RB_ADDR, offset, data, len, false, 1);
}

bool sfp_rollball_select(const char *i2c_dev_name)
{
	struct i2c_dev *devs = get_i2c_devs();
	int i;
	for (i = 0; i < get_i2c_devs_count(); i++) {
		if (strcmp(devs[i].name, i2c_dev_name) == 0) {
			set_i2c_active_dev(i);
			return true;
		}
	}
	return false;
}

bool sfp_rollball_select_mux(uint8_t mux_addr, int channel)
{
	/* For configuring PCA954x I2C muxes as used on many OEM dev boards. */
	uint8_t mask = 1 << (channel & 7);
	return i2c_write(mux_addr, mask, NULL, 0, 1);
}

bool sfp_rollball_open(void)
{
	if (!sfp_rollball_select(CONFIG_SFP_ROLLBALL_I2C)) {
		printf("SFP RollBall: I2C device %s not found\n", CONFIG_SFP_ROLLBALL_I2C);
		return false;
	}
#if defined(CONFIG_SFP_ROLLBALL_MUX_ADDR) && defined(CONFIG_SFP_ROLLBALL_MUX_CHANNEL)
	if (!sfp_rollball_select_mux(CONFIG_SFP_ROLLBALL_MUX_ADDR, CONFIG_SFP_ROLLBALL_MUX_CHANNEL)) {
		printf("SFP RollBall: I2C mux 0x%02x did not answer\n", CONFIG_SFP_ROLLBALL_MUX_ADDR);
		return false;
	}
#endif
	return true;
}

bool sfp_rollball_present(void)
{
	return i2c_poll(RB_ADDR);
}

bool sfp_rollball_unlock(void)
{
	static const uint8_t password[4] = {0xff, 0xff, 0xff, 0xff};
	return rb_wr(RB_PASSWORD, password, sizeof(password));
}

static bool rb_select_page(uint8_t *saved)
{
	uint8_t page = RB_PAGE_MDIO;
	if (!rb_rd(RB_PAGE, saved, 1))
		return false;
	return rb_wr(RB_PAGE, &page, 1);
}

static void rb_restore_page(uint8_t saved)
{
	rb_wr(RB_PAGE, &saved, 1);
}

static bool rb_poll(uint8_t *buf, unsigned int len)
{
	int i;
	for (i = 0; i < RB_POLL_MAX; i++) {
		uint8_t saved;
		bool ok;
		busy_wait(RB_POLL_MS);
		if (!rb_select_page(&saved))
			return false;
		ok = rb_rd(RB_CMD, buf, len);
		rb_restore_page(saved);
		if (ok && buf[0] == RB_CMD_DONE)
			return true;
	}
	return false;
}

int sfp_rollball_mdio_read(uint8_t mmd, uint16_t reg)
{
	uint8_t saved;
	uint8_t data[3] = {mmd & 0x1f, reg >> 8, reg & 0xff};
	uint8_t cmd     = RB_CMD_READ;
	uint8_t buf[6];
	bool ok;

	if (!rb_select_page(&saved))
		return -1;
	ok = rb_wr(RB_DATA, data, sizeof(data)) && rb_wr(RB_CMD, &cmd, 1);
	rb_restore_page(saved);
	if (!ok || !rb_poll(buf, sizeof(buf)))
		return -1;
	return (buf[4] << 8) | buf[5];
}

bool sfp_rollball_mdio_write(uint8_t mmd, uint16_t reg, uint16_t val)
{
	uint8_t saved;
	uint8_t data[5] = {mmd & 0x1f, reg >> 8, reg & 0xff, val >> 8, val & 0xff};
	uint8_t cmd     = RB_CMD_WRITE;
	uint8_t buf[1];
	bool ok;

	if (!rb_select_page(&saved))
		return false;
	ok = rb_wr(RB_DATA, data, sizeof(data)) && rb_wr(RB_CMD, &cmd, 1);
	rb_restore_page(saved);
	return ok && rb_poll(buf, sizeof(buf));
}

uint32_t sfp_rollball_phy_id(void)
{
	int hi = sfp_rollball_mdio_read(1, 2);
	int lo = sfp_rollball_mdio_read(1, 3);
	if (hi < 0 || lo < 0)
		return 0;
	return ((uint32_t)hi << 16) | (uint32_t)lo;
}

/* MACTYPE ----------------------------------------------------------------------------------- */

/* Locate the port-control register for this PHY. */
static bool mv_port_ctrl(uint8_t *mmd, uint16_t *reg)
{
	uint32_t id = sfp_rollball_phy_id();
	int v;
	if (id == 0)
		return false;
	switch (id & MV_ID_MASK) {
	case MV_ID_88X3310:
		*mmd = MV_V2_PORT_CTRL_MMD; *reg = MV_V2_PORT_CTRL_REG;
		return true;
	case MV_ID_88E2110:
		*mmd = MV_PMA_PORT_CTRL_MMD; *reg = MV_PMA_PORT_CTRL_REG;
		return true;
	default:
		break;
	}
	v = sfp_rollball_mdio_read(MV_V2_PORT_CTRL_MMD, MV_V2_PORT_CTRL_REG);
	if (v < 0 || (v & ~(MV_PORT_CTRL_MACTYPE | MV_PORT_CTRL_SWRST | 0x0800)) != 0)
		return false;
	printf("SFP RollBall: unknown PHY ID 0x%08lx, assuming 88X3310-style port control\n",
	       (unsigned long)id);
	*mmd = MV_V2_PORT_CTRL_MMD; *reg = MV_V2_PORT_CTRL_REG;
	return true;
}

int sfp_rollball_get_mactype(void)
{
	uint8_t mmd; uint16_t reg; int v;
	if (!mv_port_ctrl(&mmd, &reg))
		return -1;
	v = sfp_rollball_mdio_read(mmd, reg);
	return v < 0 ? -1 : (v & MV_PORT_CTRL_MACTYPE);
}

bool sfp_rollball_set_mactype(int mactype)
{
	uint8_t mmd; uint16_t reg; int cur, i;
	uint16_t target;

	if (!mv_port_ctrl(&mmd, &reg))
		return false;
	cur = sfp_rollball_mdio_read(mmd, reg);
	if (cur < 0)
		return false;
	if ((cur & MV_PORT_CTRL_MACTYPE) == mactype)
		return true;

	target = (cur & ~MV_PORT_CTRL_MACTYPE) | (mactype & MV_PORT_CTRL_MACTYPE);
	if (!sfp_rollball_mdio_write(mmd, reg, target))
		return false;
	/* The software reset applies the new mode. Some firmware only shows the new value after
	 * it (Wiitek SFP-10G-T-X), and the transport drops while the PHY reboots, so the write's
	 * completion is not checked. */
	sfp_rollball_mdio_write(mmd, reg, target | MV_PORT_CTRL_SWRST);

	for (i = 0; i < 20; i++) {
		busy_wait(250);
		if (!sfp_rollball_present() || !sfp_rollball_unlock())
			continue;
		cur = sfp_rollball_mdio_read(mmd, reg);
		if (cur >= 0 && (cur & MV_PORT_CTRL_MACTYPE) == mactype)
			return true;
	}
	return false;
}

/* Boot-time initialization ------------------------------------------------------------------ */

void sfp_rollball_init(void)
{
#ifdef CONFIG_SFP_ROLLBALL_MACTYPE
	int attempt, saved_dev = get_i2c_active_dev();

	if (!sfp_rollball_open()) {
		set_i2c_active_dev(saved_dev);
		return;
	}
	/* A freshly powered module takes a few seconds to boot PHY firmware. */
	for (attempt = 1; attempt <= 15; attempt++) {
		uint32_t id;
		int cur;
		if (!sfp_rollball_present() || !sfp_rollball_unlock()) {
			busy_wait(1000);
			continue;
		}
		id = sfp_rollball_phy_id();
		if (id == 0) {
			busy_wait(1000);
			continue;
		}
		cur = sfp_rollball_get_mactype();
		printf("SFP RollBall: PHY ID 0x%08lx, MACTYPE %d", (unsigned long)id, cur);
		if (cur == CONFIG_SFP_ROLLBALL_MACTYPE) {
			printf(" (already set)\n");
			break;
		}
		printf(" -> %d: ", CONFIG_SFP_ROLLBALL_MACTYPE);
		if (sfp_rollball_set_mactype(CONFIG_SFP_ROLLBALL_MACTYPE)) {
			printf("done\n");
			break;
		}
		printf("failed\n");
		busy_wait(1000);
	}
	if (attempt > 15)
		printf("SFP RollBall: no module answered, giving up\n");
	set_i2c_active_dev(saved_dev);
#endif
}

#endif /* CONFIG_HAS_I2C && CONFIG_SFP_ROLLBALL_I2C */
