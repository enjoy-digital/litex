#ifndef __SYSTEM_H
#define __SYSTEM_H

void flush_cpu_icache(void);
void flush_cpu_dcache(void);
__attribute__((noreturn)) void reboot(void);
__attribute__((noreturn)) void reconf(void);

#endif /* __SYSTEM_H */
