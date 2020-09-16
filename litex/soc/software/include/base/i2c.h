#ifndef __I2C_H
#define __I2C_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>

/* I2C frequency defaults to a safe value in range 10-100 kHz to be compatible with SMBus */
#ifndef I2C_FREQ_HZ
#define I2C_FREQ_HZ  50000
#endif

#define I2C_ADDR_WR(addr) ((addr) << 1)
#define I2C_ADDR_RD(addr) (((addr) << 1) | 1u)

void i2c_reset(void);

/* Reads and writes with single byte register addresses */
bool i2c_write(unsigned char slave_addr, unsigned char addr, const unsigned char *data, unsigned int len);
bool i2c_read(unsigned char slave_addr, unsigned char addr, unsigned char *data, unsigned int len, bool send_stop);

/* Reads and writes with two byte register addresses */
bool i2c_write2(unsigned char slave_addr, unsigned short addr, const unsigned char *data, unsigned int len);
bool i2c_read2(unsigned char slave_addr, unsigned short addr, unsigned char *data, unsigned int len, bool send_stop);

/* Read/write with arbitrary register length */
bool i2c_writen(unsigned char slave_addr, unsigned char *addr, int addr_len, const unsigned char *data, unsigned int len);
bool i2c_readn(unsigned char slave_addr, unsigned char *addr, int addr_len, unsigned char *data, unsigned int len, bool send_stop);

#ifdef __cplusplus
}
#endif

#endif /* __I2C_H */
