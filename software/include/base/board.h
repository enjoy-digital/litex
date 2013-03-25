#ifndef __BOARD_H
#define __BOARD_H

#ifdef __cplusplus
extern "C" {
#endif

#define BOARD_NAME_LEN 32

struct board_desc {
	unsigned short int id;
	char name[BOARD_NAME_LEN];
	unsigned int ethernet_phyadr;
};

int get_pcb_revision(void);
void get_soc_version(unsigned int *major, unsigned int *minor, unsigned int *subminor, unsigned int *rc);
void get_soc_version_formatted(char *version);

extern const struct board_desc *brd_desc;
void board_init(void);

#ifdef __cplusplus
}
#endif

#endif /* __BOARD_H */
