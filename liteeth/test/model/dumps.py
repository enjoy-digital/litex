import re

def format_dump(dump):
	return [int(s, 16) for s in re.split(r'[;,\s\n]\s*', dump) if s is not ""]

def verify_packet(packet, infos):
	errors = 0
	for k, v in infos.items():
		if hasattr(packet, k):
			if getattr(packet, k) != v:
				print("[Error] " + k)
				errors += 1
	return errors

arp_request = format_dump("""
00 22 19 22 54 9e 00 12 3f 97 92 01 08 06 00 01
08 00 06 04 00 01 00 12 3f 97 92 01 a9 fe ff 42
00 22 19 22 54 9e a9 fe 64 62""")

arp_request_infos = {
	"source_mac_address"		:	0x00123f979201,
	"destination_mac_address"	:	0x00221922549e,
	"ethernet_type"				: 	0x806,
	"hardware_type"				: 	0x1,
	"operation"					:	0x1,
	"protocol_address_length"	:	0x4,
	"protocol_type"				:	0x800,
	"source_ip_address"			:	0xa9feff42,
	"destination_ip_address"	:	0xa9fe6462

}

arp_reply = format_dump("""
00 12 3f 97 92 01 00 22 19 22 54 9e 08 06 00 01
08 00 06 04 00 02 00 22 19 22 54 9e a9 fe 64 62
00 12 3f 97 92 01 a9 fe ff 42 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00""")

arp_reply_infos = {
	"source_mac_address"		:	0x00221922549e,
	"destination_mac_address"	:	0x00123f979201,
	"ethernet_type"				: 	0x806,
	"hardware_type"				: 	0x1,
	"operation"					:	0x2,
	"protocol_address_length"	:	0x4,
	"protocol_type"				:	0x800,
	"source_ip_address"			:	0xa9fe6462,
	"destination_ip_address"	:	0xa9feff42
}

udp = format_dump("""
d0 7a b5 96 cd 0a 00 14 0b 33 33 27 08 00 45 00
00 5f 31 16 00 00 80 11 87 77 c0 a8 01 65 b2 7b
0d 78 a6 3f 69 0f 00 4b 6a 54 64 31 3a 61 64 32
3a 69 64 32 30 3a 5a fa 29 99 3a 5e ce 19 d1 8b
aa 9b 4e 4d f9 2e 51 52 fe ff 65 31 3a 71 34 3a
70 69 6e 67 31 3a 74 34 3a 85 72 00 00 31 3a 76
34 3a 55 54 7e 62 31 3a 79 31 3a 71 65""")

udp_infos = {
	"source_mac_address"		:	0x00140b333327,
	"destination_mac_address"	:	0xd07ab596cd0a,
	"protocol"					:	0x11,
	"source_ip_address"			:	0xc0a80165,
	"destination_ip_address"	:	0xb27b0d78,
	"source_port"				:	0xa63f,
	"destination_port"			:	0x690f
}
