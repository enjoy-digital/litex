#ifndef __TFTP_H
#define __TFTP_H

#include <stdint.h>

int tftp_get(uint32_t ip, const char *filename, void *buffer);
int tftp_put(uint32_t ip, const char *filename, const void *buffer, int size);

#endif /* __TFTP_H */

