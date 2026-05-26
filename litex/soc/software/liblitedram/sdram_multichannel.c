#include <generated/csr.h>

#include <liblitedram/sdram.h>

int sdram_init_all(void)
{
	int ok = 1;

#ifdef CSR_SDRAM_BASE
	ok &= sdram_init();
#endif

	return ok;
}
