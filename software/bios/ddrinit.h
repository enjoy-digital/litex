#ifndef __DDRINIT_H
#define __DDRINIT_H

void ddrsw(void);
void ddrhw(void);
void ddrrow(char *_row);
void ddrrd(char *startaddr);
void ddrwr(char *startaddr);
int memtest_silent(void);
void memtest(void);
int ddrinit(void);

#endif /* __DDRINIT_H */
