#ifndef __UDP_H
#define __UDP_H

#ifdef __cplusplus
extern "C" {
#endif

#include <generated/soc.h>

#define ETHMAC_EV_SRAM_WRITER	0x1
#define ETHMAC_EV_SRAM_READER	0x1

#define IPTOINT(a, b, c, d) ((a << 24)|(b << 16)|(c << 8)|d)

#define UDP_BUFSIZE (5*1532)

typedef void (*udp_callback)(uint32_t src_ip, uint16_t src_port, uint16_t dst_port, void *data, uint32_t length);

void udp_set_ip(uint32_t ip);
uint32_t udp_get_ip(void);
void udp_set_mac(const uint8_t *macaddr);
void udp_start(const uint8_t *macaddr, uint32_t ip);
int udp_arp_resolve(uint32_t ip);
void *udp_get_tx_buffer(void);
int udp_send(uint16_t src_port, uint16_t dst_port, uint32_t length);
void udp_set_callback(udp_callback callback);
#ifdef ETH_UDP_BROADCAST
void udp_set_broadcast_callback(udp_callback callback);
void udp_set_broadcast(void);
#endif /* ETH_UDP_BROADCAST */
void udp_service(void);

int send_ping(uint32_t ip, unsigned short payload_length);

void eth_init(void);
void eth_mode(void);

#ifdef __cplusplus
}
#endif

#endif /* __UDP_H */
