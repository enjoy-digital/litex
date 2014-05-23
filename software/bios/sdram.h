#ifndef __SDRAM_H
#define __SDRAM_H

void sdrsw(void);
void sdrhw(void);
void sdrrow(char *_row);
void sdrrd(char *startaddr);
void sdrwr(char *startaddr);
int memtest_silent(void);
int memtest(void);
int sdrinit(void);

#endif /* __SDRAM_H */
