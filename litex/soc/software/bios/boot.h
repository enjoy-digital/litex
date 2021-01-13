#ifndef __BOOT_H
#define __BOOT_H

void set_local_ip(const char * ip_address);
void set_remote_ip(const char * ip_address);
void set_mac_addr(const char * mac_address);
int serialboot(void);
void netboot(void);
void flashboot(void);
void romboot(void);
void sdcardboot(void);
void sataboot(void);

#endif /* __BOOT_H */
