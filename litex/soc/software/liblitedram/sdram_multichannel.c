#include <generated/csr.h>

#include <liblitedram/sdram.h>

int sdram_init_all(void)
{
	int ok = 1;

#ifdef CSR_SDRAM_BASE
	ok &= sdram_init();
#endif
#ifdef CSR_SDRAM1_BASE
	ok &= sdram1_init();
#endif
#ifdef CSR_SDRAM2_BASE
	ok &= sdram2_init();
#endif
#ifdef CSR_SDRAM3_BASE
	ok &= sdram3_init();
#endif

	return ok;
}
