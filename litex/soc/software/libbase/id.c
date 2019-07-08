#include <generated/csr.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <id.h>

#define DFII_ADDR_SHIFT CONFIG_CSR_ALIGNMENT/8

void get_ident(char *ident)
{
#ifdef CSR_IDENTIFIER_MEM_BASE
    int i;
    for(i=0;i<256;i++)
        ident[i] = MMPTR(CSR_IDENTIFIER_MEM_BASE + DFII_ADDR_SHIFT*i);
#else
    ident[0] = 0;
#endif
}
