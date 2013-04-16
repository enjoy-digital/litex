#ifndef __TFTP_H
#define __TFTP_H

#include <stdint.h>

int tftp_get(uint32_t ip, const char *filename, void *buffer);

#endif /* __TFTP_H */

