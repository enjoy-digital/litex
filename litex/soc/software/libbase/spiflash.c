#include <generated/csr.h>

#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)

#include <spiflash.h>

#define PAGE_PROGRAM_CMD 0x02
#define WRDI_CMD         0x04
#define RDSR_CMD         0x05
#define WREN_CMD         0x06
#define RD_CMD           0x0b
#define SE_CMD           0xd8

#define BITBANG_CLK         (1 << 1)
#define BITBANG_CS_N        (1 << 2)
#define BITBANG_DQ_INPUT    (1 << 3)

#define SR_WIP              1

static void flash_write_byte(unsigned char b);
static void flash_write_addr(unsigned int addr);
static void wait_for_device_ready(void);

#define min(a,b)  (a>b?b:a)

// flash_read/flash_write fcns make no assumptions on bitbang reg on entry.
// They will all leave the bitbang reg as 0x00 on exit.
static unsigned char flash_read_byte()
{
    int i;
    unsigned char b = 0;
    spiflash_bitbang_write(BITBANG_DQ_INPUT); // ~CS_N ~CLK DQ_INPUT

    for(i = 0; i < 8; i++) {
        b <<= 1;
        spiflash_bitbang_write(BITBANG_CLK | BITBANG_DQ_INPUT);
        b |= spiflash_miso_read();
        spiflash_bitbang_write(0           | BITBANG_DQ_INPUT);
    }

    spiflash_bitbang_write(0); // ~CS_N ~CLK
    return b;
}

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


// Bitbang commands will have flash_read/write fcns set up the bitbang reg
// on entry. On exit, bitbang command fcns will deassert CS_N bitbang
// regs (required) and then disable bitbang interface.
// write_to_flash_page leaves CS_N as 0. Why?
static void wait_for_device_ready(void)
{
    unsigned char sr;
    unsigned char i;
    do {
        sr = 0;
        flash_write_byte(RDSR_CMD);
        sr = flash_read_byte();
        spiflash_bitbang_write(BITBANG_CS_N);
    } while(sr & SR_WIP);
}

void erase_flash_sector(unsigned int addr)
{
    unsigned int sector_addr = addr & ~(SPIFLASH_SECTOR_SIZE - 1);

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

void read_from_flash(unsigned int addr, const unsigned char *c, unsigned int len)
{
    unsigned int i;

    spiflash_bitbang_en_write(1);

    wait_for_device_ready();

    flash_write_byte(RD_CMD);
    flash_write_addr(addr);
    for(i = 0; i < len; i++)
        *c++ = flash_read_byte();
    spiflash_bitbang_write(BITBANG_CS_N);

    wait_for_device_ready();

    spiflash_bitbang_en_write(0);
}

void write_to_flash_page(unsigned int addr, const unsigned char *c, unsigned int len)
{
    unsigned int i;

    if(len > SPIFLASH_PAGE_SIZE)
        len = SPIFLASH_PAGE_SIZE;

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

#define SPIFLASH_PAGE_MASK (SPIFLASH_PAGE_SIZE - 1)

void write_to_flash(unsigned int addr, const unsigned char *c, unsigned int len)
{
   unsigned int written = 0;

   if(addr & SPIFLASH_PAGE_MASK) {
       written = min(SPIFLASH_PAGE_SIZE - (addr & SPIFLASH_PAGE_MASK), len);
       write_to_flash_page(addr, c, written);
       c += written;
       addr += written;
       len -= written;
   }

   while(len > 0) {
       written = min(len, SPIFLASH_PAGE_SIZE);
       write_to_flash_page(addr, c, written);
       c += written;
       addr += written;
       len -= written;
   }
}

#endif /* CSR_SPIFLASH_BASE && SPIFLASH_PAGE_SIZE */
