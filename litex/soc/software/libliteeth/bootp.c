// This file is Copyright (c) 2024 Matthias Breithaupt <m.breithaupt@vogl-electronic.com>

// License: BSD

#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include <libbase/lfsr.h>

#include <libliteeth/inet.h>
#include <libliteeth/udp.h>
#include <libliteeth/bootp.h>

#define PORT_SERVER     67
#define PORT_CLIENT     68

#define OP_BOOTREQUEST  1
#define OP_BOOTREPLY    2

#define HTYPE_ETHERNET  1

#define HLEN_ETHERNET   6

#define FLAG_BROADCAST  0x8000

#define MAGIC_COOKIE    0x63825363

typedef struct {
    uint8_t op;
    uint8_t htype;
    uint8_t hlen;
    uint8_t hops;
    uint32_t xid;
    uint16_t secs;
    uint16_t flags;
    uint32_t ciaddr;
    uint32_t yiaddr;
    uint32_t siaddr;
    uint32_t giaddr;
    uint8_t chaddr[6];
    uint8_t pad[10];
    uint8_t sname[64];
    uint8_t file[128];
    uint32_t cookie;
    uint8_t vend[60];
} __attribute__((packed)) bootp_message;

static unsigned int seed = 0;

static void seed_from_mac(const unsigned char* macaddr)
{
	seed = macaddr[2] << 24 | macaddr[3] << 16 | macaddr[4] << 8 | macaddr[5];
}

static uint32_t rand32(void)
{
#ifdef CSR_TIMER0_UPTIME_CYCLES_ADDR
	timer0_uptime_latch_write(1);
	seed = timer0_uptime_cycles_read();
#endif
	uint32_t ret = lfsr(32, seed);
	seed = ret;
	return ret;
}

static int format_request(uint8_t *buf, uint32_t xid, const unsigned char* macaddr)
{
	uint16_t flags = FLAG_BROADCAST;
	uint16_t uptime = 0;
#ifdef CSR_TIMER0_UPTIME_CYCLES_ADDR
	timer0_uptime_latch_write(1);
	uptime = timer0_uptime_cycles_read()/CONFIG_CLOCK_FREQUENCY
#endif

	bootp_message *msg = (bootp_message*) buf;
	msg->op = OP_BOOTREQUEST;
	msg->htype = HTYPE_ETHERNET;
	msg->hlen = HLEN_ETHERNET;
	msg->hops = 0;
	msg->xid = htonl(xid);
	msg->secs = htons(uptime);
	msg->flags = htons(flags);
	msg->ciaddr = 0;
	msg->yiaddr = 0;
	msg->siaddr = 0;
	msg->giaddr = 0;
	memcpy(msg->chaddr, macaddr, 6);
	memset(msg->pad, 0, sizeof(msg->pad));
	memset(msg->sname, 0, sizeof(msg->sname));
	memset(msg->file, 0, sizeof(msg->file));
	msg->cookie = htonl(MAGIC_COOKIE);
	memset(msg->vend, 0, sizeof(msg->vend));
	return 300;
}

static uint32_t xid;
static uint8_t response_received;

static unsigned char mymac[6];
static uint32_t client_ip;
static uint32_t server_ip;
static char filename[128];

static uint8_t got_ip;

static void rx_callback(uint32_t src_ip, uint16_t src_port,
    uint16_t dst_port, void *buf, unsigned int length)
{
	bootp_message *msg;
	if(length < 300) return;
	msg = (bootp_message*) buf;
	if(dst_port != PORT_CLIENT) return;
	if(msg->op != OP_BOOTREPLY) return;
	if(msg->htype != HTYPE_ETHERNET) return;
	if(msg->hlen != HLEN_ETHERNET) return;
	if(msg->hops != 0) return;
	if(ntohl(msg->xid) != xid) return;
	if(memcmp(msg->chaddr, mymac, 6) != 0) return;
	client_ip = ntohl(msg->yiaddr);
	server_ip = ntohl(msg->siaddr);
	memcpy(filename, msg->file, sizeof(filename));
	filename[sizeof(filename) - 1] = 0;
	response_received = 1;
}

int bootp_get(const unsigned char *macaddr, uint32_t *_client_ip,
    uint32_t *_server_ip, char *_filename, size_t _len_filename,
    uint8_t force)
{
	int len, tries, i;
	int ret = -1;
        uint8_t *packet_data;
	uint8_t len_filename = 128;

	if (_len_filename < 128) {
		len_filename = _len_filename;
	}
	if (got_ip && !force) {
		ret = 0;
		goto copy;
	}
	response_received = 0;
	memcpy(mymac, macaddr, 6);

	client_ip = udp_get_ip();
	udp_set_ip(IPTOINT(0, 0, 0, 0));

#ifndef CSR_TIMER0_UPTIME_CYCLES_ADDR
	if(seed == 0) {
		seed_from_mac(macaddr);
	}
#endif

	udp_set_broadcast_callback((udp_callback) rx_callback);

	tries = 3;

	while(1) {
		xid = rand32();
		
		packet_data = udp_get_tx_buffer();
		len = format_request(packet_data, xid, macaddr);

		udp_set_broadcast();
		udp_send(PORT_CLIENT, PORT_SERVER, len);
		for(i=0;i<100000;i++) {
			udp_service();
			if(response_received) break;
		}
		if(response_received) break;
		tries--;
		if(tries == 0) {
			ret = -1;
			goto end;
		}
	}

	ret = 0;
	got_ip = 1;
copy:
	*_server_ip = server_ip;
	len = strlen(filename);
	memcpy(_filename, filename, len_filename);
	_filename[len_filename - 1] = 0;

end:
	*_client_ip = client_ip;
	udp_set_broadcast_callback(NULL);
	udp_set_ip(client_ip);

	return ret;
}
