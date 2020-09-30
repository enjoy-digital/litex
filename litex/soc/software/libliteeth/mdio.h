#ifndef __MDIO_H
#define __MDIO_H

#define MDIO_CLK 0x01
#define MDIO_OE	0x02
#define MDIO_DO	0x04

#define MDIO_DI	0x01

#define MDIO_PREAMBLE    0xffffffff
#define MDIO_START       0x1
#define MDIO_READ        0x2
#define MDIO_WRITE       0x1
#define MDIO_TURN_AROUND 0x2

void mdio_write(int phyadr, int reg, int val);
int mdio_read(int phyadr, int reg);

#endif /* __MDIO_H */
