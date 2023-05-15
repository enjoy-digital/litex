#ifndef __SPIFLASH_H
#define __SPIFLASH_H

#ifdef __cplusplus
extern "C" {
#endif

void write_to_flash_page(unsigned int addr, const unsigned char *c, unsigned int len);
void erase_flash_sector(unsigned int addr);
void erase_flash(void);
void write_to_flash(unsigned int addr, const unsigned char *c, unsigned int len);

#ifdef __cplusplus
}
#endif

#endif /* __SPIFLASH_H */
