#include <generated/csr.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <id.h>


void get_ident(char *ident)
{
#ifdef CSR_IDENTIFIER_MEM_BASE
    int i;
    for(i=0;i<256;i++)
        ident[i] = MMPTR(CSR_IDENTIFIER_MEM_BASE + 4*i);
#else
    ident[0] = 0;
#endif
}
