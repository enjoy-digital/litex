#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "error.h"

#include <event2/listener.h>
#include <event2/util.h>
#include <event2/event.h>
#include <json-c/json.h>
#include <zlib.h>
#include "tapcfg.h"
#include "modules.h"

// ---------- SETTINGS ---------- //

// Ethernet MTU. Must be >= MIN_ETH_LEN.
#define ETH_LEN 9000

// MAC address for the host's TAP interface
static const char macadr[6] = {0xaa, 0xb6, 0x24, 0x69, 0x77, 0x21};

// Debug (print to stderr) invalid bus states
#define GMII_TX_DEBUG_INVAL_SIGNAL

// Hex-dump transmitted (Sim -> TAP) packets to stderr
//#define GMII_TX_DEBUG

// Hex-dump received (TAP -> Sim) packets to stderr
//#define GMII_RX_DEBUG

// ------------------------------ //

#define MIN_ETH_LEN 60

// RX incoming (TAP -> Sim) Ethernet packet queue structs
typedef struct eth_packet_queue {
    // Does not contain the trailing CRC32 checksum
    uint8_t data[ETH_LEN];
    size_t len;
    struct eth_packet_queue *next;
} eth_packet_queue_t;

typedef struct gmii_state {
    // ---------- SIMULATION & BUS STATE ----------
    // GMII bus signals
    //
    // Receive (TAP -> SIM)
    uint8_t *rx_data_signal;
    bool *rx_dv_signal;
    bool *rx_er_signal;

    // Transmit (Sim -> TAP)
    uint8_t *tx_data_signal;
    uint8_t *tx_en_signal;
    uint8_t *tx_er_signal;

    // Collision detection and carrier sensing currently not implemented
    // bool *rx_col_signal;
    // bool *rx_cs_signal;

    // RX clock signal and edge state
    bool *rx_clk;
    clk_edge_state_t rx_clk_edge;

    // TX clock signal and edge state
    // current only gigabit clock supported
    bool *tx_clk;
    clk_edge_state_t tx_clk_edge;

    // ---------- GLOBAL STATE --------
    tapcfg_t *tapcfg;
    int tap_fd;

    // ---------- TX (Sim -> TAP) STATE ---------

    // Packet currently being transmitted over the GMII bus (Sim -> TAP).
    uint8_t current_tx_pkt[ETH_LEN];
    size_t current_tx_len;

    bool prev_tx_en;
    bool current_tx_abrt;
    bool current_tx_drop_warning;
    uint8_t current_tx_preamble_state;

    // ---------- RX (TAP -> Sim) STATE ---------

    // Packet currently being received over the GMII bus (TAP -> Sim). Packets
    // copied here are already removed from the TAP incoming queue. Fields are
    // valid if current_rx_len != 0. This field includes the CRC32 checksum.
    uint8_t current_rx_pkt[ETH_LEN + sizeof(uint32_t)];
    uint8_t current_rx_preamble_state;
    size_t current_rx_len;
    size_t current_rx_progress;

    // Linked list of pending RX (TAP -> Sim) packets. `tail` is only valid when
    // head != NULL.
    eth_packet_queue_t *pending_rx_pkt_head;
    eth_packet_queue_t *pending_rx_pkt_tail;
    struct event *ev;
} gmii_ethernet_state_t;

// Shared libevent state, set on module init
static struct event_base *base = NULL;

/**
 * Advance the RX (TAP -> Sim) state machine, producing a new bus snapshot
 *
 * This method must be called on the rising clock edge. It will produce a GMII
 * bus word which needs to be presented to the device.
 *
 * This function will detect pending RX packets in the queue and remove them
 * accordingly. Thus it is important that this function will be called on every
 * rising clock edge, regardless of whether a packet is currently being
 * transmitted.
 */
static void gmii_ethernet_rx_adv(gmii_ethernet_state_t *s,
                                 uint64_t time_ps) {
    // Check whether we are currently transmitting a packet over the GMII
    // interface (i.e. whether there are still bytes left in the packet input
    // buffer)
    if (s->current_rx_len) {
        // TODO:
        // assert s->current_rx_progress < s->current_rx_len

        // There are bytes to send, transfer the preamble, start of frame
        // character and data onto the bus.
        if (s->current_rx_preamble_state < 8) {
            // Transmit 56 bits (7 bytes) of 0x55(preamble), followed by 1 byte
            // 0xD5 (start of frame)
            switch (s->current_rx_preamble_state) {
            case 7:
                *s->rx_data_signal = 0xD5;
                break;
            default:
                *s->rx_data_signal = 0x55;
            }
            *s->rx_dv_signal = true;
            *s->rx_er_signal = false;
            s->current_rx_preamble_state++;
        } else if (s->current_rx_progress < s->current_rx_len) {
            *s->rx_data_signal = s->current_rx_pkt[s->current_rx_progress++];
            *s->rx_dv_signal = true; // Data on the bus is valid
            *s->rx_er_signal = false; // No receive error in this data word
        } else {
            // Finished transmitting, reset progress and length to zero.
            //
            // This cannot be combined with the branch above to ensure that we
            // have at least one cycle where rx_dv is deasserted.
            s->current_rx_preamble_state = 0;
            s->current_rx_progress = 0;
            s->current_rx_len = 0;

            *s->rx_data_signal = 0;
            *s->rx_dv_signal = 0;
            *s->rx_er_signal = 0;
        }
    } else {
        // No packet to transmit, indicate the bus is idle by deasserting `data
        // valid` (`rx_dv_signal`)
        *s->rx_data_signal = 0;
        *s->rx_dv_signal = false;
        *s->rx_er_signal = false;
    }

    if (!s->current_rx_len) {
        // No packet is currently in transit (or one has just completed
        // reception). Check if there is an outstanding packet from the TAP
        // interface and copy it into the input buffer
        if (s->pending_rx_pkt_head) {
            eth_packet_queue_t* popped_rx_pkt;

            // CRITICAL REGION {
            // Advance the pending packets queue, removing the copied
            // packet and freeing its allocated memory.
            popped_rx_pkt = s->pending_rx_pkt_head;
            s->pending_rx_pkt_head = s->pending_rx_pkt_head->next;
            // } CRITICAL REGION

            // Determine the maximum length to copy. We must not copy
            // beyond the length of s->current_rx_pkt and need to
            // reserve at least 4 bytes for the CRC32 to be appended.
            size_t copy_len =
                (popped_rx_pkt->len
                 <= sizeof(s->current_rx_pkt) - sizeof(uint32_t))
                  ? popped_rx_pkt->len
                  : sizeof(s->current_rx_pkt) - sizeof(uint32_t);

            // Copy the packet into the buffer
            memcpy(s->current_rx_pkt, popped_rx_pkt->data, copy_len);

            // Calculate the CRC32 checksum and append it to the
            // packet data. This uses the original packet's length. If
            // the original packet didn't fit into the buffer, the CRC
            // is going to be wrong and thus the packet being cut off
            // can be detected.
            uint32_t crc = crc32(0, popped_rx_pkt->data, popped_rx_pkt->len);
            s->current_rx_pkt[copy_len + 3] = (crc >> 24) & 0xFF;
            s->current_rx_pkt[copy_len + 2] = (crc >> 16) & 0xFF;
            s->current_rx_pkt[copy_len + 1] = (crc >>  8) & 0xFF;
            s->current_rx_pkt[copy_len + 0] = (crc >>  0) & 0xFF;

#ifdef GMII_RX_DEBUG
            fprintf(stderr, "\n----------------------------------\n"
                    "Received packet with %ld bytes\n", copy_len);
            for (size_t i = 0; i < copy_len; i++) {
                fprintf(stderr, "%02x", s->current_rx_pkt[i] & 0xff);
                if (i != 0 && (i + 1) % 16 == 0) {
                    fprintf(stderr, "\n");
                } else if (i != 0 && (i + 1) % 8 == 0) {
                    fprintf(stderr, "  ");
                }
            }
            fprintf(stderr, "\n----------------------------------\n");
#endif

            // Set the packet length (including CRC32) and thus
            // indicate that a packet is ready to be transmitted over
            // the GMII interface
            s->current_rx_len = copy_len + sizeof(uint32_t);

            // Release the packet data memory
            free(popped_rx_pkt);
        }
    }
}

/**
 * Advance the TX (Sim -> TAP) state machine based on a GMII bus word
 *
 * This method must be called on a rising clock edge (when the device has placed
 * a new GMII bus word).
 *
 * This function will detect frames sent by the device and place them on the TAP
 * network interface.
 */
static void gmii_ethernet_tx_adv(gmii_ethernet_state_t *s, uint64_t time_ps) {
    // Check whether the device is currently transmitting a new packet or
    // continuing an old transmission based on the previous tx_en_signal value
    if (s->prev_tx_en == false && *s->tx_en_signal == true) {
        // New transmission, reset the current packet length and transmission
        // abort state
        s->current_tx_len = 0;
        s->current_tx_preamble_state = 0;
        s->current_tx_abrt = false;
        s->current_tx_drop_warning = false;
    }

    if (s->current_tx_abrt) {
        // The current transmission has experienced an error. Wait for this
        // condition to be reset on the next new initiated transmission.
    } else if (*s->tx_en_signal == true && *s->tx_er_signal == true) {
        // Error condition on the bus, can't meaningfully handle. Abort
        // transmission.
        fprintf(stderr, "[gmii_ethernet]: TX error %02x %u %u\n",
                *s->tx_data_signal, *s->tx_en_signal, *s->tx_er_signal);
    } else if (*s->tx_en_signal == true
               && s->current_tx_len == ETH_LEN
               && !s->current_tx_drop_warning) {
        // Data on bus is valid and transmission has not previously experienced
        // an error condition, but no space left for the packet. Warn the user
        // once per such error in a single transmission.
        s->current_tx_drop_warning = true;
        fprintf(stderr, "[gmii_ethernet]: TX ETH_LEN reached, "
                "dropping frame data. Check the MTU.\n");
    } else if (*s->tx_en_signal == true && s->current_tx_len < ETH_LEN) {
        // Data valid, transmission has not previously experienced an error
        // condition and sufficient space left in the buffer. Expect preamble or
        // valid data.

        // Read in the preamble. If it doesn't match, report and error and abort
        // the current transmission.
        bool preamble_error = false;
        if (s->current_tx_preamble_state < 7) {
            // Expect 56 bits (7 bytes) of 0x55
            if (*s->tx_data_signal == 0x55) {
                s->current_tx_preamble_state++;
            } else {
                preamble_error = true;
            }
        } else if (s->current_tx_preamble_state < 8) {
            // Expect 8 bits (1 byte) of 0xD5
            if (*s->tx_data_signal == 0xD5) {
                s->current_tx_preamble_state++;
            } else {
                preamble_error = true;
            }
        } else {
            s->current_tx_pkt[s->current_tx_len++] = *s->tx_data_signal;
        }

        if (preamble_error) {
            fprintf(stderr, "[gmii_ethernet]: TX preamble error! %u %02x\n",
                    s->current_tx_preamble_state, *s->tx_data_signal);
            s->current_tx_abrt = true;
        }
    }

    if (s->prev_tx_en == true
        && *s->tx_en_signal == false
        && s->current_tx_len >= 1
        && !s->current_tx_abrt) {
        // Falling edge on tx_en, the frame has been transmitted into the
        // buffer. Transmit over the TAP interface.

        // Length without frame check sequence
        size_t pkt_len =
            (s->current_tx_len > 3) ? s->current_tx_len - 4 : 0;

#ifdef GMII_TX_DEBUG

        fprintf(stderr, "\n----------------------------------\n"
                "Transmitted packet with %ld bytes\n", pkt_len);
        for (size_t i = 0; i < pkt_len; i++) {
            fprintf(stderr, "%02x", s->current_tx_pkt[i] & 0xff);
            if (i != 0 && (i + 1) % 16 == 0) {
                fprintf(stderr, "\n");
            } else if (i != 0 && (i + 1) % 8 == 0) {
                fprintf(stderr, "  ");
            }
        }
        fprintf(stderr, "\n----------------------------------\n");
#endif

        if (s->current_tx_len < 4) {
            fprintf(stderr, "[gmii_ethernet]: TX packet too short to contain "
                    "frame check sequence\n");
        } else {
            uint32_t crc = crc32(0, s->current_tx_pkt, pkt_len);
            if (!((s->current_tx_pkt[pkt_len + 0] == ((crc >>  0) & 0xFF))
                  && (s->current_tx_pkt[pkt_len + 1] == ((crc >>  8) & 0xFF))
                  && (s->current_tx_pkt[pkt_len + 2] == ((crc >> 16) & 0xFF))
                  && (s->current_tx_pkt[pkt_len + 3] == ((crc >> 24) & 0xFF))))
            {
                fprintf(stderr, "[gmii_ethernet]: TX packet FCS mismatch. "
                        "Expected: %08x. Actual: %08x.\n", crc,
                        (uint32_t) s->current_tx_pkt[pkt_len + 0] << 0
                        | (uint32_t) s->current_tx_pkt[pkt_len + 1] << 8
                        | (uint32_t) s->current_tx_pkt[pkt_len + 2] << 16
                        | (uint32_t) s->current_tx_pkt[pkt_len + 3] << 24);
            }
        }

        tapcfg_write(s->tapcfg, s->current_tx_pkt, pkt_len);
    }

    // Store the previous tx_en_signal for edge detection
    s->prev_tx_en = *s->tx_en_signal;
}

static int gmii_ethernet_tick(void *state, uint64_t time_ps) {
    gmii_ethernet_state_t *s = (gmii_ethernet_state_t*) state;

    if (clk_pos_edge(&s->tx_clk_edge, *s->tx_clk)) {
        gmii_ethernet_tx_adv(s, time_ps);
    }

    if (clk_pos_edge(&s->rx_clk_edge, *s->rx_clk)) {
        gmii_ethernet_rx_adv(s, time_ps);
    }

    return RC_OK;
}

int litex_sim_module_get_args(char *args, char *arg, char **val) {
    int ret = RC_OK;
    json_object *jsobj = NULL;
    json_object *obj = NULL;
    char *value = NULL;
    int r;

    jsobj = json_tokener_parse(args);
    if (NULL == jsobj) {
        fprintf(stderr, "[gmii_ethernet]: error parsing json arg: %s\n", args);
        ret = RC_JSERROR;
        goto out;
    }

    if (!json_object_is_type(jsobj, json_type_object)) {
        fprintf(stderr, "[gmii_ethernet]: arg must be type object!: %s\n",
                args);
        ret = RC_JSERROR;
        goto out;
    }

    obj = NULL;
    r = json_object_object_get_ex(jsobj, arg, &obj);
    if (!r) {
        fprintf(stderr, "[gmii_ethernet]: could not find object: \"%s\" "
                "(%s)\n", arg, args);
        ret = RC_JSERROR;
        goto out;
    }
    value = strdup(json_object_get_string(obj));

 out:
    *val = value;
    return ret;
}

static int litex_sim_module_pads_get(struct pad_s *pads, char *name,
                                     void **signal) {
    int ret = RC_OK;
    void *sig = NULL;
    int i;

    if (!pads || !name || !signal) {
        ret=RC_INVARG;
        goto out;
    }

    i = 0;
    while (pads[i].name) {
        if (!strcmp(pads[i].name, name)) {
            sig=(void*)pads[i].signal;
            break;
        }
        i++;
    }

 out:
    *signal=sig;
    return ret;
}

void event_handler(int tap_fd, short event, void *arg) {
    gmii_ethernet_state_t *s = arg;

    // Expect a new TAP packet if the socket has become readable
    if (event & EV_READ) {
        eth_packet_queue_t *rx_pkt =
            malloc(sizeof(eth_packet_queue_t));

        // Read the TAP packet into the buffer, extending its length
        // to the minimum required Ethernet frame length if necessary.
        int read_len = tapcfg_read(s->tapcfg, rx_pkt->data, ETH_LEN);
        if (read_len < 0) {
            // An error occured while reading from the TAP interface,
            // report, free the packet and abort.
            fprintf(stderr, "[gmii_ethernet]: TAP read error %d\n", read_len);
            free(rx_pkt);
            return;
        } else if (read_len < MIN_ETH_LEN) {
            // To avoid leaking any data, set the packet's contents
            // after the proper received length to zero.
            memset(&rx_pkt->data[read_len], 0, MIN_ETH_LEN - read_len);
            rx_pkt->len = MIN_ETH_LEN;
        } else {
            // A packet larger than the minimum Ethernet frame length
            // has been read.
            rx_pkt->len = read_len;
        }

        // Packet is inserted into the back of the queue, thus no next
        // packet.
        rx_pkt->next = NULL;

        // CRITICAL REGION {
        // Append the received packet to the packet queue
        if (!s->pending_rx_pkt_head) {
            s->pending_rx_pkt_head = rx_pkt;
            s->pending_rx_pkt_tail = rx_pkt;
        } else {
            s->pending_rx_pkt_tail->next = rx_pkt;
            s->pending_rx_pkt_tail = rx_pkt;
        }
        // } CRITICAL REGION
    }
}

static int gmii_ethernet_add_pads(void *state, struct pad_list_s *plist) {
    int ret = RC_OK;
    gmii_ethernet_state_t *s = (gmii_ethernet_state_t*) state;
    struct pad_s *pads;
    if (!state || !plist) {
        ret = RC_INVARG;
        goto out;
    }
    pads = plist->pads;
    if (!strcmp(plist->name, "gmii_eth")) {
        litex_sim_module_pads_get(pads, "rx_data", (void**) &s->rx_data_signal);
        litex_sim_module_pads_get(pads, "rx_dv", (void**) &s->rx_dv_signal);
        litex_sim_module_pads_get(pads, "rx_er", (void**) &s->rx_er_signal);
        litex_sim_module_pads_get(pads, "tx_data", (void**) &s->tx_data_signal);
        litex_sim_module_pads_get(pads, "tx_en", (void**) &s->tx_en_signal);
        litex_sim_module_pads_get(pads, "tx_er", (void**) &s->tx_er_signal);
    }

    if (!strcmp(plist->name, "sys_clk")) {
        // TODO: currently the single sys_clk signal is used for both the RX and
        // TX GMII clock signals. This should be changed.
        litex_sim_module_pads_get(pads, "sys_clk", (void**)&s->rx_clk);
        s->tx_clk = s->rx_clk;
    }

out:
    return ret;
}

static int gmii_ethernet_start(void *b) {
  base = (struct event_base *) b;
  printf("[gmii_ethernet] loaded (%p)\n", base);
  return RC_OK;
}

static int gmii_ethernet_new(void **state, char *args) {
    int ret = RC_OK;
    char *c_tap = NULL;
    char *c_tap_ip = NULL;
    gmii_ethernet_state_t *s = NULL;
    struct timeval tv = {10, 0};

    if (!state) {
        ret = RC_INVARG;
        goto out;
    }

    s = (gmii_ethernet_state_t*)malloc(sizeof(gmii_ethernet_state_t));
    if (!s) {
        ret = RC_NOENMEM;
        goto out;
    }
    memset(s, 0, sizeof(gmii_ethernet_state_t));

    ret = litex_sim_module_get_args(args, "interface", &c_tap);
    if (ret != RC_OK) {
        goto out;
    }
    ret = litex_sim_module_get_args(args, "ip", &c_tap_ip);
    if (ret != RC_OK) {
        goto out;
    }

    s->tapcfg = tapcfg_init();
    tapcfg_start(s->tapcfg, c_tap, 0);
    s->tap_fd = tapcfg_get_fd(s->tapcfg);
    tapcfg_iface_set_hwaddr(s->tapcfg, macadr, 6);
    tapcfg_iface_set_ipv4(s->tapcfg, c_tap_ip, 24);
    tapcfg_iface_set_status(s->tapcfg, TAPCFG_STATUS_ALL_UP);
    free(c_tap);
    free(c_tap_ip);

    s->ev = event_new(base, s->tap_fd, EV_READ | EV_PERSIST, event_handler, s);
    event_add(s->ev, &tv);

out:
    *state = (void*) s;
    return ret;
}

static struct ext_module_s ext_mod = {
    "gmii_ethernet",
    gmii_ethernet_start,
    gmii_ethernet_new,
    gmii_ethernet_add_pads,
    NULL,
    gmii_ethernet_tick
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *)) {
    int ret = RC_OK;

    // Initiate calculation of zlib's CRC32 lookup table such that multithreaded
    // calls to crc32() are safe.
    get_crc_table();

    ret = register_module(&ext_mod);
    return ret;
}
