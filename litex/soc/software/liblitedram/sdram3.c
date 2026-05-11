#include <generated/csr.h>

#ifdef CSR_SDRAM3_BASE
#define LITEDRAM_INSTANCE          sdram3
#define LITEDRAM_SDRAM_CSR_PREFIX  sdram3
#define LITEDRAM_DDRPHY_CSR_PREFIX ddrphy3
#define LITEDRAM_DDRCTRL_CSR_PREFIX ddrctrl3
#define LITEDRAM_PHY_HEADER        <generated/sdram3_phy.h>
#define CSR_SDRAM_BASE             CSR_SDRAM3_BASE
#ifdef CSR_DDRPHY3_BASE
#define CSR_DDRPHY_BASE            CSR_DDRPHY3_BASE
#endif
#include <liblitedram/instance.h>
#include "sdram.c"
#endif
