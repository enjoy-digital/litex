#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import textwrap


def _write(path, contents=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(contents))


def test_liteeth_tftp_receive_bounds_host_coverage(tmp_path):
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    include_dir = tmp_path / "include"
    source = tmp_path / "tftp_harness.c"
    binary = tmp_path / "tftp_harness"

    _write(include_dir / "generated" / "soc.h")
    _write(include_dir / "libbase" / "progress.h", """
        #ifndef __PROGRESS_H
        #define __PROGRESS_H
        static inline void init_progression_bar(unsigned int total) {(void)total;}
        static inline void show_progress(int current) {(void)current;}
        #endif
    """)
    _write(source, f"""
        #include <stdint.h>
        #include <stdio.h>
        #include <string.h>

        #include "{repo}/litex/soc/software/libliteeth/udp.h"

        static uint8_t tx_buffer[2048];
        static uint16_t last_src_port;
        static uint16_t last_dst_port;
        static uint32_t last_send_length;
        static int send_count;
        static udp_callback current_callback;

        void udp_set_ip(uint32_t ip);
        uint32_t udp_get_ip(void);
        void udp_set_mac(const uint8_t *macaddr);
        void udp_start(const uint8_t *macaddr, uint32_t ip);
        int udp_arp_resolve(uint32_t ip);
        void *udp_get_tx_buffer(void);
        int udp_send(uint16_t src_port, uint16_t dst_port, uint32_t length);
        void udp_set_callback(udp_callback callback);
        void udp_service(void);

        void udp_set_ip(uint32_t ip) {{ (void)ip; }}
        uint32_t udp_get_ip(void) {{ return 0; }}
        void udp_set_mac(const uint8_t *macaddr) {{ (void)macaddr; }}
        void udp_start(const uint8_t *macaddr, uint32_t ip) {{ (void)macaddr; (void)ip; }}
        int udp_arp_resolve(uint32_t ip) {{ (void)ip; return 1; }}
        void *udp_get_tx_buffer(void) {{ return tx_buffer; }}
        int udp_send(uint16_t src_port, uint16_t dst_port, uint32_t length)
        {{
            last_src_port = src_port;
            last_dst_port = dst_port;
            last_send_length = length;
            send_count++;
            return 0;
        }}
        void udp_set_callback(udp_callback callback) {{ current_callback = callback; }}
        void udp_service(void) {{}}

        #include "{repo}/litex/soc/software/libliteeth/tftp.c"

        #define REQUIRE(cond) do {{ \\
            if (!(cond)) {{ \\
                fprintf(stderr, "requirement failed at %s:%d: %s\\n", __FILE__, __LINE__, #cond); \\
                return 1; \\
            }} \\
        }} while (0)

        static void reset_rx(uint8_t *dst, size_t dst_size)
        {{
            memset(tx_buffer, 0, sizeof(tx_buffer));
            last_src_port = 0;
            last_dst_port = 0;
            last_send_length = 0;
            send_count = 0;
            packet_data = NULL;
            total_length = 0;
            transfer_finished = 0;
            dst_buffer = dst;
            dst_buffer_size = dst_size;
            last_ack = -1;
            data_port = 0;
        }}

        static void make_data_packet(uint8_t *packet, uint16_t block,
            const uint8_t *payload, unsigned int payload_length)
        {{
            packet[0] = 0x00;
            packet[1] = TFTP_DATA;
            packet[2] = (block >> 8) & 0xff;
            packet[3] = block & 0xff;
            memcpy(&packet[4], payload, payload_length);
        }}

        static int test_short_and_wrong_port_packets_are_ignored(void)
        {{
            uint8_t dst[8] = {{0}};
            uint8_t packet[8] = {{0, TFTP_DATA, 0, 1, 1, 2, 3, 4}};

            reset_rx(dst, sizeof(dst));
            rx_callback(0, 1000, PORT_IN, packet, 3);
            REQUIRE(total_length == 0);
            REQUIRE(transfer_finished == 0);
            REQUIRE(send_count == 0);

            rx_callback(0, 1000, PORT_IN + 1, packet, sizeof(packet));
            REQUIRE(total_length == 0);
            REQUIRE(transfer_finished == 0);
            REQUIRE(send_count == 0);
            return 0;
        }}

        static int test_oack_and_ack_update_transfer_state(void)
        {{
            uint8_t dst[8] = {{0}};
            uint8_t oack[4] = {{0, TFTP_OACK, 0, 0}};
            uint8_t ack[4] = {{0, TFTP_ACK, 0x12, 0x34}};

            reset_rx(dst, sizeof(dst));
            rx_callback(0, 1069, PORT_IN, oack, sizeof(oack));
            REQUIRE(send_count == 1);
            REQUIRE(last_src_port == PORT_IN);
            REQUIRE(last_dst_port == 1069);
            REQUIRE(last_send_length == 4);
            REQUIRE(tx_buffer[0] == 0);
            REQUIRE(tx_buffer[1] == TFTP_ACK);
            REQUIRE(tx_buffer[2] == 0);
            REQUIRE(tx_buffer[3] == 0);
            REQUIRE(last_ack == 0);
            REQUIRE(data_port == 1069);

            rx_callback(0, 1070, PORT_IN, ack, sizeof(ack));
            REQUIRE(last_ack == 0x1234);
            REQUIRE(data_port == 1070);
            return 0;
        }}

        static int test_data_packet_copies_and_acknowledges(void)
        {{
            uint8_t dst[8] = {{0}};
            uint8_t packet[8];
            uint8_t payload[4] = {{1, 2, 3, 4}};

            reset_rx(dst, sizeof(dst));
            make_data_packet(packet, 1, payload, sizeof(payload));
            rx_callback(0, 1069, PORT_IN, packet, sizeof(packet));
            REQUIRE(total_length == 4);
            REQUIRE(transfer_finished == 1);
            REQUIRE(memcmp(dst, payload, sizeof(payload)) == 0);
            REQUIRE(send_count == 1);
            REQUIRE(last_dst_port == 1069);
            REQUIRE(tx_buffer[1] == TFTP_ACK);
            REQUIRE(tx_buffer[2] == 0);
            REQUIRE(tx_buffer[3] == 1);
            return 0;
        }}

        static int test_invalid_data_blocks_do_not_write_or_ack(void)
        {{
            uint8_t dst[8];
            uint8_t packet[12];
            uint8_t payload[8] = {{0, 1, 2, 3, 4, 5, 6, 7}};

            memset(dst, 0xaa, sizeof(dst));
            reset_rx(dst, sizeof(dst));
            make_data_packet(packet, 0, payload, 4);
            rx_callback(0, 1069, PORT_IN, packet, 8);
            REQUIRE(total_length == 0);
            REQUIRE(transfer_finished == 0);
            REQUIRE(send_count == 0);
            REQUIRE(dst[0] == 0xaa);

            reset_rx(dst, 4);
            make_data_packet(packet, 1, payload, sizeof(payload));
            rx_callback(0, 1069, PORT_IN, packet, 12);
            REQUIRE(total_length == -1);
            REQUIRE(transfer_finished == 1);
            REQUIRE(send_count == 0);
            return 0;
        }}

        static int test_error_packet_finishes_with_failure(void)
        {{
            uint8_t dst[8] = {{0}};
            uint8_t error[4] = {{0, TFTP_ERROR, 0, 1}};

            reset_rx(dst, sizeof(dst));
            rx_callback(0, 1069, PORT_IN, error, sizeof(error));
            REQUIRE(total_length == -1);
            REQUIRE(transfer_finished == 1);
            REQUIRE(send_count == 0);
            return 0;
        }}

        int main(void)
        {{
            udp_set_callback((udp_callback)rx_callback);
            REQUIRE(current_callback == (udp_callback)rx_callback);
            if (test_short_and_wrong_port_packets_are_ignored())
                return 1;
            if (test_oack_and_ack_update_transfer_state())
                return 1;
            if (test_data_packet_copies_and_acknowledges())
                return 1;
            if (test_invalid_data_blocks_do_not_write_or_ack())
                return 1;
            if (test_error_packet_finishes_with_failure())
                return 1;
            return 0;
        }}
    """)

    cmd = [
        "gcc",
        "-std=gnu99",
        "-Wall",
        "-Wextra",
        "-Wstrict-prototypes",
        "-Wold-style-definition",
        "-Wmissing-prototypes",
        f"-I{include_dir}",
        f"-I{repo}/litex/soc/software",
        str(source),
        "-o",
        str(binary),
    ]
    subprocess.check_call(cmd)
    subprocess.check_call([str(binary)])
