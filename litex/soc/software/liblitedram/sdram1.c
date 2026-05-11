#include <generated/csr.h>

#ifdef CSR_SDRAM1_BASE
#define LITEDRAM_INSTANCE          sdram1
#define LITEDRAM_SDRAM_CSR_PREFIX  sdram1
#define LITEDRAM_DDRPHY_CSR_PREFIX ddrphy1
#define LITEDRAM_DDRCTRL_CSR_PREFIX ddrctrl1
#define LITEDRAM_PHY_HEADER        <generated/sdram1_phy.h>
#define CSR_SDRAM_BASE             CSR_SDRAM1_BASE
#ifdef CSR_DDRPHY1_BASE
#define CSR_DDRPHY_BASE            CSR_DDRPHY1_BASE
#endif
#include <liblitedram/instance.h>
#include "sdram.c"
#endif
