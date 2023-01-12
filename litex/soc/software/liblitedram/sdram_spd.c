// This file is Copyright (c) 2023 Antmicro <www.antmicro.com>
// License: BSD

#include <liblitedram/sdram_spd.h>

#if defined(CSR_SDRAM_BASE) && defined(CONFIG_HAS_I2C)

#if defined(SDRAM_PHY_DDR4)
/*
 * In DDR4, addresses 0x36 (SPA0) and 0x37 (SPA1) are used to switch between two 256 byte pages.
 */
static bool sdram_select_spd_page(uint8_t page) {
	uint8_t i2c_addr;

	if (page == 0) {
		i2c_addr = 0x36;
	} else if (page == 1) {
		i2c_addr = 0x37;
	} else {
		return false;
	}

	return i2c_poll(i2c_addr);
}
#else
static bool sdram_select_spd_page(uint8_t page) {
	return true;
}
#endif

bool sdram_read_spd(uint8_t spd, uint16_t addr, uint8_t *buf, uint16_t len, bool send_stop) {
	uint8_t page;
	uint16_t offset;
	uint16_t temp_len, read_bytes = 0;
	bool temp_send_stop = false;

	bool ok = true;

	while (addr < SDRAM_SPD_SIZE && len > 0) {
		page = addr / SDRAM_SPD_PAGE_SIZE;
		ok &= sdram_select_spd_page(page);

		offset = addr % SDRAM_SPD_PAGE_SIZE;

		temp_len = SDRAM_SPD_PAGE_SIZE - offset;
		if (temp_len >= len) {
			temp_send_stop = send_stop;
			temp_len = len;
		}

		ok &= i2c_read(SPD_RW_ADDR(spd), offset, &buf[read_bytes], len, temp_send_stop, 1);
		len -= temp_len;
		read_bytes += temp_len;
		addr += temp_len;
	}

	return ok;
}
#else /* no CSR_SDRAM_BASE && CONFIG_HAS_I2C */
bool sdram_read_spd(uint8_t spd, uint16_t addr, uint8_t *buf, uint16_t len, bool send_stop) {
	return false;
}
#endif /* CSR_SDRAM_BASE && CONFIG_HAS_I2C */
