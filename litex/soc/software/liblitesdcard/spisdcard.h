// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2020 Rob Shelton <rob.s.ng15@googlemail.com>
// License: BSD

#ifndef __SPISDCARD_H
#define __SPISDCARD_H

#include <generated/csr.h>

#ifdef CSR_SPISDCARD_BASE

uint8_t spisdcard_init(void);
uint8_t spisdcard_read_block(uint32_t addr, uint8_t *buf);

#endif /* CSR_SPISDCARD_BASE */

#endif /* __SPISDCARD_H */
