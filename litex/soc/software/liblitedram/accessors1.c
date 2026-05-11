#include <generated/csr.h>

#if defined(CSR_SDRAM1_BASE) && defined(CSR_DDRPHY1_BASE)
#define LITEDRAM_INSTANCE          sdram1
#define LITEDRAM_PHY_HEADER        <generated/sdram1_phy.h>
#undef CSR_SDRAM_BASE
#undef CSR_DDRPHY_BASE
#undef CSR_DDRCTRL_BASE
#define CSR_SDRAM_BASE             CSR_SDRAM1_BASE
#define CSR_DDRPHY_BASE            CSR_DDRPHY1_BASE
#include <liblitedram/instance.h>
#include "accessors.c"
#endif
