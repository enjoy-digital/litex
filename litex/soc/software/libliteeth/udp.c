// This file is Copyright (c) 2013 Werner Almesberger <werner@almesberger.net>
// This file is Copyright (c) 2014-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
// This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2018 Jean-François Nguyen <jf@lse.epita.fr>
// This file is Copyright (c) 2013 Robert Jordens <jordens@gmail.com>
// License: BSD

#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/soc.h>

#ifdef CSR_ETHMAC_BASE

#include <stdio.h>

#include <system.h>

#include <libbase/crc.h>

#include <libliteeth/inet.h>
#include <libliteeth/udp.h>

//#define ETH_UDP_TX_DEBUG
//#define ETH_UDP_RX_DEBUG

#define ETHERTYPE_ARP 0x0806
#define ETHERTYPE_IP  0x0800

#ifdef CSR_ETHMAC_PREAMBLE_CRC_ADDR
#define HW_PREAMBLE_CRC
#endif

struct ethernet_header {
#ifndef HW_PREAMBLE_CRC
	uint8_t preamble[8];
#endif
	uint8_t destmac[6];
	uint8_t srcmac[6];
	uint16_t ethertype;
} __attribute__((packed));

static void fill_eth_header(struct ethernet_header *h, const uint8_t *destmac, const uint8_t *srcmac, uint16_t ethertype)
{
	int i;

#ifndef HW_PREAMBLE_CRC
	for(i=0;i<7;i++)
		h->preamble[i] = 0x55;
	h->preamble[7] = 0xd5;
#endif
	for(i=0;i<6;i++)
		h->destmac[i] = destmac[i];
	for(i=0;i<6;i++)
		h->srcmac[i] = srcmac[i];
	h->ethertype = htons(ethertype);
}

#define ARP_HWTYPE_ETHERNET 0x0001
#define ARP_PROTO_IP        0x0800
#ifndef HW_PREAMBLE_CRC
#define ARP_PACKET_LENGTH 68
#else
#define ARP_PACKET_LENGTH 60
#endif

#define ARP_OPCODE_REQUEST  0x0001
#define ARP_OPCODE_REPLY    0x0002

struct arp_frame {
	uint16_t hwtype;
	uint16_t proto;
	uint8_t hwsize;
	uint8_t protosize;
	uint16_t opcode;
	uint8_t sender_mac[6];
	uint32_t sender_ip;
	uint8_t target_mac[6];
	uint32_t target_ip;
	uint8_t padding[18];
} __attribute__((packed));

#define IP_IPV4			0x45
#define IP_DONT_FRAGMENT	0x4000
#define IP_TTL			64
#define IP_PROTO_UDP		0x11
#define IP_PROTO_ICMP		0x01

struct ip_header {
	uint8_t version;
	uint8_t diff_services;
	uint16_t total_length;
	uint16_t identification;
	uint16_t fragment_offset;
	uint8_t ttl;
	uint8_t proto;
	uint16_t checksum;
	uint32_t src_ip;
	uint32_t dst_ip;
} __attribute__((packed));

struct udp_header {
	uint16_t src_port;
	uint16_t dst_port;
	uint16_t length;
	uint16_t checksum;
} __attribute__((packed));

struct udp_frame {
	struct ip_header ip;
	struct udp_header udp;
	char payload[];
} __attribute__((packed));

#define ICMP_ECHO_REPLY 0x00
#define ICMP_ECHO 0x08

struct icmp_header {
	unsigned char type;
	unsigned char code;
	unsigned short checksum;
	unsigned short identifier;
	unsigned short sequence_number;
} __attribute__((packed));

struct icmp_frame {
	struct ip_header ip;
	struct icmp_header icmp;
	char payload[];
} __attribute__((packed));

struct ethernet_frame {
	struct ethernet_header eth_header;
	union {
		struct arp_frame arp;
		struct udp_frame udp;
		struct icmp_frame icmp;
	} contents;
} __attribute__((packed));

typedef union {
	struct ethernet_frame frame;
	uint8_t raw[ETHMAC_SLOT_SIZE];
} ethernet_buffer;

static uint32_t rxslot;
static uint32_t rxlen;
static ethernet_buffer *rxbuffer;

static uint32_t txslot;
static uint32_t txlen;
static ethernet_buffer *txbuffer;

static void send_packet(void)
{
	/* wait buffer to be available */
	while(!(ethmac_sram_reader_ready_read()));

	/* fill txbuffer */
#ifndef HW_PREAMBLE_CRC
	uint32_t crc;
	crc = crc32(&txbuffer->raw[8], txlen-8);
	txbuffer->raw[txlen  ] = (crc & 0xff);
	txbuffer->raw[txlen+1] = (crc & 0xff00) >> 8;
	txbuffer->raw[txlen+2] = (crc & 0xff0000) >> 16;
	txbuffer->raw[txlen+3] = (crc & 0xff000000) >> 24;
	txlen += 4;
#endif

#ifdef ETH_UDP_TX_DEBUG
	int j;
	printf(">>>> txlen : %d\n", txlen);
	for(j=0;j<txlen;j++)
		printf("%02x",txbuffer->raw[j]);
	printf("\n");
#endif

	/* fill slot, length and send */
	ethmac_sram_reader_slot_write(txslot);
	ethmac_sram_reader_length_write(txlen);
	ethmac_sram_reader_start_write(1);

	/* update txslot / txbuffer */
	txslot = (txslot+1)%ETHMAC_TX_SLOTS;
	txbuffer = (ethernet_buffer *)(ETHMAC_BASE + ETHMAC_SLOT_SIZE * (ETHMAC_RX_SLOTS + txslot));
}

static uint8_t my_mac[6];
static uint32_t my_ip;

void udp_set_ip(uint32_t ip)
{
	my_ip = ip;
}

uint32_t udp_get_ip(void)
{
	return my_ip;
}

void udp_set_mac(const uint8_t *macaddr)
{
	int i;
	for(i=0;i<6;i++)
    		my_mac[i] = macaddr[i];
}

/* ARP cache - one entry only */
static uint8_t cached_mac[6];
static uint32_t cached_ip;

#ifdef ETH_UDP_BROADCAST
void udp_set_broadcast(void)
{
	int i;
	for(i=0;i<6;i++)
		cached_mac[i] = 0xFF;
	cached_ip = IPTOINT(255, 255, 255, 255);
}
#endif /* ETH_UDP_BROADCAST */

static void process_arp(void)
{
	const struct arp_frame *rx_arp = &rxbuffer->frame.contents.arp;
	struct arp_frame *tx_arp = &txbuffer->frame.contents.arp;

	if(rxlen < ARP_PACKET_LENGTH) return;
	if(ntohs(rx_arp->hwtype) != ARP_HWTYPE_ETHERNET) return;
	if(ntohs(rx_arp->proto) != ARP_PROTO_IP) return;
	if(rx_arp->hwsize != 6) return;
	if(rx_arp->protosize != 4) return;

	if(ntohs(rx_arp->opcode) == ARP_OPCODE_REPLY) {
		if(ntohl(rx_arp->sender_ip) == cached_ip) {
			int i;
			for(i=0;i<6;i++)
				cached_mac[i] = rx_arp->sender_mac[i];
		}
		return;
	}
	if(ntohs(rx_arp->opcode) == ARP_OPCODE_REQUEST) {
		if(ntohl(rx_arp->target_ip) == my_ip) {
			int i;

			fill_eth_header(&txbuffer->frame.eth_header,
				rx_arp->sender_mac,
				my_mac,
				ETHERTYPE_ARP);
			txlen = ARP_PACKET_LENGTH;
			tx_arp->hwtype = htons(ARP_HWTYPE_ETHERNET);
			tx_arp->proto = htons(ARP_PROTO_IP);
			tx_arp->hwsize = 6;
			tx_arp->protosize = 4;
			tx_arp->opcode = htons(ARP_OPCODE_REPLY);
			tx_arp->sender_ip = htonl(my_ip);
			for (int i = 0; i < sizeof(tx_arp->padding); i++)
				tx_arp->padding[i] = 0;
			for(i=0;i<6;i++)
				tx_arp->sender_mac[i] = my_mac[i];
			tx_arp->target_ip = htonl(ntohl(rx_arp->sender_ip));
			for(i=0;i<6;i++)
				tx_arp->target_mac[i] = rx_arp->sender_mac[i];
			send_packet();
		}
		return;
	}
}

static const uint8_t broadcast[6] = {0xff, 0xff, 0xff, 0xff, 0xff, 0xff};

int udp_arp_resolve(uint32_t ip)
{
	struct arp_frame *arp;
	int i;
	int tries;
	int timeout;

	if(cached_ip == ip) {
		for(i=0;i<6;i++)
			if(cached_mac[i]) return 1;
	}
	cached_ip = ip;
	for(i=0;i<6;i++)
		cached_mac[i] = 0;

	for(tries=0;tries<8;tries++) {
		/* Send an ARP request */
		fill_eth_header(&txbuffer->frame.eth_header,
				broadcast,
				my_mac,
				ETHERTYPE_ARP);
		txlen = ARP_PACKET_LENGTH;
		arp = &txbuffer->frame.contents.arp;
		arp->hwtype = htons(ARP_HWTYPE_ETHERNET);
		arp->proto = htons(ARP_PROTO_IP);
		arp->hwsize = 6;
		arp->protosize = 4;
		arp->opcode = htons(ARP_OPCODE_REQUEST);
		arp->sender_ip = htonl(my_ip);
		for (int i = 0; i < sizeof(arp->padding); i++)
			arp->padding[i] = 0;
		for(i=0;i<6;i++)
			arp->sender_mac[i] = my_mac[i];
		arp->target_ip = htonl(ip);
		for(i=0;i<6;i++)
			arp->target_mac[i] = 0;

		send_packet();

		/* Do we get a reply ? */
		for(timeout=0;timeout<100000;timeout++) {
			udp_service();
			for(i=0;i<6;i++)
				if(cached_mac[i]) return 1;
		}
	}

	return 0;
}

static uint16_t ip_checksum(uint32_t r, void *buffer, uint32_t length, int complete)
{
	uint8_t *ptr;
	uint32_t i;

	ptr = (uint8_t *)buffer;
	length >>= 1;

	for(i=0;i<length;i++)
		r += ((uint32_t)(ptr[2*i]) << 8)|(uint32_t)(ptr[2*i+1]) ;

	/* Add overflows */
	while(r >> 16)
		r = (r & 0xffff) + (r >> 16);

	if(complete) {
		r = ~r;
		r &= 0xffff;
		if(r == 0) r = 0xffff;
	}
	return r;
}

void *udp_get_tx_buffer(void)
{
	return txbuffer->frame.contents.udp.payload;
}

struct pseudo_header {
	uint32_t src_ip;
	uint32_t dst_ip;
	uint8_t zero;
	uint8_t proto;
	uint16_t length;
} __attribute__((packed));

int udp_send(uint16_t src_port, uint16_t dst_port, uint32_t length)
{
	struct pseudo_header h;
	uint32_t r;

	if((cached_mac[0] == 0) && (cached_mac[1] == 0) && (cached_mac[2] == 0)
		&& (cached_mac[3] == 0) && (cached_mac[4] == 0) && (cached_mac[5] == 0))
		return 0;

	txlen = length + sizeof(struct ethernet_header) + sizeof(struct udp_frame);
	if(txlen < ARP_PACKET_LENGTH) txlen = ARP_PACKET_LENGTH;

	fill_eth_header(&txbuffer->frame.eth_header,
		cached_mac,
		my_mac,
		ETHERTYPE_IP);

	txbuffer->frame.contents.udp.ip.version = IP_IPV4;
	txbuffer->frame.contents.udp.ip.diff_services = 0;
	txbuffer->frame.contents.udp.ip.total_length = htons(length + sizeof(struct udp_frame));
	txbuffer->frame.contents.udp.ip.identification = htons(0);
	txbuffer->frame.contents.udp.ip.fragment_offset = htons(IP_DONT_FRAGMENT);
	txbuffer->frame.contents.udp.ip.ttl = IP_TTL;
	h.proto = txbuffer->frame.contents.udp.ip.proto = IP_PROTO_UDP;
	txbuffer->frame.contents.udp.ip.checksum = 0;
	h.src_ip = txbuffer->frame.contents.udp.ip.src_ip = htonl(my_ip);
	h.dst_ip = txbuffer->frame.contents.udp.ip.dst_ip = htonl(cached_ip);
	txbuffer->frame.contents.udp.ip.checksum = htons(ip_checksum(0, &txbuffer->frame.contents.udp.ip,
		sizeof(struct ip_header), 1));

	txbuffer->frame.contents.udp.udp.src_port = htons(src_port);
	txbuffer->frame.contents.udp.udp.dst_port = htons(dst_port);
	h.length = txbuffer->frame.contents.udp.udp.length = htons(length + sizeof(struct udp_header));
	txbuffer->frame.contents.udp.udp.checksum = 0;

	h.zero = 0;
	r = ip_checksum(0, &h, sizeof(struct pseudo_header), 0);
	if(length & 1) {
		txbuffer->frame.contents.udp.payload[length] = 0;
		length++;
	}
	r = ip_checksum(r, &txbuffer->frame.contents.udp.udp,
		sizeof(struct udp_header)+length, 1);
	txbuffer->frame.contents.udp.udp.checksum = htons(r);

	send_packet();

	return 1;
}

static unsigned ping_seq_number = 0;
static uint64_t ping_ts_send = 0;

int send_ping(uint32_t ip, unsigned short payload_length)
{
	if(!udp_arp_resolve(ip)) {
		printf("ARP failed");
		return -1;
	}

	fill_eth_header(
		&txbuffer->frame.eth_header,
		cached_mac,
		my_mac,
		ETHERTYPE_IP
	);

	struct icmp_frame *tx_icmp = &txbuffer->frame.contents.icmp;

	tx_icmp->ip.version = IP_IPV4;
	tx_icmp->ip.diff_services = 0;
	tx_icmp->ip.total_length = htons(payload_length + sizeof(struct icmp_frame));
	tx_icmp->ip.identification = htons(0);
	tx_icmp->ip.fragment_offset = htons(IP_DONT_FRAGMENT);
	tx_icmp->ip.ttl = IP_TTL;
	tx_icmp->ip.proto = IP_PROTO_ICMP;
	tx_icmp->ip.checksum = 0;
	tx_icmp->ip.src_ip = htonl(my_ip);
	tx_icmp->ip.dst_ip = htonl(ip);
	tx_icmp->ip.checksum = htons(ip_checksum(
		0, &tx_icmp->ip, sizeof(struct ip_header), 1
	));

	tx_icmp->icmp.type = ICMP_ECHO;
	tx_icmp->icmp.code = 0;
	tx_icmp->icmp.identifier = 0xbe7c;
	tx_icmp->icmp.sequence_number = ++ping_seq_number;
	for (unsigned i=0; i<payload_length; i++)
		tx_icmp->payload[i] = i;

	tx_icmp->icmp.checksum = 0;
	unsigned short r = ip_checksum(
		0,
		&tx_icmp->icmp,
		payload_length + sizeof(struct icmp_header),
		1
	);
	tx_icmp->icmp.checksum = htons(r);

	txlen = payload_length + sizeof(struct ethernet_header) + sizeof(struct icmp_frame);
	send_packet();

	ping_ts_send = 1;
#ifdef CSR_TIMER0_UPTIME_CYCLES_ADDR
	timer0_uptime_latch_write(1);
	ping_ts_send = timer0_uptime_cycles_read();
#endif

	// Do we get a reply ?
	for(unsigned timeout = 0; timeout < 10000; timeout++) {
		udp_service();
		if(ping_ts_send == 0)
			return 0;
	}

	return -2;
}

static void process_icmp(void)
{
	if (rxlen < (sizeof(struct ethernet_header) + sizeof(struct icmp_frame)))
		return;

	const struct icmp_frame *rx_icmp = &rxbuffer->frame.contents.icmp;
	struct icmp_frame *tx_icmp = &txbuffer->frame.contents.icmp;

	if(ntohs(rx_icmp->ip.total_length) < sizeof(struct icmp_frame))
		return;

	unsigned short length = ntohs(rx_icmp->ip.total_length) - sizeof(struct icmp_frame);

	if(rx_icmp->icmp.type == ICMP_ECHO) {
		fill_eth_header(
			&txbuffer->frame.eth_header,
			rxbuffer->frame.eth_header.srcmac,
			my_mac,
			ETHERTYPE_IP
		);

		tx_icmp->ip.version = IP_IPV4;
		tx_icmp->ip.diff_services = 0;
		tx_icmp->ip.total_length = htons(length + sizeof(struct icmp_frame));
		tx_icmp->ip.identification = htons(0);
		tx_icmp->ip.fragment_offset = htons(IP_DONT_FRAGMENT);
		tx_icmp->ip.ttl = IP_TTL;
		tx_icmp->ip.proto = IP_PROTO_ICMP;
		tx_icmp->ip.checksum = 0;
		tx_icmp->ip.src_ip = htonl(my_ip);
		tx_icmp->ip.dst_ip = rxbuffer->frame.contents.icmp.ip.src_ip;
		tx_icmp->ip.checksum = htons(ip_checksum(
			0, &tx_icmp->ip, sizeof(struct ip_header), 1
		));

		tx_icmp->icmp.type = ICMP_ECHO_REPLY;
		tx_icmp->icmp.code = 0;
		tx_icmp->icmp.identifier = rx_icmp->icmp.identifier;
		tx_icmp->icmp.sequence_number = rx_icmp->icmp.sequence_number;
		for (unsigned i=0; i<length; i++)
			tx_icmp->payload[i] = rx_icmp->payload[i];

		tx_icmp->icmp.checksum = 0;
		unsigned short r = ip_checksum(
			0,
			&tx_icmp->icmp,
			length + sizeof(struct icmp_header),
			1
		);
		tx_icmp->icmp.checksum = htons(r);

		txlen = length + sizeof(struct ethernet_header) + sizeof(struct icmp_frame);
		send_packet();
	} else if (rx_icmp->icmp.type == ICMP_ECHO_REPLY) {
		uint8_t *tmp = (uint8_t *)(&rx_icmp->ip.src_ip);
		printf("%d bytes from %d.%d.%d.%d: ", length, tmp[0], tmp[1], tmp[2], tmp[3]);

		if (rx_icmp->icmp.sequence_number != ping_seq_number) {
			printf("invalid sequence number %d", rx_icmp->icmp.sequence_number);
			return;
		}
		if (rx_icmp->icmp.identifier != 0xbe7c) {
			printf("invalid identifier %d", rx_icmp->icmp.identifier);
			return;
		}

		printf("icmp_seq=%d", rx_icmp->icmp.sequence_number);

		#ifdef CSR_TIMER0_UPTIME_CYCLES_ADDR
			uint64_t ping_ts_receive = 0;
			timer0_uptime_latch_write(1);
			ping_ts_receive = timer0_uptime_cycles_read();
			int dt_us = ping_ts_receive - ping_ts_send;
			dt_us /= (CONFIG_CLOCK_FREQUENCY / 1000 / 1000);
			if (dt_us >= 10000)
				printf(" time=%d ms", dt_us / 1000);
			else
				printf(" time=%d us", dt_us);
		#endif

		ping_ts_send = 0;
		printf("\n");
	}
}

static udp_callback rx_callback;
#ifdef ETH_UDP_BROADCAST
static udp_callback bx_callback;
#endif /* ETH_UDP_BROADCAST */

static void process_udp(void)
{
	if(rxlen < (sizeof(struct ethernet_header)+sizeof(struct udp_frame))) return;
	struct udp_frame *udp_ip = &rxbuffer->frame.contents.udp;
	/* We don't verify UDP and IP checksums and rely on the Ethernet checksum solely */
	// check disabled for QEMU compatibility
	//if(rxbuffer->frame.contents.udp.ip.diff_services != 0) return;
	if(ntohs(udp_ip->ip.total_length) < sizeof(struct udp_frame)) return;
	// check disabled for QEMU compatibility
	//if(ntohs(rxbuffer->frame.contents.udp.ip.fragment_offset) != IP_DONT_FRAGMENT) return;
	if(udp_ip->ip.proto != IP_PROTO_UDP) return;
	if(ntohs(udp_ip->udp.length) < sizeof(struct udp_header)) return;
	if(ntohl(udp_ip->ip.dst_ip) != my_ip) {
#ifdef ETH_UDP_BROADCAST
		/* If the destination IP is not mine, check if it is a broadcast */
		if(ntohl(udp_ip->ip.dst_ip) == IPTOINT(255, 255, 255, 255) && bx_callback) {
			bx_callback(ntohl(udp_ip->ip.src_ip), ntohs(udp_ip->udp.src_port), ntohs(udp_ip->udp.dst_port),
				    udp_ip->payload, ntohs(udp_ip->udp.length)-sizeof(struct udp_header));
		}
#endif /* ETH_UDP_BROADCAST */
		return;
	}

	if(rx_callback) {
		rx_callback(ntohl(udp_ip->ip.src_ip), ntohs(udp_ip->udp.src_port), ntohs(udp_ip->udp.dst_port),
				udp_ip->payload, ntohs(udp_ip->udp.length)-sizeof(struct udp_header));
#ifdef ETH_UDP_BROADCAST
	} else if(bx_callback) {
		bx_callback(ntohl(udp_ip->ip.src_ip), ntohs(udp_ip->udp.src_port), ntohs(udp_ip->udp.dst_port),
				udp_ip->payload, ntohs(udp_ip->udp.length)-sizeof(struct udp_header));
#endif /* ETH_UDP_BROADCAST */
	}
}

void udp_set_callback(udp_callback callback)
{
	rx_callback = callback;
}

#ifdef ETH_UDP_BROADCAST
void udp_set_broadcast_callback(udp_callback callback)
{
	bx_callback = callback;
}
#endif /* ETH_UDP_BROADCAST */

static void process_frame(void)
{
	flush_cpu_dcache();

#ifdef ETH_UDP_RX_DEBUG
	int j;
	printf("<<< rxlen : %d\n", rxlen);
	for(j=0;j<rxlen;j++)
		printf("%02x", rxbuffer->raw[j]);
	printf("\n");
#endif

#ifndef HW_PREAMBLE_CRC
	int i;
	for(i=0;i<7;i++)
		if(rxbuffer->frame.eth_header.preamble[i] != 0x55) return;
	if(rxbuffer->frame.eth_header.preamble[7] != 0xd5) return;
#endif

#ifndef HW_PREAMBLE_CRC
	uint32_t received_crc;
	uint32_t computed_crc;
	received_crc = ((uint32_t)rxbuffer->raw[rxlen-1] << 24)
		|((uint32_t)rxbuffer->raw[rxlen-2] << 16)
		|((uint32_t)rxbuffer->raw[rxlen-3] <<  8)
		|((uint32_t)rxbuffer->raw[rxlen-4]);
	computed_crc = crc32(&rxbuffer->raw[8], rxlen-12);
	if(received_crc != computed_crc) return;

	rxlen -= 4; /* strip CRC here to be consistent with TX */
#endif

	if (ntohs(rxbuffer->frame.eth_header.ethertype) == ETHERTYPE_ARP) {
		process_arp();
	} else if (ntohs(rxbuffer->frame.eth_header.ethertype) == ETHERTYPE_IP) {
		struct ip_header *hdr = &rxbuffer->frame.contents.udp.ip;
		if(hdr->version != IP_IPV4)
			return;
		if(ntohl(hdr->dst_ip) != my_ip)
			return;
		if (hdr->proto == IP_PROTO_UDP)
			process_udp();
		else if (hdr->proto == IP_PROTO_ICMP)
			process_icmp();
	}
}

void udp_start(const uint8_t *macaddr, uint32_t ip)
{
	int i;
	ethmac_sram_reader_ev_pending_write(ETHMAC_EV_SRAM_READER);
	ethmac_sram_writer_ev_pending_write(ETHMAC_EV_SRAM_WRITER);
	udp_set_ip(ip);
	udp_set_mac(macaddr);

	cached_ip = 0;
	for(i=0;i<6;i++)
		cached_mac[i] = 0;

	txslot = 0;
	ethmac_sram_reader_slot_write(txslot);
	txbuffer = (ethernet_buffer *)(ETHMAC_BASE + ETHMAC_SLOT_SIZE * (ETHMAC_RX_SLOTS + txslot));

	rxslot = 0;
	rxbuffer = (ethernet_buffer *)(ETHMAC_BASE + ETHMAC_SLOT_SIZE * rxslot);
	rx_callback = (udp_callback)0;
#ifdef ETH_UDP_BROADCAST
	bx_callback = (udp_callback)0;
#endif /* ETH_UDP_BROADCAST */
}

void udp_service(void)
{
	if(ethmac_sram_writer_ev_pending_read() & ETHMAC_EV_SRAM_WRITER) {
		rxslot = ethmac_sram_writer_slot_read();
		rxbuffer = (ethernet_buffer *)(ETHMAC_BASE + ETHMAC_SLOT_SIZE * rxslot);
		rxlen = ethmac_sram_writer_length_read();
		process_frame();
		ethmac_sram_writer_ev_pending_write(ETHMAC_EV_SRAM_WRITER);
	}
}

void eth_init(void)
{
	printf("Ethernet init...\n");
#ifdef CSR_ETHPHY_CRG_RESET_ADDR
#ifndef ETH_PHY_NO_RESET
	ethphy_crg_reset_write(1);
	busy_wait(200);
	ethphy_crg_reset_write(0);
	busy_wait(200);
#endif
#endif
}

#ifdef CSR_ETHPHY_MODE_DETECTION_MODE_ADDR
void eth_mode(void)
{
	printf("Ethernet phy mode: ");
	if (ethphy_mode_detection_mode_read())
		printf("MII");
	else
		printf("GMII");
	printf("\n");
}
#endif

#endif
