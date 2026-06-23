#ifndef __TFTP_H
#define __TFTP_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stddef.h>
#include <stdint.h>

#define TFTP_MAX_SIZE_UNBOUNDED ((size_t)-1)

int tftp_get(uint32_t ip, uint16_t server_port, const char *filename,
    void *buffer, size_t max_size);
int tftp_put(uint32_t ip, uint16_t server_port, const char *filename,
    const void *buffer, int size);

#ifdef __cplusplus
}
#endif

#endif /* __TFTP_H */
