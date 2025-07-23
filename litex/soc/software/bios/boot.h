#ifndef __BOOT_H
#define __BOOT_H

// Set local, remote IP and MAC-address
void set_local_ip(const char * ip_address);
void set_remote_ip(const char * ip_address);
void set_mac_addr(const char * mac_address);

// Apply local IP and MAC-address to UDP driver
void net_init(void);

// Parse an IP address from a string to an array of 4x unsigned int
unsigned char parse_ip(const char * ip_address, unsigned int * ip_to_change);

void __attribute__((noreturn)) boot(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr);
int serialboot(void);
void netboot(int nb_params, char **params);
void flashboot(void);
void romboot(void);
void sdcardboot(void);
void sataboot(void);

#endif /* __BOOT_H */
