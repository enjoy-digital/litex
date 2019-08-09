#include <generated/csr.h>
#ifdef CSR_ETHPHY_MDIO_W_ADDR
#include "mdio.h"

#include <stdio.h>
#include <stdlib.h>

static void delay(void)
{
/* no delay FIXME */
}

static void raw_write(unsigned int word, int bitcount)
{
	word <<= 32 - bitcount;
	while(bitcount > 0) {
		if(word & 0x80000000) {
			ethphy_mdio_w_write(MDIO_CLK|MDIO_DO|MDIO_OE);
			delay();
			ethphy_mdio_w_write(MDIO_DO|MDIO_OE);
			delay();
		} else {
			ethphy_mdio_w_write(MDIO_CLK|MDIO_OE);
			delay();
			ethphy_mdio_w_write(MDIO_OE);
			delay();
		}
		word <<= 1;
		bitcount--;
	}
}

static unsigned int raw_read(void)
{
	unsigned int word;
	unsigned int i;

	word = 0;
	for(i=0;i<16;i++) {
		word <<= 1;
		ethphy_mdio_w_write(MDIO_CLK);
		delay();
		ethphy_mdio_w_write(0);
		delay();
		if(ethphy_mdio_r_read() & MDIO_DI)
			word |= 1;
	}
	return word;
}

static void raw_turnaround(void)
{
	ethphy_mdio_w_write(MDIO_CLK);
	delay();
	ethphy_mdio_w_write(0);
	delay();
	ethphy_mdio_w_write(MDIO_CLK);
	delay();
	ethphy_mdio_w_write(0);
	delay();
}

void mdio_write(int phyadr, int reg, int val)
{
	ethphy_mdio_w_write(MDIO_OE);
	raw_write(0xffffffff, 32); /* < sync */
	raw_write(0x05, 4); /* < start + write */
	raw_write(phyadr, 5);
	raw_write(reg, 5);
	raw_write(0x02, 2); /* < turnaround */
	raw_write(val, 16);
	raw_turnaround();
}

int mdio_read(int phyadr, int reg)
{
	int r;

	ethphy_mdio_w_write(MDIO_OE);
	raw_write(0xffffffff, 32); /* < sync */
	raw_write(0x06, 4); /* < start + read */
	raw_write(phyadr, 5);
	raw_write(reg, 5);
	raw_turnaround();
	r = raw_read();
	raw_turnaround();

	return r;
}

#endif