#ifndef __SDRAM_H
#define __SDRAM_H

#include <generated/csr.h>

int sdrdatabits(void);
int sdrfreq(void);

void sdrsw(void);
void sdrhw(void);
void sdrrow(unsigned int row);
void sdrrdbuf(int dq);
void sdrrd(unsigned int addr, int dq);
void sdrrderr(int count);
void sdrwr(unsigned int addr);

void sdrwlon(void);
void sdrwloff(void);
int write_level(void);

int sdrlevel(void);

int sdrinit(void);

#endif /* __SDRAM_H */
