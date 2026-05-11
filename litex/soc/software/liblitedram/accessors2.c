#include <generated/csr.h>

#if defined(CSR_SDRAM2_BASE) && defined(CSR_DDRPHY2_BASE)
#define LITEDRAM_INSTANCE          sdram2
#define LITEDRAM_SDRAM_CSR_PREFIX  sdram2
#define LITEDRAM_DDRPHY_CSR_PREFIX ddrphy2
#define LITEDRAM_DDRCTRL_CSR_PREFIX ddrctrl2
#define LITEDRAM_PHY_HEADER        <generated/sdram2_phy.h>
#define CSR_SDRAM_BASE             CSR_SDRAM2_BASE
#define CSR_DDRPHY_BASE            CSR_DDRPHY2_BASE
#include <liblitedram/instance.h>
#include "accessors.c"
#endif
