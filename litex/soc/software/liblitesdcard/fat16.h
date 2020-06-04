// This file is Copyright (c) 2020 Rob Shelton <rob.s.ng15@googlemail.com>
// License: BSD

#ifndef __FAT16_H
#define __FAT16_H

uint8_t sdcard_readMBR(void);
uint8_t sdcard_readFile(char *, char *, unsigned long);

#endif /* __FAT16_H */
