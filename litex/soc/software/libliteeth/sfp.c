// This file is Copyright (c) 2026 Scott Torborg <scott@quadraturecat.com>
// License: BSD

#include <generated/csr.h>
#include <generated/soc.h>

#if defined(CONFIG_HAS_I2C) && defined(CONFIG_SFP_0_I2C)

#include <stdio.h>
#include <string.h>

#include <libbase/i2c.h>
#include <libliteeth/sfp.h>

/* RollBall transport (Linux drivers/net/mdio/mdio-i2c.c). */
#define RB_ADDR      0x51     /* SFF-8472 A2h */
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

/* Marvell Alaska port-control registers. MACTYPE 4 makes the host follow the copper rate;
 * 6 pins it at 10GBASE-R with rate matching. */
#define MV_ID_MASK            0xfffffff0
#define MV_ID_88X3310         0x002b09a0
#define MV_ID_88E2110         0x002b09b0
#define MV_V2_PORT_CTRL_MMD   31
#define MV_V2_PORT_CTRL_REG   0xf001   /* 88X3310 family */
#define MV_PMA_PORT_CTRL_MMD  1
#define MV_PMA_PORT_CTRL_REG  0xc04a   /* 88E2110 family */
#define MV_PORT_CTRL_MACTYPE  0x0007
#define MV_PORT_CTRL_SWRST    0x8000
#define MV_MACTYPE_FOLLOW     4
#define MV_MACTYPE_10G_MATCH  6

/* Aquantia/Marvell AQrate (AQR113C and relatives) system-interface registers.
 * The host serdes rate is chosen per copper rate by the VEND1 config registers:
 * 0x31b=100M 0x31c=1G 0x31d=2.5G 0x31e=5G 0x31f=10G. In each, bits [2:0] select the SERDES
 * mode and bits [8:7] the rate adaptation. The factory sub-10G entries are 0x0100, i.e.
 * pause-based rate adaptation up to a 10.3125Gb/s host; a native mode with no rate adaptation
 * gives the matching host rate instead. */
#define AQ_ID_MASK            0xfffffff0
#define AQ_ID_AQR113C         0x31c31c10

/* Broadcom ------------------------------------------------------------------------------------
 * The BCM84891L selects its host (XFI) encoding through an MDIO command handler rather than a
 * plain register: write any parameters to the DATA registers, the command code to CMD, then poll
 * STATUS. Copper rate uses the standard NBASE-T advertisement bits, but unlike other PHYs the
 * other bits of that register are live (master/slave, port type), so it is read-modify-written. */
#define BCM_ID_MASK           0xfffffff0
#define BCM_ID_84891L         0x35905080

#define BCM_VEND1_MMD         30
#define BCM_CMD               0x4005
#define BCM_STATUS            0x4037
#define BCM_DATA1             0x4038
#define BCM_DATA2             0x4039
#define BCM_STATUS_PASS       0x0004   /* CMD_COMPLETE_PASS / CMD_OPEN_FOR_CMDS */
#define BCM_STATUS_BUSY       0x0002   /* CMD_IN_PROGRESS */
#define BCM_CMD_GET_XFI_MODE  0x8016
#define BCM_CMD_SET_XFI_MODE  0x8017
/* DATA1 is the encoding used when copper links at 2.5G, DATA2 when it links at 5G. */
#define BCM_XFI_IDLE_STUFF    0      /* stay 10GBASE-R and pad with idles */
#define BCM_XFI_BASEX         1      /* 2500BASE-X / 5000BASE-X (8b/10b) */
#define BCM_XFI_BASER         2      /* 2500BASE-R / 5000BASE-R (64b/66b) */
#define BCM_ADV_MASK          (ADV_10G | ADV_5G | ADV_2_5G)
#define BCM_AN_AUX_STATUS     0xfff9  /* bit15 = autonegotiation complete */
#define BCM_AN_AUX_COMPLETE   0x8000
#define BCM_CMD_POLL_TRIES    30     /* datasheet: up to 2s while the line side is training */
#define AQ_VEND1_MMD          30
#define AQ_VEND1_CFG_1G       0x031c
#define AQ_VEND1_CFG_2_5G     0x031d
#define AQ_VEND1_CFG_5G       0x031e
#define AQ_VEND1_CFG_10G      0x031f
#define AQ_CFG_SERDES_MODE    0x0007
#define AQ_CFG_RATE_ADAPT     0x0180   /* bits [8:7]: 0=none 1=USXGMII 2=pause */
#define AQ_SERDES_XFI         0        /* 10GBASE-R */
#define AQ_SERDES_SGMII       3        /* 1000BASE-X */
#define AQ_SERDES_OCSGMII     4        /* "overclocked SGMII" = 2500BASE-X */
#define AQ_SERDES_XFI5G       6        /* 5GBASE-R */
#define AQ_AN_MMD             7
#define AQ_AN_CTRL            0x0000
#define AQ_AN_CTRL_RESTART    0x3200   /* autoneg enable + restart */
#define AQ_AN_STATUS          0x0001
#define AQ_AN_STATUS_COMPLETE 0x0020   /* copper autonegotiation complete */
#define AQ_AN_10GBT_CTRL      0x0020   /* bit12=10G bit8=5G bit7=2.5G advertisement */
#define AQ_VEND1_FW_ID        0x0020   /* firmware version; 0 while the bootloader is running */
#define AQ_FW_WAIT_TRIES      20       /* module answers MDIO ~0.1s after reset, firmware ~1.9s */
#define AQ_PMA_MMD            1
#define AQ_PMA_CTRL           0x0000
#define AQ_PMA_CTRL_LOWPOWER  0x0800
#define AQ_IF_WAIT_MS         8000     /* copper autoneg + PHY training, measured ~3-4s */
#define AQ_PHYXS_MMD          4
#define AQ_PHYXS_IF_STATUS    0xe812
/* The system-interface status field layout is not public. Bit 0 was set only while the
 * interface was actually up and passing traffic (0x3559 at 5G, 0x3451 at 2.5G), and clear in
 * both observed down states (0x0048 after a failed switch, 0x1510 after a global reset). */
#define AQ_IF_STATUS_LINK     0x0001

/* Copper advertisement (MMD 7 reg 0x20) for a single NBASE-T rate. Clearing all three lets
 * autonegotiation fall back to the base page, i.e. 1000BASE-T and below. */
#define ADV_10G   0x1000
#define ADV_5G    0x0100
#define ADV_2_5G  0x0080
#define ADV_1G    0x0000

/* Aquantia NBASE-T advertisements. Default will likely be all three advertised. */
#define AQ_AN_VEND_PROV        0xc400
#define AQ_PROV_1000BASET      0x8000
#define AQ_PROV_5000BASET      0x0800
#define AQ_PROV_2500BASET      0x0400
#define AQ_PROV_RATE_MASK      (AQ_PROV_1000BASET | AQ_PROV_5000BASET | AQ_PROV_2500BASET)

/* Resolved copper rate, MMD 7 reg 0xC800 bits [3:1]. */
#define AQ_AN_VEND_STATUS      0xc800
#define AQ_VEND_STATUS_RATE(v) (((v) >> 1) & 7)
#define AQ_RATE_1G             2
#define AQ_RATE_10G            3
#define AQ_RATE_2_5G           4
#define AQ_RATE_5G             5

void busy_wait(unsigned int ms);

static bool sfp_cage_open(const struct sfp_cage *cage);
static bool sfp_cage_present(const struct sfp_cage *cage);
static bool sfp_unlock(const struct sfp_cage *cage);
static bool sfp_host_mode_ok(const struct sfp_cage *cage, int mode);

/* Cage table ---------------------------------------------------------------------------------
 * Per-cage defaults, so a board only declares what it actually has. */

#ifdef CONFIG_SFP_0_I2C
# if !defined(CONFIG_SFP_0_MUX_ADDR)
#  define CONFIG_SFP_0_MUX_ADDR 0
#  define CONFIG_SFP_0_MUX_CHANNEL 0
# endif
# ifndef CONFIG_SFP_0_HOST_MODE
#  define CONFIG_SFP_0_HOST_MODE "AUTO"
# endif
#endif
#ifdef CONFIG_SFP_1_I2C
# if !defined(CONFIG_SFP_1_MUX_ADDR)
#  define CONFIG_SFP_1_MUX_ADDR 0
#  define CONFIG_SFP_1_MUX_CHANNEL 0
# endif
# ifndef CONFIG_SFP_1_HOST_MODE
#  define CONFIG_SFP_1_HOST_MODE "AUTO"
# endif
#endif
#ifdef CONFIG_SFP_2_I2C
# if !defined(CONFIG_SFP_2_MUX_ADDR)
#  define CONFIG_SFP_2_MUX_ADDR 0
#  define CONFIG_SFP_2_MUX_CHANNEL 0
# endif
# ifndef CONFIG_SFP_2_HOST_MODE
#  define CONFIG_SFP_2_HOST_MODE "AUTO"
# endif
#endif
#ifdef CONFIG_SFP_3_I2C
# if !defined(CONFIG_SFP_3_MUX_ADDR)
#  define CONFIG_SFP_3_MUX_ADDR 0
#  define CONFIG_SFP_3_MUX_CHANNEL 0
# endif
# ifndef CONFIG_SFP_3_HOST_MODE
#  define CONFIG_SFP_3_HOST_MODE "AUTO"
# endif
#endif

#define SFP_CAGE(n) {                                \
	.i2c_dev     = CONFIG_SFP_##n##_I2C,         \
	.mux_addr    = CONFIG_SFP_##n##_MUX_ADDR,    \
	.mux_channel = CONFIG_SFP_##n##_MUX_CHANNEL, \
	.host_mode   = CONFIG_SFP_##n##_HOST_MODE,   \
}

const struct sfp_cage sfp_cages[] = {
#ifdef CONFIG_SFP_0_I2C
	SFP_CAGE(0),
#endif
#ifdef CONFIG_SFP_1_I2C
	SFP_CAGE(1),
#endif
#ifdef CONFIG_SFP_2_I2C
	SFP_CAGE(2),
#endif
#ifdef CONFIG_SFP_3_I2C
	SFP_CAGE(3),
#endif
};
const unsigned int sfp_cage_count = sizeof(sfp_cages)/sizeof(sfp_cages[0]);

/* Mode names ---------------------------------------------------------------------------------- */

static const struct { int mode; const char *name; } sfp_mode_names[] = {
	{ SFP_HOST_AUTO,      "AUTO"      },
	{ SFP_HOST_10GBASER,  "10GBASER"  },
	{ SFP_HOST_5GBASER,   "5GBASER"   },
	{ SFP_HOST_2500BASEX, "2500BASEX" },
	{ SFP_HOST_1000BASEX, "1000BASEX" },
	{ SFP_HOST_5000BASEX, "5000BASEX" },
};

int sfp_host_mode_from_name(const char *name)
{
	unsigned int i;
	for (i = 0; i < sizeof(sfp_mode_names)/sizeof(sfp_mode_names[0]); i++)
		if (strcmp(sfp_mode_names[i].name, name) == 0)
			return sfp_mode_names[i].mode;
	return -1;
}

const char *sfp_host_mode_name(int mode)
{
	unsigned int i;
	for (i = 0; i < sizeof(sfp_mode_names)/sizeof(sfp_mode_names[0]); i++)
		if (sfp_mode_names[i].mode == mode)
			return sfp_mode_names[i].name;
	return "unknown";
}

const char *sfp_family_name(int family)
{
	switch (family) {
	case SFP_PHY_MARVELL:  return "Marvell";
	case SFP_PHY_AQUANTIA: return "Aquantia";
	case SFP_PHY_BROADCOM: return "Broadcom";
	default:               return "unknown";
	}
}

/* I2C / RollBall transport --------------------------------------------------------------------
 * These act on whichever cage was last opened; every public entry point opens its own. */

static bool rb_wr(uint8_t offset, const uint8_t *data, unsigned int len)
{
	return i2c_write(RB_ADDR, offset, data, len, 1);
}

static bool rb_rd(uint8_t offset, uint8_t *data, unsigned int len)
{
	return i2c_read(RB_ADDR, offset, data, len, false, 1);
}

static bool sfp_cage_open(const struct sfp_cage *cage)
{
	struct i2c_dev *devs = get_i2c_devs();
	int i, n = get_i2c_devs_count();

	for (i = 0; i < n; i++) {
		if (strcmp(devs[i].name, cage->i2c_dev) == 0)
			break;
	}
	if (i == n) {
		printf("SFP: I2C device %s not found\n", cage->i2c_dev);
		return false;
	}
	set_i2c_active_dev(i);
	if (cage->mux_addr) {
		/* PCA954x: a single control byte selects the channel. */
		uint8_t mask = 1 << (cage->mux_channel & 7);
		if (!i2c_write(cage->mux_addr, mask, NULL, 0, 1)) {
			printf("SFP: I2C mux 0x%02x did not answer\n", cage->mux_addr);
			return false;
		}
	}
	return true;
}

static bool sfp_cage_present(const struct sfp_cage *cage)
{
	return sfp_cage_open(cage) && i2c_poll(RB_ADDR);
}

static bool sfp_unlock(const struct sfp_cage *cage)
{
	static const uint8_t password[4] = {0xff, 0xff, 0xff, 0xff};
	if (!sfp_cage_open(cage))
		return false;
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

int sfp_mdio_read(const struct sfp_cage *cage, uint8_t mmd, uint16_t reg)
{
	uint8_t saved;
	uint8_t data[3] = {mmd & 0x1f, reg >> 8, reg & 0xff};
	uint8_t cmd     = RB_CMD_READ;
	uint8_t buf[6];
	bool ok;

	if (!sfp_cage_open(cage) || !rb_select_page(&saved))
		return -1;
	ok = rb_wr(RB_DATA, data, sizeof(data)) && rb_wr(RB_CMD, &cmd, 1);
	rb_restore_page(saved);
	if (!ok || !rb_poll(buf, sizeof(buf)))
		return -1;
	return (buf[4] << 8) | buf[5];
}

bool sfp_mdio_write(const struct sfp_cage *cage, uint8_t mmd, uint16_t reg, uint16_t val)
{
	uint8_t saved;
	uint8_t data[5] = {mmd & 0x1f, reg >> 8, reg & 0xff, val >> 8, val & 0xff};
	uint8_t cmd     = RB_CMD_WRITE;
	uint8_t buf[1];
	bool ok;

	if (!sfp_cage_open(cage) || !rb_select_page(&saved))
		return false;
	ok = rb_wr(RB_DATA, data, sizeof(data)) && rb_wr(RB_CMD, &cmd, 1);
	rb_restore_page(saved);
	return ok && rb_poll(buf, sizeof(buf));
}

/* PHY identification --------------------------------------------------------------------------- */

static uint32_t sfp_phy_id(const struct sfp_cage *cage)
{
	int hi = sfp_mdio_read(cage, 1, 2);
	int lo = sfp_mdio_read(cage, 1, 3);
	if (hi < 0 || lo < 0)
		return 0;
	return ((uint32_t)hi << 16) | (uint32_t)lo;
}

static int sfp_family(uint32_t id)
{
	if (id == 0 || id == 0xffffffff)
		return SFP_PHY_UNKNOWN;
	if ((id & AQ_ID_MASK) == AQ_ID_AQR113C)
		return SFP_PHY_AQUANTIA;
	if ((id & MV_ID_MASK) == MV_ID_88X3310 || (id & MV_ID_MASK) == MV_ID_88E2110)
		return SFP_PHY_MARVELL;
	if ((id & BCM_ID_MASK) == BCM_ID_84891L)
		return SFP_PHY_BROADCOM;
	return SFP_PHY_UNKNOWN;
}

bool sfp_probe(const struct sfp_cage *cage, uint32_t *phy_id, int *family)
{
	uint32_t id;

	if (!sfp_cage_present(cage) || !sfp_unlock(cage))
		return false;
	id = sfp_phy_id(cage);
	if (phy_id)
		*phy_id = id;
	if (family)
		*family = sfp_family(id);
	return id != 0 && id != 0xffffffff;
}

/* Copper advertisement -------------------------------------------------------------------------
 * The host rate follows the copper rate, so asking for a host mode means constraining which
 * copper rate autonegotiation may settle on. */

static int mode_advertisement(int mode)
{
	switch (mode) {
	case SFP_HOST_10GBASER:  return ADV_10G;
	case SFP_HOST_5GBASER:   return ADV_5G;
	case SFP_HOST_2500BASEX: return ADV_2_5G;
	case SFP_HOST_1000BASEX: return ADV_1G;
	case SFP_HOST_5000BASEX: return ADV_5G;   /* 5G copper, 8b/10b on the host */
	default:                 return -1;
	}
}

/* Aquantia vendor advertisement bits for a single rate. */
static int aq_mode_prov(int mode)
{
	switch (mode) {
	case SFP_HOST_10GBASER:  return 0;
	case SFP_HOST_5GBASER:   return AQ_PROV_5000BASET;
	case SFP_HOST_2500BASEX: return AQ_PROV_2500BASET;
	case SFP_HOST_1000BASEX: return AQ_PROV_1000BASET;
	default:                 return -1;
	}
}

/* The copper rate a given host mode requires. The host side follows the copper side. */
static int mode_copper_rate(int mode)
{
	switch (mode) {
	case SFP_HOST_10GBASER:  return AQ_RATE_10G;
	case SFP_HOST_5GBASER:   return AQ_RATE_5G;
	case SFP_HOST_2500BASEX: return AQ_RATE_2_5G;
	case SFP_HOST_1000BASEX: return AQ_RATE_1G;
	default:                 return -1;
	}
}

/* Marvell ---------------------------------------------------------------------------------------- */

/* Locate the port-control register for this PHY. */
static bool mv_port_ctrl(uint32_t id, uint8_t *mmd, uint16_t *reg)
{
	switch (id & MV_ID_MASK) {
	case MV_ID_88X3310:
		*mmd = MV_V2_PORT_CTRL_MMD; *reg = MV_V2_PORT_CTRL_REG;
		return true;
	case MV_ID_88E2110:
		*mmd = MV_PMA_PORT_CTRL_MMD; *reg = MV_PMA_PORT_CTRL_REG;
		return true;
	default:
		return false;
	}
}

static bool mv_set_host_mode(const struct sfp_cage *cage, uint32_t id, int mode)
{
	uint8_t mmd; uint16_t reg, target;
	int cur, adv, i, mactype;

	if (!mv_port_ctrl(id, &mmd, &reg))
		return false;
	if (mode == SFP_HOST_5000BASEX)
		return false;   /* 8b/10b at 6.25Gbaud is Broadcom-only. */
	/* MACTYPE 4 follows the copper rate, which covers every sub-10G host mode; 6 pins the
	 * host at 10GBASE-R regardless of copper. */
	mactype = (mode == SFP_HOST_10GBASER) ? MV_MACTYPE_10G_MATCH : MV_MACTYPE_FOLLOW;

	adv = mode_advertisement(mode);
	if (adv < 0)
		return false;

	cur = sfp_mdio_read(cage, mmd, reg);
	if (cur < 0)
		return false;
	target = (cur & ~MV_PORT_CTRL_MACTYPE) | mactype;
	if ((cur & MV_PORT_CTRL_MACTYPE) != mactype) {
		if (!sfp_mdio_write(cage, mmd, reg, target))
			return false;
		/* The software reset applies the new mode. Some firmware only shows the new value
		 * after it, and the transport drops while the PHY reboots, so this write's
		 * completion is deliberately not checked. */
		sfp_mdio_write(cage, mmd, reg, target | MV_PORT_CTRL_SWRST);
		for (i = 0; i < 20; i++) {
			busy_wait(250);
			if (!sfp_cage_present(cage) || !sfp_unlock(cage))
				continue;
			cur = sfp_mdio_read(cage, mmd, reg);
			if (cur >= 0 && (cur & MV_PORT_CTRL_MACTYPE) == mactype)
				break;
		}
		if (i == 20)
			return false;
	}
	sfp_mdio_write(cage, AQ_AN_MMD, AQ_AN_10GBT_CTRL, adv);
	sfp_mdio_write(cage, AQ_AN_MMD, AQ_AN_CTRL, AQ_AN_CTRL_RESTART);
	return true;
}

static bool mv_host_mode_ok(const struct sfp_cage *cage, uint32_t id, int mode)
{
	uint8_t mmd; uint16_t reg; int cur, want;

	if (!mv_port_ctrl(id, &mmd, &reg) || mode == SFP_HOST_5000BASEX)
		return false;
	cur = sfp_mdio_read(cage, mmd, reg);
	if (cur < 0)
		return false;
	want = (mode == SFP_HOST_10GBASER) ? MV_MACTYPE_10G_MATCH : MV_MACTYPE_FOLLOW;
	return (cur & MV_PORT_CTRL_MACTYPE) == want;
}

/* Aquantia --------------------------------------------------------------------------------------- */

/* Per-rate config register and native SERDES mode for a host mode. */
static bool aq_mode_regs(int mode, uint16_t *cfg_reg, uint16_t *serdes)
{
	switch (mode) {
	case SFP_HOST_10GBASER:  *cfg_reg = AQ_VEND1_CFG_10G;  *serdes = AQ_SERDES_XFI;     return true;
	case SFP_HOST_5GBASER:   *cfg_reg = AQ_VEND1_CFG_5G;   *serdes = AQ_SERDES_XFI5G;   return true;
	case SFP_HOST_2500BASEX: *cfg_reg = AQ_VEND1_CFG_2_5G; *serdes = AQ_SERDES_OCSGMII; return true;
	case SFP_HOST_1000BASEX: *cfg_reg = AQ_VEND1_CFG_1G;   *serdes = AQ_SERDES_SGMII;   return true;
	default:                 return false;
	}
}

/* Wait for the PHY firmware to finish loading.
 *
 * The module acknowledges I2C and answers MDIO about 0.1s after power-up or reset, but its
 * firmware is not loaded until roughly 1.9s. Configuration written before firmware is loaded
 * gets overwritten. We use the FW_ID as a gate to see if the firwmare is loaded, following the
 * example of the Linux kernel aquantia driver.
 */
static bool aq_wait_firmware(const struct sfp_cage *cage)
{
	int i, v;

	for (i = 0; i < AQ_FW_WAIT_TRIES; i++) {
		v = sfp_mdio_read(cage, AQ_VEND1_MMD, AQ_VEND1_FW_ID);
		if (v > 0 && v != 0xffff)
			return true;
		busy_wait(100);
	}
	return false;
}

/* Select a native host mode. */
static bool aq_set_host_mode(const struct sfp_cage *cage, int mode)
{
	uint16_t cfg_reg, serdes, target;
	int v, i, adv, prov;
	bool copper_up;

	if (!aq_mode_regs(mode, &cfg_reg, &serdes))
		return false;
	if (!aq_wait_firmware(cage)) {
		printf("firmware not loaded: ");
		return false;
	}
	adv = mode_advertisement(mode);
	if (adv < 0)
		return false;

	v = sfp_mdio_read(cage, AQ_AN_MMD, AQ_AN_STATUS);
	copper_up = (v >= 0) && !!(v & AQ_AN_STATUS_COMPLETE);

	v = sfp_mdio_read(cage, AQ_VEND1_MMD, cfg_reg);
	if (v < 0)
		return false;
	target = (v & ~(AQ_CFG_SERDES_MODE | AQ_CFG_RATE_ADAPT)) | serdes;
	if (v != target && !sfp_mdio_write(cage, AQ_VEND1_MMD, cfg_reg, target))
		return false;
	sfp_mdio_write(cage, AQ_AN_MMD, AQ_AN_10GBT_CTRL, adv);

	/* The vendor advertisement is the one autonegotiation actually honours. */
	prov = aq_mode_prov(mode);
	v = sfp_mdio_read(cage, AQ_AN_MMD, AQ_AN_VEND_PROV);
	if (v < 0 || prov < 0)
		return false;
	if (!sfp_mdio_write(cage, AQ_AN_MMD, AQ_AN_VEND_PROV,
			    (v & ~AQ_PROV_RATE_MASK) | prov))
		return false;

	if (!sfp_mdio_write(cage, AQ_AN_MMD, AQ_AN_CTRL, AQ_AN_CTRL_RESTART))
		return false;
	if (!copper_up)
		return true;

	/* Force the copper link event. The per-rate config survives this. */
	v = sfp_mdio_read(cage, AQ_PMA_MMD, AQ_PMA_CTRL);
	if (v < 0)
		return false;
	sfp_mdio_write(cage, AQ_PMA_MMD, AQ_PMA_CTRL, v | AQ_PMA_CTRL_LOWPOWER);
	busy_wait(200);
	if (!sfp_mdio_write(cage, AQ_PMA_MMD, AQ_PMA_CTRL, v & ~AQ_PMA_CTRL_LOWPOWER))
		return false;

	/* Copper training dominates the wait; confirm the interface rather than assuming it. */
	for (i = 0; i < AQ_IF_WAIT_MS / 250; i++) {
		busy_wait(250);
		v = sfp_mdio_read(cage, AQ_PHYXS_MMD, AQ_PHYXS_IF_STATUS);
		if (v >= 0 && (v & AQ_IF_STATUS_LINK))
			return true;
	}
	return false;
}

static bool aq_host_mode_ok(const struct sfp_cage *cage, int mode)
{
	uint16_t cfg_reg, serdes;
	int v;

	if (!aq_mode_regs(mode, &cfg_reg, &serdes))
		return false;
	v = sfp_mdio_read(cage, AQ_VEND1_MMD, cfg_reg);
	if (v < 0 || (v & (AQ_CFG_SERDES_MODE | AQ_CFG_RATE_ADAPT)) != serdes)
		return false;
	v = sfp_mdio_read(cage, AQ_AN_MMD, AQ_AN_VEND_STATUS);
	if (v < 0 || AQ_VEND_STATUS_RATE(v) != mode_copper_rate(mode))
		return false;
	/* The register alone is not enough: on a warm reboot it can read back correct while the
	 * host interface never switched. Require the interface to actually be up. */
	v = sfp_mdio_read(cage, AQ_PHYXS_MMD, AQ_PHYXS_IF_STATUS);
	return v >= 0 && !!(v & AQ_IF_STATUS_LINK);
}

/* Broadcom ---------------------------------------------------------------------------------- */

/* XFI encoding to program for each copper rate. DATA1 applies when copper links at 2.5G, DATA2
 * when it links at 5G; only the one matching the requested mode's copper rate has any effect,
 * but the command carries both, so the other is set to a sensible default rather than left
 * stale. 1000BASE-X (SGMII at 1.25Gbaud) and 10GBASE-R are implied by the copper rate and do
 * not need XFI selection. For 10GBASE-R the idle-stuffing setting keeps the host at 10G even
 * if copper negotiates a lower rate. */
static bool bcm_xfi_modes(int mode, uint16_t *data1, uint16_t *data2)
{
	switch (mode) {
	case SFP_HOST_10GBASER:  *data1 = BCM_XFI_IDLE_STUFF; *data2 = BCM_XFI_IDLE_STUFF; return true;
	case SFP_HOST_5GBASER:   *data1 = BCM_XFI_BASEX;      *data2 = BCM_XFI_BASER;      return true;
	case SFP_HOST_5000BASEX: *data1 = BCM_XFI_BASEX;      *data2 = BCM_XFI_BASEX;      return true;
	case SFP_HOST_2500BASEX: *data1 = BCM_XFI_BASEX;      *data2 = BCM_XFI_BASEX;      return true;
	case SFP_HOST_1000BASEX: *data1 = BCM_XFI_BASEX;      *data2 = BCM_XFI_BASEX;      return true;
	default:                 return false;
	}
}

static bool bcm_command(const struct sfp_cage *cage, uint16_t command)
{
	int i, v;

	if (!sfp_mdio_write(cage, BCM_VEND1_MMD, BCM_CMD, command))
		return false;
	for (i = 0; i < BCM_CMD_POLL_TRIES; i++) {
		v = sfp_mdio_read(cage, BCM_VEND1_MMD, BCM_STATUS);
		if (v == BCM_STATUS_PASS)
			return true;
		busy_wait(100);
	}
	return false;
}

static bool bcm_get_xfi_modes(const struct sfp_cage *cage, int *data1, int *data2)
{
	if (!bcm_command(cage, BCM_CMD_GET_XFI_MODE))
		return false;
	*data1 = sfp_mdio_read(cage, BCM_VEND1_MMD, BCM_DATA1);
	*data2 = sfp_mdio_read(cage, BCM_VEND1_MMD, BCM_DATA2);
	return *data1 >= 0 && *data2 >= 0;
}

static bool bcm_set_host_mode(const struct sfp_cage *cage, int mode)
{
	uint16_t data1, data2;
	int adv, cur, i, got1, got2;

	if (!bcm_xfi_modes(mode, &data1, &data2))
		return false;
	adv = mode_advertisement(mode);
	if (adv < 0)
		return false;

	/* Host encoding first: must be set before the line side autonegotiates. */
	if (!sfp_mdio_write(cage, BCM_VEND1_MMD, BCM_DATA1, data1) ||
	    !sfp_mdio_write(cage, BCM_VEND1_MMD, BCM_DATA2, data2) ||
	    !bcm_command(cage, BCM_CMD_SET_XFI_MODE))
		return false;

	/* Copper rate. Only touch NBASE-T ability bits. */
	cur = sfp_mdio_read(cage, AQ_AN_MMD, AQ_AN_10GBT_CTRL);
	if (cur < 0)
		return false;
	if (!sfp_mdio_write(cage, AQ_AN_MMD, AQ_AN_10GBT_CTRL, (cur & ~BCM_ADV_MASK) | adv))
		return false;
	if (!sfp_mdio_write(cage, AQ_AN_MMD, AQ_AN_CTRL, AQ_AN_CTRL_RESTART))
		return false;

	/* Wait for line side to finish negotiating new rate. */
	for (i = 0; i < AQ_IF_WAIT_MS / 250; i++) {
		busy_wait(250);
		if (sfp_mdio_read(cage, AQ_AN_MMD, BCM_AN_AUX_STATUS) & BCM_AN_AUX_COMPLETE) {
			if (bcm_get_xfi_modes(cage, &got1, &got2))
				return got1 == data1 && got2 == data2;
			return false;
		}
	}
	return false;
}

/* NOTE: this only confirms what was provisioned and that autonegotiation finished, not the rate
 * it settled on. */
static bool bcm_host_mode_ok(const struct sfp_cage *cage, int mode)
{
	uint16_t data1, data2;
	int adv, cur, d1, d2;

	if (!bcm_xfi_modes(mode, &data1, &data2))
		return false;
	adv = mode_advertisement(mode);
	cur = sfp_mdio_read(cage, AQ_AN_MMD, AQ_AN_10GBT_CTRL);
	if (adv < 0 || cur < 0 || (cur & BCM_ADV_MASK) != adv)
		return false;
	if (!(sfp_mdio_read(cage, AQ_AN_MMD, BCM_AN_AUX_STATUS) & BCM_AN_AUX_COMPLETE))
		return false;
	if (!bcm_get_xfi_modes(cage, &d1, &d2))
		return false;
	return d1 == data1 && d2 == data2;
}

/* Host mode ------------------------------------------------------------------------------------- */

bool sfp_set_host_mode(const struct sfp_cage *cage, int mode)
{
	uint32_t id;
	int family;

	if (mode == SFP_HOST_AUTO)
		return true;
	if (!sfp_probe(cage, &id, &family))
		return false;
	switch (family) {
	case SFP_PHY_MARVELL:  return mv_set_host_mode(cage, id, mode);
	case SFP_PHY_AQUANTIA: return aq_set_host_mode(cage, mode);
	case SFP_PHY_BROADCOM: return bcm_set_host_mode(cage, mode);
	default:               return false;
	}
}

static bool sfp_host_mode_ok(const struct sfp_cage *cage, int mode)
{
	uint32_t id;
	int family;

	if (mode == SFP_HOST_AUTO)
		return true;
	if (!sfp_probe(cage, &id, &family))
		return false;
	switch (family) {
	case SFP_PHY_MARVELL:  return mv_host_mode_ok(cage, id, mode);
	case SFP_PHY_AQUANTIA: return aq_host_mode_ok(cage, mode);
	case SFP_PHY_BROADCOM: return bcm_host_mode_ok(cage, mode);
	default:               return false;
	}
}

/* Boot-time initialization ------------------------------------------------------------------ */

void sfp_init(void)
{
	int saved_dev = get_i2c_active_dev();
	unsigned int c;

	for (c = 0; c < sfp_cage_count; c++) {
		const struct sfp_cage *cage = &sfp_cages[c];
		int mode = sfp_host_mode_from_name(cage->host_mode);
		int attempt;
		bool done = false;

		if (mode <= SFP_HOST_AUTO)
			continue;   /* nothing requested, or an unknown name */

		/* A freshly powered module takes a few seconds to boot PHY firmware. */
		for (attempt = 0; attempt < 15 && !done; attempt++) {
			uint32_t id;
			int family;

			if (attempt)
				busy_wait(1000);
			if (!sfp_probe(cage, &id, &family))
				continue;
			printf("SFP %s: PHY 0x%08lx (%s), %s: ", cage->i2c_dev,
			       (unsigned long)id, sfp_family_name(family),
			       sfp_host_mode_name(mode));
			if (sfp_host_mode_ok(cage, mode)) {
				printf("already set\n");
				done = true;
			} else if (sfp_set_host_mode(cage, mode)) {
				printf("done\n");
				done = true;
			} else {
				printf("failed\n");
			}
		}
		if (!done)
			printf("SFP %s: not configured, giving up\n", cage->i2c_dev);
	}
	set_i2c_active_dev(saved_dev);
}

#else /* no I2C, or no cage configured */

void sfp_init(void) {}

#endif
