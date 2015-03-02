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

#ifdef CSR_DDRPHY_BASE
void sdrwlon(void);
void sdrwloff(void);
int sdrlevel(void);
#endif

int memtest_silent(void);
int memtest(void);
int sdrinit(void);

#endif /* __SDRAM_H */
