// This file is Copyright (c) 2020 Rob Shelton <rob.s.ng15@googlemail.com>
// License: BSD

#ifndef __FAT16_H
#define __FAT16_H

uint8_t fat16_read_mbr(void);
uint8_t fat16_read_file(char *, char *, unsigned long);

#endif /* __FAT16_H */
