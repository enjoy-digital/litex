#include <generated/csr.h>

#ifdef CSR_SDRAM2_BASE
#define LITEDRAM_INSTANCE          sdram2
#define LITEDRAM_PHY_HEADER        <generated/sdram2_phy.h>
#undef CSR_SDRAM_BASE
#undef CSR_DDRPHY_BASE
#undef CSR_DDRCTRL_BASE
#define CSR_SDRAM_BASE             CSR_SDRAM2_BASE
#ifdef CSR_DDRPHY2_BASE
#define CSR_DDRPHY_BASE            CSR_DDRPHY2_BASE
#endif
#include <liblitedram/instance.h>
#include "sdram.c"
#endif
