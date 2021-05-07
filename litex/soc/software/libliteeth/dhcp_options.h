#ifndef __DHCP_OPTIONS_H
#define __DHCP_OPTIONS_H

/* Available DHCP package types */

#define DHCP_TDISCOVER        1
#define DHCP_TOFFER           2
#define DHCP_TREQUEST         3
#define DHCP_TPACK     	      4

/* Available DHCP package options */

#define DHCP_OPAD             0
#define DHCP_OREQUEST_IP      50
#define DHCP_OMESSAGE_TYPE    53
#define DHCP_OEND             255

/* DHCP client general options */

#define DHCP_PORT_CLIENT      68
#define DHCP_PORT_SERVER      67
#define DHCP_HARDWARE_LEN     6
#define DHCP_OPTIONS_LEN      128
#define DHCP_COOKIE           0x63825363
#define DHCP_XID              0x21274A1D
#define DHCP_ADDR_LEN         16

#endif /* __DHCP_OPTIONS_H */
