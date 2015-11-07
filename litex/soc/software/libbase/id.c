#include <generated/csr.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <id.h>

void get_sysid_formatted(char *sysid)
{
	sysid[0] = identifier_sysid_read() >> 8;
	sysid[1] = identifier_sysid_read();
	sysid[2] = 0;
}

void id_print(void)
{
	char sysid[3];

	get_sysid_formatted(sysid);
	printf("Running on LiteX SoC (sysid:%s) at %dMHz\n", sysid, identifier_frequency_read()/1000000);
}
