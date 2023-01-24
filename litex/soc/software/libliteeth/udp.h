#ifndef __UDP_H
#define __UDP_H

#ifdef __cplusplus
extern "C" {
#endif

#define ETHMAC_EV_SRAM_WRITER	0x1
#define ETHMAC_EV_SRAM_READER	0x1

#define IPTOINT(a, b, c, d) ((a << 24)|(b << 16)|(c << 8)|d)

#define UDP_BUFSIZE (5*1532)

typedef void (*udp_callback)(unsigned int src_ip, unsigned short src_port, unsigned short dst_port, void *data, unsigned int length);

void udp_set_ip(unsigned int ip);
void udp_set_mac(const unsigned char *macaddr);
void udp_start(const unsigned char *macaddr, unsigned int ip);
int udp_arp_resolve(unsigned int ip);
void *udp_get_tx_buffer(void);
int udp_send(unsigned short src_port, unsigned short dst_port, unsigned int length);
void udp_set_callback(udp_callback callback);
void udp_service(void);

void eth_init(void);
void eth_mode(void);

#ifdef __cplusplus
}
#endif

#endif /* __UDP_H */
