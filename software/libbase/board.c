#include <hw/csr.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <version.h>
#include <timer.h>
#include <board.h>

static const struct board_desc boards[1] = {
	{
		.id = 0x4D31, /* M1 */
		.name = "Milkymist One",
		.ethernet_phyadr = 1
	},
};

static const struct board_desc *get_board_desc_id(unsigned short int id)
{
	unsigned int i;

	for(i=0;i<sizeof(boards)/sizeof(boards[0]);i++)
		if(boards[i].id == id)
			return &boards[i];
	return NULL;
}

static const struct board_desc *get_board_desc(void)
{
	return get_board_desc_id(identifier_sysid_read());
}

int get_pcb_revision(void)
{
	/* TODO
	int r;
	unsigned int io;

	r = 0;
	io = CSR_GPIO_IN;
	if(io & GPIO_PCBREV0)
		r |= 0x1;
	if(io & GPIO_PCBREV1)
		r |= 0x2;
	if(io & GPIO_PCBREV2)
		r |= 0x4;
	if(io & GPIO_PCBREV3)
		r |= 0x8;
	return r;*/
	return 0;
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

const struct board_desc *brd_desc;

void board_init(void)
{
	int rev;
	char soc_version[13];

	brd_desc = get_board_desc();

	if(brd_desc == NULL) {
		printf("Running on unknown board, startup aborted.\n");
		while(1);
	}
	rev = get_pcb_revision();
	get_soc_version_formatted(soc_version);
	printf("Detected SoC %s at %dMHz on %s (PCB revision %d)\n", soc_version, get_system_frequency()/1000000,
	       brd_desc->name, rev);
	if(strcmp(soc_version, VERSION) != 0)
		printf("SoC and BIOS versions do not match!\n");
	if(rev > 2)
		printf("Unsupported PCB revision, please upgrade!\n");
}
