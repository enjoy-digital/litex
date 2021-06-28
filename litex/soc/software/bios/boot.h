#ifndef __BOOT_H
#define __BOOT_H

void set_local_ip(const char * ip_address);
void set_remote_ip(const char * ip_address);
void set_mac_addr(const char * mac_address);
void set_tftpserver_port(unsigned port_address);

void __attribute__((noreturn)) boot(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr);
int serialboot(void);
void netboot(int nb_params, char **params);
void flashboot(void);
void romboot(void);
void sdcardboot(void);
void sataboot(void);
int init_env_from_flash(void);
int get_env_params(char * base_env_params, unsigned int size);

#endif /* __BOOT_H */
