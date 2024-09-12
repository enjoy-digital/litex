#ifndef __BOOTP_H
#define __BOOTP_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

int bootp_get(const unsigned char *macaddr, uint32_t *client_ip,
    uint32_t *server_ip, char *filename, size_t len_filename,
    uint8_t force);

int bootp_has_ip(void);

#ifdef __cplusplus
}
#endif

#endif /* __BOOTP_H */

