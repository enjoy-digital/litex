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
    "sender_mac":    0x00123f979201,
    "target_mac":    0x00221922549e,
    "ethernet_type": 0x806,
    "hwtype":        0x1,
    "opcode":        0x1,
    "protosize":     0x4,
    "proto":         0x800,
    "sender_ip":     0xa9feff42,
    "target_ip":     0xa9fe6462

}

arp_reply = format_dump("""
00 12 3f 97 92 01 00 22 19 22 54 9e 08 06 00 01
08 00 06 04 00 02 00 22 19 22 54 9e a9 fe 64 62
00 12 3f 97 92 01 a9 fe ff 42 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00""")

arp_reply_infos = {
    "sender_mac":    0x00221922549e,
    "target_mac":    0x00123f979201,
    "ethernet_type": 0x806,
    "hwtype":        0x1,
    "opcode":        0x2,
    "protosize":     0x4,
    "proto":         0x800,
    "sender_ip":     0xa9fe6462,
    "target_ip":     0xa9feff42
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
    "sender_mac": 0x00140b333327,
    "target_mac": 0xd07ab596cd0a,
    "protocol":   0x11,
    "sender_ip":  0xc0a80165,
    "target_ip":  0xb27b0d78,
    "src_port":   0xa63f,
    "dst_port":   0x690f
}

ping_request = format_dump("""
00 50 56 e0 14 49 00 0c 29 34 0b de 08 00 45 00
00 3c d7 43 00 00 80 01 2b 73 c0 a8 9e 8b ae 89
2a 4d 08 00 2a 5c 02 00 21 00 61 62 63 64 65 66
67 68 69 6a 6b 6c 6d 6e 6f 70 71 72 73 74 75 76
77 61 62 63 64 65 66 67 68 69""")

ping_request_infos = {
    "code":    0x0,
    "msgtype": 0x8,
    "quench":  0x2002100
}

ping_reply = format_dump("""
00 0c 29 34 0b de 00 50 56 e0 14 49 08 00 45 00
00 3c 76 e1 00 00 80 01 8b d5 ae 89 2a 4d c0 a8
9e 8b 00 00 32 5c 02 00 21 00 61 62 63 64 65 66
67 68 69 6a 6b 6c 6d 6e 6f 70 71 72 73 74 75 76
77 61 62 63 64 65 66 67 68 69""")

ping_reply_infos = {}
