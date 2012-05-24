#ifndef __HW_ID_H
#define __HW_ID_H

#include <hw/common.h>
#include <csrbase.h>

#define ID_CSR(x)		MMPTR(ID_BASE+(x))

#define CSR_ID_SYSTEMH		ID_CSR(0x00)
#define CSR_ID_SYSTEML		ID_CSR(0x04)
#define CSR_ID_VERSIONH		ID_CSR(0x08)
#define CSR_ID_VERSIONL		ID_CSR(0x0C)
#define CSR_ID_FREQ3		ID_CSR(0x10)
#define CSR_ID_FREQ2		ID_CSR(0x14)
#define CSR_ID_FREQ1		ID_CSR(0x18)
#define CSR_ID_FREQ0		ID_CSR(0x1C)

#endif /* __HW_ID_H */
