#ifndef __DHCP_H
#define __DHCP_H

#include <stdint.h>

int dhcp_resolve(const uint8_t *macaddr, uint32_t *ip_address);

#endif /* __DHCP_H */
