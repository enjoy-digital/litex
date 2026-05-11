#include <generated/csr.h>

#if defined(CSR_SDRAM2_BASE) && defined(CSR_DDRPHY2_BASE)
#define LITEDRAM_INSTANCE          sdram2
#define LITEDRAM_PHY_HEADER        <generated/sdram2_phy.h>
#undef CSR_SDRAM_BASE
#undef CSR_DDRPHY_BASE
#undef CSR_DDRCTRL_BASE
#define CSR_SDRAM_BASE             CSR_SDRAM2_BASE
#define CSR_DDRPHY_BASE            CSR_DDRPHY2_BASE
#include <liblitedram/instance.h>
#include "accessors.c"
#endif
