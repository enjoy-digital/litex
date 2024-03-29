#ifndef __TFTP_H
#define __TFTP_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

int tftp_get(uint32_t ip, uint16_t server_port, const char *filename,
    void *buffer);
int tftp_put(uint32_t ip, uint16_t server_port, const char *filename,
    const void *buffer, int size);

#ifdef __cplusplus
}
#endif

#endif /* __TFTP_H */

