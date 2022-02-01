#ifndef __I2C_H
#define __I2C_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>

typedef void (*i2c_write_t)(uint32_t v);
typedef uint32_t (*i2c_read_t)(void);

struct i2c_ops {
	i2c_write_t write;
	i2c_read_t read;
};

/* I2C frequency defaults to a safe value in range 10-100 kHz to be compatible with SMBus */
#ifndef I2C_FREQ_HZ
#define I2C_FREQ_HZ  50000
#endif

#define I2C_ADDR_WR(addr) ((addr) << 1)
#define I2C_ADDR_RD(addr) (((addr) << 1) | 1u)

void i2c_reset(void);
bool i2c_write(unsigned char slave_addr, unsigned char addr, const unsigned char *data, unsigned int len);
bool i2c_read(unsigned char slave_addr, unsigned char addr, unsigned char *data, unsigned int len, bool send_stop);
bool i2c_poll(unsigned char slave_addr);
int i2c_send_init_cmds(void);

#ifdef __cplusplus
}
#endif

#endif /* __I2C_H */
