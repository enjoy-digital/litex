#ifndef __BOOT_H
#define __BOOT_H

int serialboot(void);
void netboot(void);
void flashboot(void);
void romboot(void);

#ifdef CSR_SPISDCARD_BASE
void spisdcardboot(void);
#endif

#endif /* __BOOT_H */
