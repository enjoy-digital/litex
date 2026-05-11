#include <generated/csr.h>

#ifdef CSR_SDRAM1_BASE
#define LITEDRAM_INSTANCE          sdram1
#define LITEDRAM_PHY_HEADER        <generated/sdram1_phy.h>
#undef CSR_SDRAM_BASE
#undef CSR_DDRPHY_BASE
#undef CSR_DDRCTRL_BASE
#define CSR_SDRAM_BASE             CSR_SDRAM1_BASE
#ifdef CSR_DDRPHY1_BASE
#define CSR_DDRPHY_BASE            CSR_DDRPHY1_BASE
#endif
#include <liblitedram/instance.h>
#include "sdram.c"
#endif
