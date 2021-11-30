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

// XGMII bus data width. Can be either 32 or 64 bit.
#define XGMII_WIDTH 64

// Ethernet MTU. Must be >= MIN_ETH_LEN.
#define ETH_LEN 9000

// MAC address for the host's TAP interface
static const char macadr[6] = {0xaa, 0xb6, 0x24, 0x69, 0x77, 0x21};

// Enable the deficit idle count mechanism for RX (TAP -> SIM)
#define XGMII_RX_DIC_ENABLE

// Debug (print to stderr) invalid bus states
#define XGMII_TX_DEBUG_INVAL_SIGNAL

// Hex-dump transmitted (Sim -> TAP) packets to stderr
//#define XGMII_TX_DEBUG

// Hex-dump received (TAP -> Sim) packets to stderr
//#define XGMII_RX_DEBUG

// ------------------------------ //

#define MIN_ETH_LEN 60

#define XGMII_IDLE_DATA 0x07070707
#define XGMII_IDLE_CTL  0xF

// Contains the start XGMII control character (fb), the XGMII preamble (48-bit
// alternating 0 and 1) and the Ethernet start of frame delimiter. Is a 64-bit
// bus word, thus to transmit it over a 32-bit bus one must first transmit the
// lower and subsequently the upper half.
#define XGMII_FB_PREAMBLE_SF_DATA 0xD5555555555555FB
#define XGMII_FB_PREAMBLE_SF_CTL  0x01

#define XGMII_CTLCHAR_START 0xFB
#define XGMII_CTLCHAR_END   0xFD
#define XGMII_CTLCHAR_IDLE  0x07

// Shortcut macro for incrementing the inter-frame gap count, bounded by
// 15. While Ethernet mandates a 12-byte IFG, the DIC mechanism requires us to
// keep track of inserted IFG characters. Thus limit the IFG count to 15 bytes
// (to prevent eventual overflow).
#define XGMII_RX_IFG_INC(s) \
    if (s->rx_ifg_count < 15) s->rx_ifg_count++;

// Type definitions for the 32-bit XGMII bus contents, irrespective of the XGMII
// bus width used. The data here is then latched out over a bus with the
// xgmii_*_signal_t types (either 32-bit or 64-bit, which is two 32-bit words
// combined).
typedef uint32_t xgmii_data_t;
typedef uint8_t xgmii_ctl_t;
typedef struct xgmii_bus_snapshot {
    xgmii_data_t data;
    xgmii_ctl_t ctl;
} xgmii_bus_snapshot_t;

#if XGMII_WIDTH == 64
    typedef uint64_t xgmii_data_signal_t;
    typedef uint8_t xgmii_ctl_signal_t;

    #define XGMII_DATA_SIGNAL_MASK 0xFFFFFFFFFFFFFFFF
    #define XGMII_CTL_SIGNAL_MASK 0xFF

    // TODO: remove legacy defines
    #define DW_64
#elif XGMII_WIDTH == 32
    typedef uint32_t xgmii_data_signal_t;
    typedef uint8_t xgmii_ctl_signal_t;

    #define XGMII_DATA_SIGNAL_MASK 0xFFFFFFFF
    #define XGMII_CTL_SIGNAL_MASK 0x0F
    #define XGMII_UPPER_DATA_SHIFT 32
    #define XGMII_UPPER_CTL_SHIFT 4
#else
#error "Invalid XGMII data width!"
#endif

// XGMII RX Mealy state machine
//
// State transitions and outputs:
//
//   IDLE
//   |-> IDLE:    data = XGMII_IDLE_DATA
//   |            ctl  = XGMII_IDLE_CTL
//   \-> PREAMB:  data = (XGMII_FB_PREAMBLE_SF_DATA & 0xFFFFFFFF)
//                ctl  = (XGMII_FB_PREAMBLE_SF_CTL & 0xF)
//
//   PREAMB
//   \-> RECEIVE: data = ((XGMII_FB_PREAMBLE_SF_DATA >> 32) & 0xFFFFFFFF)
//                ctl  = ((XGMII_FB_PREAMBLE_SF_CTL >> 4) & 0xF)
//
//   RECEIVE
//   |-> RECEIVE: data = 4 * <payload>
//   |            ctl  = 0x0
//   \-> IDLE:    data = m * XGMII_CTLCHAR_IDLE
//                       | XGMII_CTLCHAR_PACKET_END
//                       | n * <payload>
//                ctl  = 0xF & ~(2 ** n - 1)
typedef enum xgmii_rx_state {
    XGMII_RX_STATE_IDLE,
    XGMII_RX_STATE_PREAMB,
    XGMII_RX_STATE_RECEIVE,
} xgmii_rx_state_t;

// XGMII TX Mealy state machine
typedef enum xgmii_tx_state {
    XGMII_TX_STATE_IDLE,
    XGMII_TX_STATE_PREAMB,
    XGMII_TX_STATE_TRANSMIT,
    XGMII_TX_STATE_ABORT,
} xgmii_tx_state_t;

// RX incoming (TAP -> Sim) Ethernet packet queue structs
typedef struct eth_packet_queue {
    // Does not contain the trailing CRC32 checksum
    uint8_t data[ETH_LEN];
    size_t len;
    struct eth_packet_queue *next;
} eth_packet_queue_t;

typedef struct xgmii_state {
    // ---------- SIMULATION & BUS STATE ----------
    // XGMII bus signals
    xgmii_data_signal_t *tx_data_signal;
    xgmii_ctl_signal_t  *tx_ctl_signal;
    xgmii_data_signal_t *rx_data_signal;
    xgmii_ctl_signal_t  *rx_ctl_signal;

    // RX clock signal and edge state
    uint8_t *rx_clk;
    clk_edge_state_t rx_clk_edge;

    // TX clock signal and edge state
    uint8_t *tx_clk;
    clk_edge_state_t tx_clk_edge;

    // ---------- GLOBAL STATE --------
    tapcfg_t *tapcfg;
    int tap_fd;

    // ---------- TX (Sim -> TAP) STATE ---------
    xgmii_tx_state_t tx_state;

    // Packet currently being transmitted over the XGMII bus (Sim -> TAP).
    uint8_t current_tx_pkt[ETH_LEN];
    size_t current_tx_len;

    // ---------- RX (TAP -> Sim) STATE ---------
    xgmii_rx_state_t rx_state;

    // How many bytes of inter-frame gap we've produced on the XGMII
    // bus (bounded counter to 12).
    size_t rx_ifg_count;

#ifdef XGMII_RX_DIC_ENABLE
    // Because XGMII only allows start of frame characters to be placed on lane
    // 0 (first octet in a 32-bit XGMII bus word), when a packet's length % 4 !=
    // 0, we can't transmit exactly 12 XGMII idle characters inter-frame gap
    // (the XGMII end of frame character counts towards the inter-frame gap,
    // while start of frame does not). Given we are required to transmit a
    // minimum of 12 bytes IFG, it's allowed to send packet length % 4 bytes
    // additional IFG bytes. However this would waste precious bandwidth
    // transmitting these characters.
    //
    // Thus, 10Gbit/s Ethernet and above allow using the deficit idle count
    // mechanism. It allows to delete some idle characters, as long as an
    // average count of >= 12 bytes IFG is maintained. This is to be implemented
    // as a two bit counter as specified in IEEE802.3-2018, section four,
    // 46.3.1.4 Start control character alignment.
    //
    // This module optionally implements the deficit idle count algorithm as
    // described by Eric Lynskey of the UNH InterOperability Lab[1]:
    //
    // | current |             |             |             |             |
    // | count   |           0 |           1 |           2 |           3 |
    // |---------+-----+-------+-----+-------+-----+-------+-----+-------|
    // |         |     | new   |     | new   |     | new   |     | new   |
    // | pkt % 4 | IFG | count | IFG | count | IFG | count | IFG | count |
    // |---------+-----+-------+-----+-------+-----+-------+-----+-------|
    // |       0 |  12 |     0 |  12 |     1 |  12 |     2 |  12 |     3 |
    // |       1 |  11 |     1 |  11 |     2 |  11 |     3 |  15 |     0 |
    // |       2 |  10 |     2 |  10 |     3 |  14 |     0 |  14 |     1 |
    // |       3 |   9 |     3 |  13 |     0 |  13 |     1 |  13 |     2 |
    //
    // [1]: https://www.iol.unh.edu/sites/default/files/knowledgebase/10gec/10GbE_DIC.pdf
    size_t rx_dic;
#endif

    // Packet currently being received over the XGMII bus (TAP ->
    // Sim). Packets copied here are already removed from the TAP
    // incoming queue. Fields are valid if current_rx_len != 0. This
    // field includes the CRC32 checksum.
    uint8_t current_rx_pkt[ETH_LEN + sizeof(uint32_t)];
    size_t current_rx_len;
    size_t current_rx_progress;

    // Linked list of pending RX (TAP -> Sim) packets. tail is only
    // valid when head != NULL.
    eth_packet_queue_t *pending_rx_pkt_head;
    eth_packet_queue_t *pending_rx_pkt_tail;
    struct event *ev;
} xgmii_ethernet_state_t;

// Shared libevent state, set on module init
static struct event_base *base = NULL;

/**
 * Check whether sufficient IFG (XGMII IDLE characters) has been inserted on the
 * XGMII interface to start a new transmission.
 *
 * If enabled, this method must conform to the DIC mechanism and thus allow
 * transmission with up to 3 deleted XGMII idle characters.
 */
bool xgmii_ethernet_rx_sufficient_ifg(xgmii_ethernet_state_t *s);

/**
 * Update the internal DIC count based on the actual inserted IFG.
 *
 * This method MUST be called on/after the start of a new transmission,
 * regardless of whether the DIC mechanism is enabled.
 */
void xgmii_ethernet_rx_update_dic(xgmii_ethernet_state_t *s, size_t gen_ifg);

// Implementation of the forwards-declared methods, depending on whether
// XGMII_RX_DIC_ENABLE is on.
#ifdef XGMII_RX_DIC_ENABLE
bool xgmii_ethernet_rx_sufficient_ifg(xgmii_ethernet_state_t *s) {
    return s->rx_ifg_count >= 9 + s->rx_dic;
}
void xgmii_ethernet_rx_update_dic(xgmii_ethernet_state_t *s, size_t gen_ifg) {
    // Check whether we've deleted or inserted some IDLE characters and update
    // the DIC count accordingly.
    if (gen_ifg < 9) {
        fprintf(stderr, "[xgmii_ethernet]: PANIC PANIC PANIC - RX generated "
                "invalid IFG: %lu!\n", gen_ifg);
    }

    if (gen_ifg < 12) {
        // Deleted characters, add them to the DIC
        s->rx_dic += 12 - gen_ifg;
    } else if (gen_ifg > 12) {
        // Inserted characters, subtract them from the DIC, avoiding an
        // underflow
        if (s->rx_dic < gen_ifg - 12) {
            s->rx_dic = 0;
        } else {
            s->rx_dic -= gen_ifg - 12;
        }
    }
}
#else
bool xgmii_ethernet_rx_sufficient_ifg(xgmii_ethernet_state_t *s) {
    return s->rx_ifg_count >= 12;
}
void xgmii_ethernet_rx_update_dic(xgmii_ethernet_state_t *s, size_t gen_ifg) {}
#endif

/**
 * Advance the RX (TAP->Sim) state machine, producing a 32-bit bus word
 *
 * For a 32-bit bus, call this method on either clock edge to retrieve a valid
 * bus word. When using a 64-bit (non-DDR) bus, this method must be called twice
 * on a rising clock edge, resulting in the lower and upper half of the 64-bit
 * XGMII bus word.
 *
 * This function will detect pending RX packets in the queue and remove them
 * accordingly, and keeps track of the IFG and DIC. Thus it is important that
 * this function will be called on every clock edge (32-bit bus) or twice on the
 * rising clock edge (64-bit bus), regardless of whether a packet is currently
 * being transmitted.
 */
static xgmii_bus_snapshot_t xgmii_ethernet_rx_adv(xgmii_ethernet_state_t *s,
                                                 uint64_t time_ps) {
    xgmii_bus_snapshot_t bus;

    // Check whether we are currently transmitting a packet over the XGMII
    // interface (i.e. whether there are still bytes left in the packet input
    // buffer)
    if (s->current_rx_len) {
        // There are bytes to send, check whether we're currently idling or
        // already transmitting.
        if (s->rx_state == XGMII_RX_STATE_IDLE) {
            // Currently idling, do we have sufficient IFG?
            if (xgmii_ethernet_rx_sufficient_ifg(s)) {
                // Yup, we can start a transmission.

                // Update the DIC if enabled
                xgmii_ethernet_rx_update_dic(s, s->rx_ifg_count);

                // Reset the transmit progress
                s->current_rx_progress = 0;

                // Reset the inter-frame gap counter
                s->rx_ifg_count = 0;

                // Send the start-of-packet XGMII control code, and the first half
                // of the preamble.
                bus.data = XGMII_FB_PREAMBLE_SF_DATA & 0xFFFFFFFF;
                bus.ctl  = XGMII_FB_PREAMBLE_SF_CTL & 0xF;

                // Enter the PREAMB state.
                s->rx_state = XGMII_RX_STATE_PREAMB;
            } else {
                // We are in IDLE and have a packet ready, but need to wait
                // until we've accumulated sufficient IFG.
                bus.data = XGMII_IDLE_DATA;
                bus.ctl  = XGMII_IDLE_CTL;
                for (size_t i = 0; i < sizeof(bus.data); i++) {
                    XGMII_RX_IFG_INC(s);
                }
            }
        } else if (s->rx_state == XGMII_RX_STATE_PREAMB) {
            // We have initiated a new transmission, time to send the second
            // half of the preamble and the Ethernet start character.
            bus.data = (XGMII_FB_PREAMBLE_SF_DATA >> 32) & 0xFFFFFFFF;
            bus.ctl  = (XGMII_FB_PREAMBLE_SF_CTL >> 4) & 0xF;

            // Enter the RECEIVE state.
            s->rx_state = XGMII_RX_STATE_RECEIVE;
        } else if (s->rx_state == XGMII_RX_STATE_RECEIVE) {
            // Reception of the packet has been initiated, transfer as much as
            // required.

            // Initialize ctl and data to zero
            bus.ctl = 0;
            bus.data = 0;

            // Place the bytes one by one: either with data, end of frame
            // delimiters or idle markers
            for (int idx = 0; idx < sizeof(bus.data); idx++) {
                if (s->current_rx_progress < s->current_rx_len) {
                    // Actual data byte to transmit
                    bus.data |=
                        ((xgmii_data_t)
                         (s->current_rx_pkt[s->current_rx_progress] & 0xFF))
                        << (idx * 8);
                    s->current_rx_progress++;
                } else if (s->current_rx_progress == s->current_rx_len) {
                    // End of frame delimiter to transmit
                    bus.data |=
                        ((xgmii_data_t) XGMII_CTLCHAR_END)
                        << (idx * 8);
                    bus.ctl  |= 1 << idx;

                    // The end of frame XGMII control character counts towards
                    // the inter-frame gap
                    XGMII_RX_IFG_INC(s);

                    // We deliberately let the progress advance beyond the
                    // length here, to indicate that we've already transmitted
                    // the end-of-frame buffer
                    s->current_rx_progress++;

                    // Furthermore, set the packet length to zero to mark
                    // that a new packet can be transmitted (invalidating
                    // the current one).
                    s->current_rx_len = 0;

                    // We return into the idle state here, there's nothing more
                    // to send.
                    s->rx_state = XGMII_RX_STATE_IDLE;
                } else {
                    // Fill the rest of this bus word with idle indicators
                    bus.data |=
                        ((xgmii_data_t) XGMII_CTLCHAR_IDLE) << (idx * 8);
                    bus.ctl  |= 1 << idx;

                    // The trailing XGMII idle characters on the last bus word
                    // count towards the inter-frame gap
                    XGMII_RX_IFG_INC(s);
                }
            }

            // If not transitioned to IDLE state above, remain in RECEIVE
            // state.
        } else {
            fprintf(stderr, "[xgmii_ethernet]: PANIC PANIC PANIC - RX state "
                    "machine reached invalid state!\n");

            // We need to produce a valid bus word to avoid returning some
            // uninitialized memory. Set to IDLE, but don't count towards IFG
            // because this should never happen and we don't want to ruin the
            // next transmission because of insufficent IFG as well.
            bus.data = XGMII_IDLE_DATA;
            bus.ctl  = XGMII_IDLE_CTL;

            // Return to idle in the hopes that we aren't entirely broken.
            s->rx_state = XGMII_RX_STATE_IDLE;
        }
    } else {
        // No packet to transmit, indicate that we are idle.
        bus.data = XGMII_IDLE_DATA;
        bus.ctl  = XGMII_IDLE_CTL;
        for (size_t i = 0; i < sizeof(bus.data); i++) {
            XGMII_RX_IFG_INC(s);
        }
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

#ifdef XGMII_RX_DEBUG
            fprintf(stderr, "\n----------------------------------\n"
                    "Received packet with %ld bytes\n", popped_rx_pkt->len);
            for (size_t i = 0; i < popped_rx_pkt->len; i++) {
                fprintf(stderr, "%02x", popped_rx_pkt->data[i] & 0xff);
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
            // the XGMII interface
            s->current_rx_len = copy_len + sizeof(uint32_t);

            // Release the packet data memory
            free(popped_rx_pkt);
        }
    }

    return bus;
}

/**
 * Advance the TX (Sim -> TAP) state machine based on a 32-bit bus word
 *
 * This method must be called whenever 32-bit bus word has been transmitted by
 * the device. This means that for a 64-bit bus, it must be invoked twice on the
 * rising clock edge, first with the lower and subsequently with the upper half
 * of the 64-bit bus word, whereas on a 32-bit (DDR) bus it must be invoked on
 * the rising and falling clock edge with the respective 32-bit bus words.
 *
 * This function will detect frames sent by the device and place them on the TAP
 * network interface.
 */
static void xgmii_ethernet_tx_adv(xgmii_ethernet_state_t *s, uint64_t time_ps,
                                  xgmii_bus_snapshot_t bus) {
    if (s->tx_state == XGMII_TX_STATE_IDLE) {
        // Idling until a XGMII start of packet control marker is detected. By
        // IEEE802.3, this must be on lane 0, i.e. the first octect of the XGMII
        // bus, replacing one Ethernet preamble octet.
        if ((bus.data & 0xFF) == XGMII_CTLCHAR_START && (bus.ctl & 0x1) != 0) {
            // The rest of the 32-bit data word must 24 bits of the
            // preamble. The rest of the preamble and the the Ethernet start of
            // frame delimiter are expected on the subsequent invocation of
            // xgmii_ethernet_tx_adv.
            if (bus.data == (XGMII_FB_PREAMBLE_SF_DATA & 0xFFFFFFFF)
                && bus.ctl == (XGMII_FB_PREAMBLE_SF_CTL & 0xF)) {
                // XGMII start character and first half of preamble detected.

                // Reset the current progress
                s->current_tx_len = 0;

                // Switch to the PREAMB state
                s->tx_state = XGMII_TX_STATE_PREAMB;
            } else {
                fprintf(stderr, "[xgmii_ethernet]: got XGMII start character, "
                        "but Ethernet preamble is not valid: %08x %01x. "
                        "Discarding rest of transaction.\n",
                        bus.data, bus.ctl);
                s->tx_state = XGMII_TX_STATE_ABORT;
            }
        } else {
#ifdef XGMII_TX_DEBUG_INVAL_SIGNAL
            for (size_t idx = 0; idx < sizeof(xgmii_data_t); idx++) {
                if ((bus.ctl & (1 << idx)) != 0) {
                    if (((bus.data >> (idx * 8)) & 0xFF) != 0x07) {
                        fprintf(stderr, "[xgmii_ethernet]: got invalid XGMII "
                                "control character in XGMII_TX_STATE_IDLE: "
                                "%08x %01x %lu\n", bus.data, bus.ctl, idx);
                    }
                } else {
                    fprintf(stderr, "[xgmii_ethernet]: got non-XGMII control "
                            "character in XGMII_TX_STATE_IDLE without "
                            "proper XGMII_CTLCHAR_START: %08x %01x %lu\n",
                            bus.data, bus.ctl, idx);
                }
            }
#endif
        }
    } else if (s->tx_state == XGMII_TX_STATE_PREAMB) {
        // We've seen the XGMII start of frame control character. This bus word
        // MUST contain the rest of the Ethernet preamble.
        if (bus.data == ((XGMII_FB_PREAMBLE_SF_DATA >> 32) & 0xFFFFFFFF)
            && bus.ctl == ((XGMII_FB_PREAMBLE_SF_CTL >> 4) & 0xF)) {
            // Rest of the Ethernet preamble and Ethernet start of frame
            // delimiter detected. Continue in the TRANSMIT state.
            s->tx_state = XGMII_TX_STATE_TRANSMIT;
        } else {
            fprintf(stderr, "[xgmii_ethernet]: got XGMII start character and "
                    "partially valid Ethernet preamble, but either second "
                    "half of Ethernet preamble or Ethernet start of frame "
                    "delimiter is not valid: %08x %01x. Discarding rest of "
                    "transaction.\n", bus.data, bus.ctl);
            s->tx_state = XGMII_TX_STATE_ABORT;
        }
    } else if (s->tx_state == XGMII_TX_STATE_TRANSMIT) {
        // Iterate over all bytes until we hit an XGMII end of frame control
        // character
        size_t idx;
        bool drop_warning_issued = false;
        bool transmission_finished = false;
        for (idx = 0; idx < sizeof(xgmii_data_t); idx++) {
            // Check whether we are reading a data or control character
            if ((bus.ctl & (1 << idx)) == 0) {
                // We are reading a data character. If ETH_LEN is reached, drop
                // other bytes and issue a warning once.
                if (s->current_tx_len <= ETH_LEN) {
                    s->current_tx_pkt[s->current_tx_len++] =
                        (uint8_t) (bus.data >> (idx * 8) & 0xFF);
                } else if (!drop_warning_issued) {
                    drop_warning_issued = true;
                    fprintf(stderr, "[xgmii_ethernet]: TX ETH_LEN reached, "
                            "dropping frame data. Check the MTU.\n");
                }
            } else {
                // Check what type of control character is received. Only
                // XGMII_CTLCHAR_END is valid, all others indicate an error
                // condition.
                if (((bus.data >> (idx * 8)) & 0xFF) == XGMII_CTLCHAR_END) {
                    transmission_finished = true;
                    idx++; // Important to avoid checking the XGMII_CTLCHAR_END
                           // in the debug for-loop below
                    break;
                } else {
                    fprintf(stderr, "[xgmii_ethernet]: received non-end XGMII "
                            "control character in XGMII_TX_STATE_TRANSMIT. "
                            "Aborting TX. %08x %01x %lu\n", bus.data, bus.ctl,
                            idx);
                    s->tx_state = XGMII_TX_STATE_ABORT;
                    return;
                }
            }
        }

#ifdef XGMII_TX_DEBUG_INVAL_SIGNAL
        // If additional debugging is enabled, also verify that all remaining
        // bytes are XGMII idle markers. This must be true, as the only
        // possibility for there to be remaining bytes is to exit the loop with
        // a break statement, which only happens in the case a XGMII end control
        // character is recognized. The next frame can however only start with
        // the next 64-bit bus word. Thus the device must fill the rest of the
        // 64-bit bus word with idle control characters.
        //
        // Avoid further incrementing `idx` conditionally due to preprocessor
        // macros to prevent introducing tricky bugs.
        for (size_t chk_idx = idx; chk_idx < sizeof(xgmii_data_t); chk_idx++) {
            if ((bus.ctl & (1 << chk_idx)) == 0
                || ((bus.data >> (chk_idx * 8)) & 0xFF) != XGMII_CTLCHAR_IDLE) {
                fprintf(stderr, "[xgmii_ethernet]: received non-XGMII idle "
                        "control character after XGMII end of frame marker. "
                        "%08x %01x %lu\n", bus.data, bus.ctl, chk_idx);
            }
        }
#endif

        // Length without frame check sequence
        size_t pkt_len =
            (s->current_tx_len > 3) ? s->current_tx_len - 4 : 0;

        if (transmission_finished) {
#ifdef XGMII_TX_DEBUG
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
                fprintf(stderr, "[xgmii_ethernet]: TX packet too short to contain "
                        "frame check sequence\n");
            } else {
                uint32_t crc = crc32(0, s->current_tx_pkt, pkt_len);
                if (!((s->current_tx_pkt[pkt_len + 0] == ((crc >>  0) & 0xFF))
                      && (s->current_tx_pkt[pkt_len + 1] == ((crc >>  8) & 0xFF))
                      && (s->current_tx_pkt[pkt_len + 2] == ((crc >> 16) & 0xFF))
                      && (s->current_tx_pkt[pkt_len + 3] == ((crc >> 24) & 0xFF))))
                    {
                        fprintf(stderr, "[xgmii_ethernet]: TX packet FCS mismatch. "
                                "Expected: %08x. Actual: %08x.\n", crc,
                                (uint32_t) s->current_tx_pkt[pkt_len + 0] << 0
                                | (uint32_t) s->current_tx_pkt[pkt_len + 1] << 8
                                | (uint32_t) s->current_tx_pkt[pkt_len + 2] << 16
                                | (uint32_t) s->current_tx_pkt[pkt_len + 3] << 24);
                    }
            }


            // Packet read completely, place it on the TAP interface
            tapcfg_write(s->tapcfg, s->current_tx_pkt, s->current_tx_len);
            s->tx_state = XGMII_TX_STATE_IDLE;
        }
    } else if (s->tx_state == XGMII_TX_STATE_ABORT) {
        // The transmission has been aborted. Scan for the end of the
        // transmission (XGMII end control character) and return back to IDLE.
        for (size_t i = 0; i < sizeof(xgmii_data_t); i++) {
            if ((bus.ctl & (1 << i)) == 1
                && ((bus.data >> (i * 8)) & 0xFF) == XGMII_CTLCHAR_END) {
                s->tx_state = XGMII_TX_STATE_IDLE;
            }
        }
    } else {
        fprintf(stderr, "[xgmii_ethernet]: PANIC PANIC PANIC - TX state "
                "machine reached invalid state!\n");
        s->tx_state = XGMII_TX_STATE_IDLE;
    }
}

static int xgmii_ethernet_tick(void *state, uint64_t time_ps) {
    xgmii_ethernet_state_t *s = (xgmii_ethernet_state_t*) state;

    // ---------- TX BUS (Sim -> TAP) ----------

    // Determine the current TX clock edge. Depending on the XGMII_WIDTH, we
    // must act on both the rising and falling clock edge.
    clk_edge_t tx_edge = clk_edge(&s->tx_clk_edge, *s->tx_clk);

#if XGMII_WIDTH == 64
    // 64-bit bus. Sample the entire data on the rising clock edge and process
    // accordingly (invoke xgmii_ethernet_tx_adv twice).
    if (tx_edge == CLK_EDGE_RISING) {
        xgmii_bus_snapshot_t tx_bus_lower = {
            .data = *s->tx_data_signal & 0xFFFFFFFF,
            .ctl = *s->tx_ctl_signal & 0xF,
        };

        xgmii_ethernet_tx_adv(s, time_ps, tx_bus_lower);

        xgmii_bus_snapshot_t tx_bus_upper = {
            .data = (*s->tx_data_signal >> 32) & 0xFFFFFFFF,
            .ctl = (*s->tx_ctl_signal >> 4) & 0xF,
        };

        xgmii_ethernet_tx_adv(s, time_ps, tx_bus_upper);
    }
#elif XGMII_WIDTH == 32
    // 32-bit bus.
    xgmii_bus_snapshot_t tx_bus = {
        .data = *s->tx_data_signal,
        .ctl = *s->tx_ctl_signal,
    };

    xgmii_ethernet_tx_adv(s, time_ps, tx_bus);
#endif

    // ---------- RX BUS (TAP -> Sim) ----------

    // Determine the current RX clock edge. Depending on the XGMII_WIDTH, we
    // must act on both the rising and falling clock edge.
    clk_edge_t rx_edge = clk_edge(&s->rx_clk_edge, *s->rx_clk);

    if (rx_edge == CLK_EDGE_RISING) {
        // Positive clock edge, advance the RX state and place new contents on
        // the XGMII RX bus.

#if XGMII_WIDTH == 64
        // 64-bit wide bus. We must transmit two XGMII 32-bit bus words in the
        // same cycle.
        xgmii_bus_snapshot_t rx_bus_lower = xgmii_ethernet_rx_adv(s, time_ps);
        xgmii_bus_snapshot_t rx_bus_upper = xgmii_ethernet_rx_adv(s, time_ps);
        *s->rx_data_signal =
            ((xgmii_data_signal_t) rx_bus_upper.data << 32)
            | (xgmii_data_signal_t) rx_bus_lower.data;
        *s->rx_ctl_signal =
            ((xgmii_ctl_signal_t) rx_bus_upper.ctl << 4)
            | (xgmii_ctl_signal_t) rx_bus_lower.ctl;
#elif XGMII_WIDTH == 32
        // 32-bit wide bus.
        xgmii_bus_snapshot_t rx_bus = xgmii_ethernet_rx_adv(s, time_ps);
        *s->rx_data_signal = rx_bus.data;
        *s->rx_ctl_signal = rx_bus.ctl;
#endif
    }

#if XGMII_WIDTH == 32
    if (rx_edge == CLK_EDGE_FALLING) {
        // 32-bit wide bus and negative clock edge.
        xgmii_bus_snapshot_t rx_bus = xgmii_ethernet_rx_adv(s, time_ps);
        *s->rx_data_signal = rx_bus.data;
        *s->rx_ctl_signal = rx_bus.ctl;
    }
#endif

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
        fprintf(stderr, "[xgmii_ethernet]: error parsing json arg: %s\n", args);
        ret = RC_JSERROR;
        goto out;
    }

    if (!json_object_is_type(jsobj, json_type_object)) {
        fprintf(stderr, "[xgmii_ethernet]: arg must be type object!: %s\n",
                args);
        ret = RC_JSERROR;
        goto out;
    }

    obj = NULL;
    r = json_object_object_get_ex(jsobj, arg, &obj);
    if (!r) {
        fprintf(stderr, "[xgmii_ethernet]: could not find object: \"%s\" "
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
    xgmii_ethernet_state_t *s = arg;

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
            fprintf(stderr, "[xgmii_ethernet]: TAP read error %d\n", read_len);
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

static int xgmii_ethernet_add_pads(void *state, struct pad_list_s *plist) {
    int ret = RC_OK;
    xgmii_ethernet_state_t *s = (xgmii_ethernet_state_t*) state;
    struct pad_s *pads;
    if (!state || !plist) {
        ret = RC_INVARG;
        goto out;
    }
    pads = plist->pads;
    if (!strcmp(plist->name, "xgmii_eth")) {
        litex_sim_module_pads_get(pads, "rx_data", (void**) &s->rx_data_signal);
        litex_sim_module_pads_get(pads, "rx_ctl", (void**) &s->rx_ctl_signal);
        litex_sim_module_pads_get(pads, "tx_data", (void**) &s->tx_data_signal);
        litex_sim_module_pads_get(pads, "tx_ctl", (void**) &s->tx_ctl_signal);
    }

    if (!strcmp(plist->name, "sys_clk")) {
        // TODO: currently the single sys_clk signal is used for both the RX and
        // TX XGMII clock signals. This should be changed. Also, using sys_clk
        // does not make sense for the 32-bit DDR bus.
        litex_sim_module_pads_get(pads, "sys_clk", (void**)&s->rx_clk);
        s->tx_clk = s->rx_clk;
    }

out:
    return ret;
}

static int xgmii_ethernet_start(void *b) {
  base = (struct event_base *) b;
  printf("[xgmii_ethernet] loaded (%p)\n", base);
  return RC_OK;
}

static int xgmii_ethernet_new(void **state, char *args) {
    int ret = RC_OK;
    char *c_tap = NULL;
    char *c_tap_ip = NULL;
    xgmii_ethernet_state_t *s = NULL;
    struct timeval tv = {10, 0};

    if (!state) {
        ret = RC_INVARG;
        goto out;
    }

    s = (xgmii_ethernet_state_t*)malloc(sizeof(xgmii_ethernet_state_t));
    if (!s) {
        ret = RC_NOENMEM;
        goto out;
    }
    memset(s, 0, sizeof(xgmii_ethernet_state_t));

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
    "xgmii_ethernet",
    xgmii_ethernet_start,
    xgmii_ethernet_new,
    xgmii_ethernet_add_pads,
    NULL,
    xgmii_ethernet_tick
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *)) {
    int ret = RC_OK;

    // Initiate calculation of zlib's CRC32 lookup table such that multithreaded
    // calls to crc32() are safe.
    get_crc_table();

    ret = register_module(&ext_mod);
    return ret;
}
