#ifndef __SDRAM_H
#define __SDRAM_H

void ddrsw(void);
void ddrhw(void);
void ddrrow(char *_row);
void ddrrd(char *startaddr);
void ddrwr(char *startaddr);
int memtest_silent(void);
void memtest(void);
int ddrinit(void);

void asmiprobe(void);

#endif /* __SDRAM_H */
