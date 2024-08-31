#ifndef __BOOT_H
#define __BOOT_H

void set_local_ip(const char * ip_address);
void set_remote_ip(const char * ip_address);
void set_mac_addr(const char * mac_address);

void __attribute__((noreturn)) boot(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr);
int serialboot(void);
void netboot(int nb_params, char **params);
void flashboot(void);
void romboot(void);
void sdcardboot(void);
void sataboot(void);
extern void target_init(void) __attribute__((weak));
extern void target_boot(void) __attribute__((weak));
extern int copy_image_from_flash_to_ram(unsigned int flash_address, unsigned long ram_address);

#endif /* __BOOT_H */
