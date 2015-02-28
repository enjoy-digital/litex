#ifndef __CRC_H
#define __CRC_H

unsigned short crc16(const unsigned char *buffer, int len);
unsigned int crc32(const unsigned char *buffer, unsigned int len);

#endif
