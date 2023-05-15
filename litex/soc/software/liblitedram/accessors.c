#include <stdio.h>

#include <liblitedram/accessors.h>

#if defined(CSR_SDRAM_BASE) && defined(CSR_DDRPHY_BASE)

/*----------------------------------------------------------------------------*/
/* Read DQ Delays Reset/Increment Functions                                   */
/*----------------------------------------------------------------------------*/

#if defined(SDRAM_PHY_READ_LEVELING_CAPABLE)

int read_dq_delay[SDRAM_PHY_MODULES];
void read_inc_dq_delay(int module) {
	/* Increment delay */
	read_dq_delay[module] = (read_dq_delay[module] + 1) & (SDRAM_PHY_DELAYS - 1);
	ddrphy_rdly_dq_inc_write(1);
}

void read_rst_dq_delay(int module) {
	/* Reset delay */
	read_dq_delay[module] = 0;
	ddrphy_rdly_dq_rst_write(1);
}

#endif // defined(SDRAM_PHY_READ_LEVELING_CAPABLE)

/*----------------------------------------------------------------------------*/
/* Write DQ/DQS/Clk Delays Reset/Increment Functions                          */
/*----------------------------------------------------------------------------*/

#if defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE)

int sdram_clock_delay;
void sdram_inc_clock_delay(void) {
	sdram_clock_delay = (sdram_clock_delay + 1) & (SDRAM_PHY_DELAYS - 1);
	ddrphy_cdly_inc_write(1);
	cdelay(100);
}

void sdram_rst_clock_delay(void) {
	sdram_clock_delay = 0;
	ddrphy_cdly_rst_write(1);
	cdelay(100);
}

int write_dq_delay[SDRAM_PHY_MODULES];
void write_inc_dq_delay(int module) {
	/* Increment DQ delay */
	write_dq_delay[module] = (write_dq_delay[module] + 1) & (SDRAM_PHY_DELAYS - 1);
	ddrphy_wdly_dq_inc_write(1);
	cdelay(100);
}

void write_rst_dq_delay(int module) {
#if defined(SDRAM_PHY_USDDRPHY) || defined(SDRAM_PHY_USPDDRPHY)
	/* Reset DQ delay */
	int dq_count = ddrphy_wdly_dqs_inc_count_read();
	while (dq_count != SDRAM_PHY_DELAYS) {
		ddrphy_wdly_dq_inc_write(1);
		cdelay(100);
		dq_count++;
	}
#else
	/* Reset DQ delay */
	ddrphy_wdly_dq_rst_write(1);
	cdelay(100);
#endif //defined(SDRAM_PHY_USDDRPHY) || defined(SDRAM_PHY_USPDDRPHY)
	write_dq_delay[module] = 0;
}

void write_inc_dqs_delay(int module) {
	/* Increment DQS delay */
	ddrphy_wdly_dqs_inc_write(1);
	cdelay(100);
}

void write_rst_dqs_delay(int module) {
#if defined(SDRAM_PHY_USDDRPHY) || defined(SDRAM_PHY_USPDDRPHY)
	/* Reset DQS delay */
	while (ddrphy_wdly_dqs_inc_count_read() != 0) {
		ddrphy_wdly_dqs_inc_write(1);
		cdelay(100);
	}
#else
	/* Reset DQS delay */
	ddrphy_wdly_dqs_rst_write(1);
	cdelay(100);
#endif //defined(SDRAM_PHY_USDDRPHY) || defined(SDRAM_PHY_USPDDRPHY)
}

void write_inc_delay(int module) {
	/* Increment DQ/DQS delay */
	write_inc_dq_delay(module);
	write_inc_dqs_delay(module);
}

void write_rst_delay(int module) {
	write_rst_dq_delay(module);
	write_rst_dqs_delay(module);
}

#endif // defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE)

/*----------------------------------------------------------------------------*/
/* Bitslip Delays Reset/Increment Functions                                   */
/*----------------------------------------------------------------------------*/

#if defined(SDRAM_PHY_BITSLIPS) && defined(SDRAM_PHY_READ_LEVELING_CAPABLE)

int read_dq_bitslip[SDRAM_PHY_MODULES];
void read_inc_dq_bitslip(int module) {
	/* Increment bitslip */
	read_dq_bitslip[module] = (read_dq_bitslip[module] + 1) & (SDRAM_PHY_BITSLIPS - 1);
	ddrphy_rdly_dq_bitslip_write(1);
}

void read_rst_dq_bitslip(int module) {
/* Reset bitslip */
	read_dq_bitslip[module] = 0;
	ddrphy_rdly_dq_bitslip_rst_write(1);
}

#endif  // defined(SDRAM_PHY_BITSLIPS) && defined(SDRAM_PHY_READ_LEVELING_CAPABLE)

#if defined(SDRAM_PHY_BITSLIPS) && defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE)

int write_dq_bitslip[SDRAM_PHY_MODULES];
void write_inc_dq_bitslip(int module) {
	/* Increment bitslip */
	write_dq_bitslip[module] = (write_dq_bitslip[module] + 1) & (SDRAM_PHY_BITSLIPS - 1);
	ddrphy_wdly_dq_bitslip_write(1);
}

void write_rst_dq_bitslip(int module) {
	/* Increment bitslip */
	write_dq_bitslip[module] = 0;
	ddrphy_wdly_dq_bitslip_rst_write(1);
}

#endif // defined(SDRAM_PHY_BITSLIPS) && defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE)

/*----------------------------------------------------------------------------*/
/* SDRAM Module Selection Functions                                           */
/*----------------------------------------------------------------------------*/

void sdram_select(int module, int dq_line) {
	ddrphy_dly_sel_write(1 << module);

#ifdef SDRAM_DELAY_PER_DQ
	/* Select DQ line */
	ddrphy_dq_dly_sel_write(1 << dq_line);
#endif
}

void sdram_deselect(int module, int dq_line) {
	ddrphy_dly_sel_write(0);

#if defined(SDRAM_PHY_ECP5DDRPHY) || defined(SDRAM_PHY_GW2DDRPHY)
	/* Sync all DQSBUFM's, By toggling all dly_sel (DQSBUFM.PAUSE) lines. */
	ddrphy_dly_sel_write(0xff);
	ddrphy_dly_sel_write(0);
#endif //SDRAM_PHY_ECP5DDRPHY

#ifdef SDRAM_DELAY_PER_DQ
	/* Un-select DQ line */
	ddrphy_dq_dly_sel_write(0);
#endif
}

/*----------------------------------------------------------------------------*/
/* SDRAM Actions                                                              */
/*----------------------------------------------------------------------------*/

void sdram_leveling_action(int module, int dq_line, action_callback action) {
	/* Select module */
	sdram_select(module, dq_line);

	/* Action */
	action(module);

	/* Un-select module */
	sdram_deselect(module, dq_line);
}

#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE
int _sdram_write_leveling_dat_delays[16];

void sdram_write_leveling_rst_dat_delay(int module, int show) {
	_sdram_write_leveling_dat_delays[module] = -1;
	if (show)
		printf("Reseting Dat delay of module %d\n", module);
}

void sdram_write_leveling_force_dat_delay(int module, int taps, int show) {
	_sdram_write_leveling_dat_delays[module] = taps;
	if (show)
		printf("Forcing Dat delay of module %d to %d taps\n", module, taps);
}

#if defined(SDRAM_PHY_BITSLIPS)
int _sdram_write_leveling_bitslips[16];
void sdram_write_leveling_rst_bitslip(int module, int show) {
	_sdram_write_leveling_bitslips[module] = -1;
	if (show)
		printf("Reseting Bitslip of module %d\n", module);
}

void sdram_write_leveling_force_bitslip(int module, int bitslip, int show) {
	_sdram_write_leveling_bitslips[module] = bitslip;
	if (show)
		printf("Forcing Bitslip of module %d to %d\n", module, bitslip);
}
#endif // defined(SDRAM_PHY_BITSLIPS)
#endif // SDRAM_PHY_WRITE_LEVELING_CAPABLE

#endif // defined(CSR_SDRAM_BASE) && defined(CSR_DDRPHY_BASE)
