#ifndef __HELPERS_H__
#define __HELPERS_H__

struct command_struct;

void dump_bytes(unsigned int *ptr, unsigned int count, unsigned long addr);
void crcbios(void);
void bios_print_section(const char *name);
void bios_print_status(const char *label, int success);
int get_param(char *buf, char **cmd, char **params);
struct command_struct *command_dispatcher(char *command, int nb_params, char **params);
void init_dispatcher(void);

#endif
