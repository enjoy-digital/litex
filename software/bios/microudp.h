/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009, 2010, 2011 Sebastien Bourdeauducq
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef __NET_MICROUDP_H
#define __NET_MICROUDP_H

#define IPTOINT(a, b, c, d) ((a << 24)|(b << 16)|(c << 8)|d)

#define MICROUDP_BUFSIZE (5*1532)

typedef void (*udp_callback)(unsigned int src_ip, unsigned short src_port, unsigned short dst_port, void *data, unsigned int length);

void microudp_start(unsigned char *macaddr, unsigned int ip);
int microudp_arp_resolve(unsigned int ip);
void *microudp_get_tx_buffer(void);
int microudp_send(unsigned short src_port, unsigned short dst_port, unsigned int length);
void microudp_set_callback(udp_callback callback);
void microudp_service(void);

#endif /* __NET_MICROUDP_H */
