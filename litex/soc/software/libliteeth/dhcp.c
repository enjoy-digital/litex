// This file is Copyright (c) 2021 Mateusz Kosmala <mkosmala@internships.antmicro.com>
// This file is Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#include <generated/soc.h>

#ifdef ETH_WITH_DHCP

#include <stddef.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include <libliteeth/dhcp.h>
#include <libliteeth/inet.h>
#include <libliteeth/udp.h>

#ifndef ETH_UDP_BROADCAST
#error "ETH_WITH_DHCP requires ETH_UDP_BROADCAST"
#endif

#define DHCP_CLIENT_PORT		68
#define DHCP_SERVER_PORT		67

#define DHCP_OP_REQUEST			1
#define DHCP_OP_REPLY			2
#define DHCP_HTYPE_ETHERNET		1
#define DHCP_HLEN_ETHERNET		6
#define DHCP_FLAGS_BROADCAST		0x8000
#define DHCP_MAGIC_COOKIE		0x63825363
#define DHCP_MIN_PACKET_SIZE		300
#define DHCP_TX_OPTIONS_SIZE		64
#define DHCP_TIMEOUT			2000000
#define DHCP_TRIES			5

#define DHCP_OPTION_SUBNET_MASK		1
#define DHCP_OPTION_ROUTER		3
#define DHCP_OPTION_REQUESTED_IP		50
#define DHCP_OPTION_MESSAGE_TYPE		53
#define DHCP_OPTION_SERVER_ID		54
#define DHCP_OPTION_PARAMETER_LIST	55
#define DHCP_OPTION_END			255

#define DHCPDISCOVER			1
#define DHCPOFFER			2
#define DHCPREQUEST			3
#define DHCPDECLINE			4
#define DHCPACK				5
#define DHCPNAK				6

struct dhcp_packet {
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
	uint8_t chaddr[16];
	uint8_t sname[64];
	uint8_t file[128];
	uint32_t cookie;
	uint8_t options[];
} __attribute__((packed));

static const uint8_t *client_mac;
static uint32_t transaction_id;
static uint32_t offered_ip;
static uint32_t assigned_ip;
static uint32_t server_id;
static uint8_t wait_message_type;
static int transfer_finished;
static int transfer_failed;

static uint32_t dhcp_transaction_id(const uint8_t *macaddr)
{
	uint32_t xid = 0x4c580000; /* LX */

	for(int i=0;i<DHCP_HLEN_ETHERNET;i++)
		xid = (xid << 5) ^ macaddr[i];

	return xid;
}

static int dhcp_add_option(uint8_t *options, int offset, uint8_t code, const void *data, uint8_t length)
{
	if((offset + 2 + length) > DHCP_TX_OPTIONS_SIZE)
		return -1;
	options[offset++] = code;
	options[offset++] = length;
	memcpy(&options[offset], data, length);
	return offset + length;
}

static int dhcp_add_u8_option(uint8_t *options, int offset, uint8_t code, uint8_t value)
{
	return dhcp_add_option(options, offset, code, &value, sizeof(value));
}

static int dhcp_end_options(uint8_t *options, int offset)
{
	if(offset >= DHCP_TX_OPTIONS_SIZE)
		return -1;
	options[offset++] = DHCP_OPTION_END;
	return offset;
}

static int dhcp_get_message_type(const uint8_t *options, int length)
{
	int offset = 0;

	while(offset < length) {
		uint8_t code = options[offset++];
		uint8_t option_length;

		if(code == 0)
			continue;
		if(code == DHCP_OPTION_END)
			break;
		if(offset >= length)
			break;

		option_length = options[offset++];
		if((offset + option_length) > length)
			break;

		if((code == DHCP_OPTION_MESSAGE_TYPE) && (option_length == 1))
			return options[offset];

		offset += option_length;
	}

	return 0;
}

static uint32_t dhcp_get_u32_option(const uint8_t *options, int length, uint8_t requested_code)
{
	int offset = 0;

	while(offset < length) {
		uint8_t code = options[offset++];
		uint8_t option_length;

		if(code == 0)
			continue;
		if(code == DHCP_OPTION_END)
			break;
		if(offset >= length)
			break;

		option_length = options[offset++];
		if((offset + option_length) > length)
			break;

		if((code == requested_code) && (option_length == 4)) {
			uint32_t value;
			memcpy(&value, &options[offset], sizeof(value));
			return ntohl(value);
		}

		offset += option_length;
	}

	return 0;
}

static int dhcp_mac_matches(const uint8_t *macaddr)
{
	for(int i=0;i<DHCP_HLEN_ETHERNET;i++)
		if(macaddr[i] != client_mac[i])
			return 0;

	return 1;
}

static int dhcp_format_message(uint8_t *buffer, uint8_t message_type)
{
	struct dhcp_packet *packet = (struct dhcp_packet *)buffer;
	uint8_t parameter_list[] = {
		DHCP_OPTION_SUBNET_MASK,
		DHCP_OPTION_ROUTER,
	};
	uint32_t requested_ip;
	int offset = 0;
	int length;

	memset(packet, 0, DHCP_MIN_PACKET_SIZE);

	packet->op     = DHCP_OP_REQUEST;
	packet->htype  = DHCP_HTYPE_ETHERNET;
	packet->hlen   = DHCP_HLEN_ETHERNET;
	packet->xid    = htonl(transaction_id);
	packet->flags  = htons(DHCP_FLAGS_BROADCAST);
	packet->cookie = htonl(DHCP_MAGIC_COOKIE);
	memcpy(packet->chaddr, client_mac, DHCP_HLEN_ETHERNET);

	offset = dhcp_add_u8_option(packet->options, offset, DHCP_OPTION_MESSAGE_TYPE, message_type);
	if(offset < 0)
		return -1;

	if(message_type == DHCPREQUEST) {
		requested_ip = htonl(offered_ip);
		offset = dhcp_add_option(packet->options, offset, DHCP_OPTION_REQUESTED_IP,
			&requested_ip, sizeof(requested_ip));
		if(offset < 0)
			return -1;
		if(server_id != 0) {
			uint32_t requested_server = htonl(server_id);
			offset = dhcp_add_option(packet->options, offset, DHCP_OPTION_SERVER_ID,
				&requested_server, sizeof(requested_server));
			if(offset < 0)
				return -1;
		}
	}

	offset = dhcp_add_option(packet->options, offset, DHCP_OPTION_PARAMETER_LIST,
		parameter_list, sizeof(parameter_list));
	if(offset < 0)
		return -1;

	offset = dhcp_end_options(packet->options, offset);
	if(offset < 0)
		return -1;

	length = offsetof(struct dhcp_packet, options) + offset;
	if(length < DHCP_MIN_PACKET_SIZE)
		length = DHCP_MIN_PACKET_SIZE;

	return length;
}

static int dhcp_send_message(uint8_t message_type)
{
	uint8_t *packet_data = udp_get_tx_buffer();
	int length;

	length = dhcp_format_message(packet_data, message_type);
	if(length < 0)
		return 0;

	udp_set_broadcast();
	return udp_send(DHCP_CLIENT_PORT, DHCP_SERVER_PORT, length);
}

static void dhcp_rx_callback(uint32_t src_ip, uint16_t src_port, uint16_t dst_port,
	void *_data, uint32_t length)
{
	const struct dhcp_packet *packet = _data;
	const uint8_t *options;
	int options_length;
	int message_type;

	if((src_port != DHCP_SERVER_PORT) || (dst_port != DHCP_CLIENT_PORT))
		return;
	if(length < offsetof(struct dhcp_packet, options))
		return;
	if(packet->op != DHCP_OP_REPLY)
		return;
	if(packet->htype != DHCP_HTYPE_ETHERNET)
		return;
	if(packet->hlen != DHCP_HLEN_ETHERNET)
		return;
	if(ntohl(packet->xid) != transaction_id)
		return;
	if(ntohl(packet->cookie) != DHCP_MAGIC_COOKIE)
		return;
	if(!dhcp_mac_matches(packet->chaddr))
		return;

	options = packet->options;
	options_length = length - offsetof(struct dhcp_packet, options);
	message_type = dhcp_get_message_type(options, options_length);

	if(message_type == DHCPNAK) {
		transfer_failed = 1;
		transfer_finished = 1;
		return;
	}

	if(message_type != wait_message_type)
		return;

	if(message_type == DHCPOFFER) {
		offered_ip = ntohl(packet->yiaddr);
		server_id = dhcp_get_u32_option(options, options_length, DHCP_OPTION_SERVER_ID);
		if(server_id == 0)
			server_id = src_ip;
	} else if(message_type == DHCPACK) {
		assigned_ip = ntohl(packet->yiaddr);
		if(assigned_ip == 0)
			assigned_ip = offered_ip;
	}

	transfer_finished = 1;
}

static int dhcp_send_and_wait(uint8_t message_type, uint8_t expected_type)
{
	wait_message_type = expected_type;
	transfer_failed = 0;

	for(int tries=0;tries<DHCP_TRIES;tries++) {
		transfer_finished = 0;
		if(!dhcp_send_message(message_type))
			return 0;

		for(int timeout=0;timeout<DHCP_TIMEOUT;timeout++) {
			udp_service();
			if(transfer_finished)
				return !transfer_failed;
		}
	}

	return 0;
}

int dhcp_resolve(const uint8_t *macaddr, uint32_t *ip_address)
{
	client_mac = macaddr;
	transaction_id = dhcp_transaction_id(macaddr);
	offered_ip = 0;
	assigned_ip = 0;
	server_id = 0;

	udp_start(macaddr, IPTOINT(0, 0, 0, 0));
	udp_set_callback(dhcp_rx_callback);
	udp_set_broadcast_callback(dhcp_rx_callback);

	if(!dhcp_send_and_wait(DHCPDISCOVER, DHCPOFFER)) {
		printf("DHCP: no offer\n");
		goto failed;
	}

	if(!dhcp_send_and_wait(DHCPREQUEST, DHCPACK)) {
		printf("DHCP: no acknowledgement\n");
		goto failed;
	}

	udp_set_callback(NULL);
	udp_set_broadcast_callback(NULL);
	*ip_address = assigned_ip;
	return 0;

failed:
	udp_set_callback(NULL);
	udp_set_broadcast_callback(NULL);
	return -1;
}

#endif /* ETH_WITH_DHCP */
