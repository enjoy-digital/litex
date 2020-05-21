#ifndef __SPD_H
#define __SPD_H

#include <generated/csr.h>

int spdread(unsigned int spdaddr, unsigned int addr, unsigned char *buf, unsigned int len);

#endif /* __SPD_H */
