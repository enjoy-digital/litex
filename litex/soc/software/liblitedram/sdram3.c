#include <generated/csr.h>

#ifdef CSR_SDRAM3_BASE
#define LITEDRAM_INSTANCE          sdram3
#define LITEDRAM_PHY_HEADER        <generated/sdram3_phy.h>
#undef CSR_SDRAM_BASE
#undef CSR_DDRPHY_BASE
#undef CSR_DDRCTRL_BASE
#define CSR_SDRAM_BASE             CSR_SDRAM3_BASE
#ifdef CSR_DDRPHY3_BASE
#define CSR_DDRPHY_BASE            CSR_DDRPHY3_BASE
#endif
#include <liblitedram/instance.h>
#include "sdram.c"
#endif
