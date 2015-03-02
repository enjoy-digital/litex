#include <generated/csr.h>

#include <spiflash.h>

#ifdef CSR_SPIFLASH_BASE

#define PAGE_PROGRAM_CMD    (0x02)
#define WRDI_CMD        (0x04)
#define RDSR_CMD        (0x05)
#define WREN_CMD        (0x06)
#define SE_CMD            (0x20)

#define BITBANG_CLK        (1 << 1)
#define BITBANG_CS_N        (1 << 2)
#define BITBANG_DQ_INPUT    (1 << 3)

#define SR_WIP            (1)

#define PAGE_SIZE (256)
#define PAGE_MASK (PAGE_SIZE - 1)
#define SECTOR_SIZE (4096)
#define SECTOR_MASK (SECTOR_SIZE - 1)

static void flash_write_byte(unsigned char b);
static void flash_write_addr(unsigned int addr);
static void wait_for_device_ready(void);

#define min(a,b)  (a>b?b:a)

static void flash_write_byte(unsigned char b)
{
    int i;
    spiflash_bitbang_write(0); // ~CS_N ~CLK

    for(i = 0; i < 8; i++, b <<= 1) {

        spiflash_bitbang_write((b & 0x80) >> 7);
        spiflash_bitbang_write(((b & 0x80) >> 7) | BITBANG_CLK);
    }

    spiflash_bitbang_write(0); // ~CS_N ~CLK

}

static void flash_write_addr(unsigned int addr)
{
    int i;
    spiflash_bitbang_write(0);

    for(i = 0; i < 24; i++, addr <<= 1) {
        spiflash_bitbang_write((addr & 0x800000) >> 23);
        spiflash_bitbang_write(((addr & 0x800000) >> 23) | BITBANG_CLK);
    }

    spiflash_bitbang_write(0);
}

static void wait_for_device_ready(void)
{
    unsigned char sr;
    unsigned char i;
    do {
        sr = 0;
        flash_write_byte(RDSR_CMD);
        spiflash_bitbang_write(BITBANG_DQ_INPUT);
        for(i = 0; i < 8; i++) {
            sr <<= 1;
            spiflash_bitbang_write(BITBANG_CLK | BITBANG_DQ_INPUT);
            sr |= spiflash_miso_read();
            spiflash_bitbang_write(0           | BITBANG_DQ_INPUT);
        }
        spiflash_bitbang_write(0);
        spiflash_bitbang_write(BITBANG_CS_N);
    } while(sr & SR_WIP);
}

void erase_flash_sector(unsigned int addr)
{
    unsigned int sector_addr = addr & ~(SECTOR_MASK);

    spiflash_bitbang_en_write(1);

    wait_for_device_ready();

    flash_write_byte(WREN_CMD);
    spiflash_bitbang_write(BITBANG_CS_N);

    flash_write_byte(SE_CMD);
    flash_write_addr(sector_addr);
    spiflash_bitbang_write(BITBANG_CS_N);

    wait_for_device_ready();

    spiflash_bitbang_en_write(0);
}

void write_to_flash_page(unsigned int addr, unsigned char *c, unsigned int len)
{
    unsigned int i;

    if(len > PAGE_SIZE)
        len = PAGE_SIZE;

    spiflash_bitbang_en_write(1);

    wait_for_device_ready();

    flash_write_byte(WREN_CMD);
    spiflash_bitbang_write(BITBANG_CS_N);
    flash_write_byte(PAGE_PROGRAM_CMD);
    flash_write_addr((unsigned int)addr);
    for(i = 0; i < len; i++)
        flash_write_byte(*c++);

    spiflash_bitbang_write(BITBANG_CS_N);
    spiflash_bitbang_write(0);

    wait_for_device_ready();

    spiflash_bitbang_en_write(0);
}

#endif
