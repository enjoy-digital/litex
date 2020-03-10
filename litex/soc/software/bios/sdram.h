#ifndef __SDRAM_H
#define __SDRAM_H

#include <generated/csr.h>

void sdrsw(void);
void sdrhw(void);
void sdrrow(char *_row);
void sdrrdbuf(int dq);
void sdrrd(char *startaddr, char *dq);
void sdrrderr(char *count);
void sdrwr(char *startaddr);

#ifdef CSR_DDRPHY_WLEVEL_EN_ADDR
void sdrwlon(void);
void sdrwloff(void);
int write_level(void);
#endif

#ifdef CSR_DDRPHY_BASE
void sdrwlon(void);
void sdrwloff(void);
int sdrlevel(void);
#endif

int memtest_silent(void);
int memtest(void);
int sdrinit(void);

#if defined(DDRPHY_CMD_DELAY) || defined(USDDRPHY_DEBUG)
void ddrphy_cdly(unsigned int delay);
#endif

#ifdef USDDRPHY_DEBUG
void sdrcal(void);
void sdrmrwr(char reg, int value);
void sdrmpr(void);
#endif

#endif /* __SDRAM_H */
