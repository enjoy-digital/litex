#include <generated/csr.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <id.h>


void get_ident(char *ident)
{
#ifdef CSR_IDENTIFIER_MEM_BASE
    int len, i;
    
    len = MMPTR(CSR_IDENTIFIER_MEM_BASE);
    for(i=0;i<len;i++)
        ident[i] = MMPTR(CSR_IDENTIFIER_MEM_BASE + 4 + i*4);
    ident[i] = 0;
#else
    ident[0] = 0;
#endif
}
