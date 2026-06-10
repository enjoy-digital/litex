#ifndef __BOOT_H
#define __BOOT_H

typedef int (*boot_method_handler)(void);

struct boot_method {
	boot_method_handler handler;
	const char *name;
	int priority;
};

extern const struct boot_method *const __bios_boot_start[];
extern const struct boot_method *const __bios_boot_end[];

#define define_boot_method(method_name, handler_fn, priority_id) \
	static const struct boot_method s_boot_##method_name = { \
		.handler  = (boot_method_handler)handler_fn, \
		.name     = #method_name, \
		.priority = priority_id, \
	}; \
	const struct boot_method *__bios_boot_##method_name __attribute__((__used__)) \
	__attribute__((__section__(".bios_boot"))) = &s_boot_##method_name

// Set local, remote IP and MAC-address
void set_local_ip(const char * ip_address);
void set_remote_ip(const char * ip_address);
void set_mac_addr(const char * mac_address);

// Apply local IP and MAC-address to UDP driver
void net_init(void);

// Parse an IP address from a string to an array of 4x unsigned int
int parse_ip(const char *ip_address, unsigned int *ip_to_change);

void __attribute__((noreturn)) boot(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr);
int serialboot(void);
void netboot(int nb_params, char **params);
void flashboot(void);
void romboot(void);
void sdcardboot(int nb_params, char **params);
void sataboot(int nb_params, char **params);

#endif /* __BOOT_H */
