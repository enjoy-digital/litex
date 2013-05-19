#include <hw/csr.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <version.h>
#include <id.h>

void get_sysid_formatted(char *sysid)
{
	sysid[0] = identifier_sysid_read() >> 8;
	sysid[1] = identifier_sysid_read();
	sysid[2] = 0;
}

void get_soc_version(unsigned int *major, unsigned int *minor, unsigned int *subminor, unsigned int *rc)
{
	unsigned int id;

	id = identifier_version_read();
	*major = (id & 0xf000) >> 12;
	*minor = (id & 0x0f00) >> 8;
	*subminor = (id & 0x00f0) >> 4;
	*rc = id & 0x000f;
}

void get_soc_version_formatted(char *version)
{
	unsigned int major, minor, subminor, rc;

	get_soc_version(&major, &minor, &subminor, &rc);

	version += sprintf(version, "%u.%u", major, minor);
	if(subminor != 0)
		version += sprintf(version, ".%u", subminor);
	if(rc != 0)
		sprintf(version, "RC%u", rc);
}

void id_print(void)
{
	char soc_version[13];
	char sysid[3];

	get_soc_version_formatted(soc_version);
	get_sysid_formatted(sysid);
	printf("Running on Milkymist-ng SoC %s (sysid:%s) at %dMHz\n", soc_version, sysid, identifier_frequency_read()/1000000);
}
