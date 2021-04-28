#include <bios/boot.h>
#include <inet.h>

#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include "dhcp_client.h"
#include "dhcp_options.h"
#include "udp.h"

//#define DHCP_UDP_DEBUG

/*Format of a DHCP message based on RFC2131(Page 8) */
struct dhcp
{
        uint8_t  op;                                // Op code
        uint8_t  htype;                             // Hardware address type
        uint8_t  hlen;                              // Hardware address length
        uint8_t  hops;                              // Relay agent
        uint32_t xid;                               // Transaction ID
        uint16_t secs;                              // Second elapsed
        uint16_t flags;                             // Flags
        uint32_t ciaddr;                            // Client IP adress(32 bits)
        uint32_t yiaddr;                            // Client IP addres(32 bits)
        uint32_t siaddr;                            // IP address of next server(32 bits)
        uint32_t giaddr;                            // Relay agent IP address(32 bits)
        unsigned char chaddr[16];                   // Client hardware address
        unsigned char sname[64];                    // Optional server host name
        unsigned char file[128];                    // Boot file name
        uint32_t mcookie;                           // Magic cookie
        unsigned char options[DHCP_OPTIONS_LEN];    // Optional parameters
} __attribute__((packed));

static uint8_t *packet_data;
static struct dhcp dhcp_p;
static int transfer_finished;
static uint32_t offered_ip_address;

static void rx_callback(uint32_t server_ip, uint16_t server_port, uint16_t dst_port, void *_data, unsigned int length)
{
        struct dhcp *data = _data;
        if(dst_port != DHCP_PORT_CLIENT) return;

        if(data->op == DHCP_TOFFER)
        {
                offered_ip_address = (data->yiaddr);
                transfer_finished = 1;
        }
}

static int fill_options(uint8_t *chunk, uint8_t code_option, void *data_option, uint8_t len_option)
{
        if(code_option == DHCP_OEND)
        {
                chunk[0] = DHCP_OEND;
                return len_option;
        }
        chunk[0] = code_option;
        chunk[1] = len_option;
        memcpy(&chunk[2], data_option, len_option);
        return len_option + (sizeof(uint8_t) << 1);
}

static void format_base(uint8_t *buff, struct dhcp *p, unsigned char * mc_addr)
{
        memset(p, 0, sizeof(struct dhcp));
        p->op = 0x01;
        p->htype = 0x01;
        p->hlen = 0x06;
        p->hops = 0x00;
        p->xid = htonl(DHCP_XID);
        p->secs = 0x0;
        p->flags = 0x0;
        p->ciaddr = IPTOINT(0, 0, 0, 0);
        p->yiaddr = IPTOINT(0, 0, 0, 0);
        p->siaddr = IPTOINT(0, 0, 0, 0);
        p->giaddr = IPTOINT(0, 0, 0, 0);
        memcpy(p->chaddr, mc_addr, DHCP_ADDR_LEN);
        memset(p->sname, 0, 64);
        memset(p->file, 0, 128);
        p->mcookie = htonl(DHCP_COOKIE);
}

static int format_request(uint8_t *buff, struct dhcp *p, unsigned char* mc_addr)
{
        format_base(buff, p, mc_addr);
        uint8_t option_tag = DHCP_TREQUEST;
        int len = fill_options(&p->options[0], DHCP_OMESSAGE_TYPE, &option_tag, sizeof(option_tag));
        len += fill_options(&p->options[len], DHCP_OREQUEST_IP , &offered_ip_address, sizeof(offered_ip_address));
        len += fill_options(&p->options[len], DHCP_OEND, &option_tag, sizeof(option_tag));
        memcpy(buff, p, sizeof(struct dhcp));
        return sizeof(struct dhcp);
}

static int format_discovery(uint8_t *buff, struct dhcp *p, unsigned char* mc_addr)
{
        format_base(buff, p, mc_addr);
        uint8_t option_tag = DHCP_TDISCOVER;
        int len = fill_options(&p->options[0], DHCP_OMESSAGE_TYPE, &option_tag, sizeof(option_tag));
        option_tag = DHCP_OEND;
        len += fill_options(&p->options[len], DHCP_OEND, &option_tag, sizeof(option_tag));
        memcpy(buff, p, sizeof(struct dhcp));
        return sizeof(struct dhcp);
}

static int dhcp_dispatcher(uint8_t *buff, struct dhcp *p, unsigned char* mc_addr, uint16_t option)
{
        int message_len;
        if(option == DHCP_TDISCOVER)
                message_len = format_discovery(buff, p, mc_addr);
        else if(option == DHCP_TREQUEST)
                message_len = format_request(buff, p, mc_addr);
        return message_len;
}

static int send_message(unsigned char * mc_addr, uint16_t type)
{
        for(int tries=5; tries > 0; --tries)
        {
                packet_data = udp_get_tx_buffer();
                int len = dhcp_dispatcher(packet_data, &dhcp_p, mc_addr, type);
                udp_send(DHCP_PORT_CLIENT, DHCP_PORT_SERVER, len);

#ifdef DHCP_UDP_DEBUG
                printf(">>>> UDP_Payload : %d\n", len);
                for(int i=0; i<len; i++)
                {
                        if(i % 16 == 0)
                                printf("\n %x :: ", i);
                        printf(" %02x ", packet_data[i]);
                }
                printf("\n");
#endif

                for(int i=0; i<2000000; ++i)
                {
                        udp_service();
                        if(transfer_finished)
                        {
                                transfer_finished = 0;
                                return 1;
                        }
                }
        }
        return 0;
}

void dhcp_resolve(unsigned char * mc_addr)
{
        udp_start(mc_addr, IPTOINT(0, 0, 0, 0));
        udp_arp_resolve(IPTOINT(255, 255, 255, 255));
        udp_set_callback(rx_callback);

        if(!send_message(mc_addr, DHCP_TDISCOVER))
        {
                printf("DHCP Server not found, Abort.");
                udp_set_callback(NULL);
                return;
        }
        if(!send_message(mc_addr, DHCP_TREQUEST))
        {
                printf("No Acknowledgement from DHCP server, Abort.");
                udp_set_callback(NULL);
                return;
        }
        char ip_resolved[15];
        unsigned char *octets = (unsigned char *)&offered_ip_address;
        snprintf(ip_resolved, sizeof(ip_resolved), "%d.%d.%d.%d", octets[0], octets[1], octets[2], octets[3]);
        set_local_ip(ip_resolved);
}
