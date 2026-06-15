//
// JTAGPHY Shift Register for ECP5
//
// This module handles the JTAG shift register logic and provides
// clean interfaces for CDC via AsyncFIFO. The CDC is handled in Migen.
//
// Supports continuous multi-word Shift-DR operation as used by
// litex_server's jtagstream (multiple 11-bit words in a single drscan).
//
// Wire format (11 bits, LSB first):
//   Host -> Target: [padding:10][rx_valid:9][rx_data:8-1][tx_ready:0]
//   Target -> Host: [padding:10][tx_valid:9][tx_data:8-1][rx_ready:0]
//
// JTDI/TDO timing (per Tom Verbeure's analysis):
//   - JTDI = FF(posedge TCK, TDI) - JTDI is registered, 1 cycle late
//   - TDO = FF(negedge TCK, JTDO1) - TDO sampled on falling edge
//   - First JSHIFT cycle: JTDI is NOT valid (stale)
//   - JTDI lags TDI by 1 TCK cycle
//
// Multi-word timing (continuous Shift-DR):
//   count:  0   1   2   3  ...  9  10 | 0   1   2  ...
//   JTDI: stale b0  b1  b2 ... b8  b9 |b10 b0' b1' ...
//                                       ^-- last bit of previous word
//   At count=0: capture JTDI (=previous word's bit 10), extract word
//               load new TX word
//   At count=1..10: shift JTDI into RX, shift TX out
//
// Copyright (c) 2026 LiteX-SDR Project
// SPDX-License-Identifier: BSD-2-Clause

`default_nettype none

module jtagphy_shift #(
    parameter DATA_WIDTH = 8
)(
    // JTAG clock output (directly from JTAGG primitive)
    output wire jtag_clk,
    output wire jtag_rst,

    // RX interface (JTAG domain) - data received from host
    output reg  [DATA_WIDTH-1:0] rx_data,
    output reg                   rx_valid,
    input  wire                  rx_ready,

    // TX interface (JTAG domain) - data to send to host
    input  wire [DATA_WIDTH-1:0] tx_data,
    input  wire                  tx_valid,
    output wire                  tx_ready,

    // Debug outputs
    output reg [7:0] debug_shift_count,
    output reg [7:0] debug_rx_count,
    output reg [7:0] debug_tx_count
);

    // =========================================================================
    // JTAGG Primitive Instantiation
    // =========================================================================

    wire jtagg_jtck;
    wire jtagg_jtdi;
    wire jtagg_jshift;
    wire jtagg_jupdate;
    wire jtagg_jrstn;
    wire jtagg_jce1;

    JTAGG jtagg_inst (
        .JTCK(jtagg_jtck),
        .JTDI(jtagg_jtdi),
        .JSHIFT(jtagg_jshift),
        .JUPDATE(jtagg_jupdate),
        .JRSTN(jtagg_jrstn),
        .JCE1(jtagg_jce1),
        .JCE2(),
        .JRTI1(),
        .JRTI2(),
        .JTDO1(tx_shift_nxt[0]),  // TDO driven by combinational next-state
        .JTDO2(1'b0)
    );

    // Output JTAG clock for CDC
    // Use inverted clock per Hazard3 approach - gives half-cycle setup margin
    wire jtck = ~jtagg_jtck;
    assign jtag_clk = jtck;
    assign jtag_rst = ~jtagg_jrstn;

    // =========================================================================
    // Shift Register Logic with Modulo-11 Counter
    // =========================================================================

    reg jshift_dly;
    reg [10:0] rx_shift;
    reg [10:0] tx_shift;
    reg [3:0]  bit_count;      // 0-10 for 11-bit words

    // TX data holding register
    reg [DATA_WIDTH-1:0] tx_data_hold;
    reg                  tx_valid_hold;

    // Combinational next-state (critical for TDO timing)
    reg [10:0] rx_shift_nxt;
    reg [10:0] tx_shift_nxt;

    // Word boundary detection
    wire first_shift = jtagg_jshift && !jshift_dly;  // JSHIFT rising edge
    wire last_shift  = !jtagg_jshift && jshift_dly;   // JSHIFT falling edge
    wire word_boundary = jtagg_jshift && (bit_count == 4'd0) && !first_shift;
    // word_boundary: count wrapped from 10 to 0, starting a new word
    // first_shift: very first shift cycle of entire scan

    always @(*) begin
        // Default: hold current value
        rx_shift_nxt = rx_shift;
        tx_shift_nxt = tx_shift;

        if (first_shift) begin
            // Very first cycle of scan - JTDI is stale, load TX
            tx_shift_nxt = {1'b0, tx_valid_hold, tx_data_hold, 1'b1};
        end
        else if (last_shift) begin
            // Scan ending - capture final JTDI bit
            rx_shift_nxt = {jtagg_jtdi, rx_shift[10:1]};
        end
        else if (word_boundary) begin
            // Word boundary in continuous scan:
            // JTDI has the last bit (bit 10) of previous word.
            // Capture it, then load new TX word.
            rx_shift_nxt = {jtagg_jtdi, rx_shift[10:1]};
            tx_shift_nxt = {1'b0, tx_valid_hold, tx_data_hold, 1'b1};
        end
        else if (jtagg_jshift) begin
            // Normal shift cycles
            rx_shift_nxt = {jtagg_jtdi, rx_shift[10:1]};
            tx_shift_nxt = {1'b0, tx_shift[10:1]};
        end

        // Pre-load TX when JCE1 active but JSHIFT not yet
        if (jtagg_jce1 && !jtagg_jshift) begin
            tx_shift_nxt = {1'b0, tx_valid_hold, tx_data_hold, 1'b1};
        end
    end

    // =========================================================================
    // Registered State Update
    // =========================================================================

    always @(posedge jtck) begin
        if (~jtagg_jrstn) begin
            jshift_dly <= 1'b0;
            bit_count <= 4'd0;
            rx_shift <= 11'd0;
            tx_shift <= 11'h001;
            tx_data_hold <= {DATA_WIDTH{1'b0}};
            tx_valid_hold <= 1'b0;
            rx_data <= {DATA_WIDTH{1'b0}};
            rx_valid <= 1'b0;
            debug_shift_count <= 8'd0;
            debug_rx_count <= 8'd0;
            debug_tx_count <= 8'd0;
        end else begin
            jshift_dly <= jtagg_jshift;
            rx_shift <= rx_shift_nxt;
            tx_shift <= tx_shift_nxt;

            // Clear rx_valid when consumed
            if (rx_ready && rx_valid) begin
                rx_valid <= 1'b0;
            end

            // Bit counter management
            if (first_shift) begin
                // Start of scan: reset counter
                bit_count <= 4'd1;  // We're at shift cycle 0, next will be 1
                debug_shift_count <= debug_shift_count + 8'd1;
                if (tx_valid_hold) begin
                    debug_tx_count <= debug_tx_count + 8'd1;
                end
            end
            else if (last_shift) begin
                // End of scan: extract received word
                bit_count <= 4'd0;
                if (rx_shift_nxt[9]) begin  // rx_valid bit
                    rx_data <= rx_shift_nxt[8:1];
                    rx_valid <= 1'b1;
                    debug_rx_count <= debug_rx_count + 8'd1;
                end
            end
            else if (word_boundary) begin
                // Word boundary: extract previous word, start new word
                bit_count <= 4'd1;  // Starting new word
                debug_shift_count <= debug_shift_count + 8'd1;

                // Extract received word from completed shift
                if (rx_shift_nxt[9]) begin  // rx_valid bit
                    rx_data <= rx_shift_nxt[8:1];
                    rx_valid <= 1'b1;
                    debug_rx_count <= debug_rx_count + 8'd1;
                end

                // Mark TX as sent, load new TX data
                if (tx_valid_hold) begin
                    debug_tx_count <= debug_tx_count + 8'd1;
                end
            end
            else if (jtagg_jshift) begin
                // Normal shift: increment counter with wrap
                if (bit_count == 4'd10) begin
                    bit_count <= 4'd0;  // Will trigger word_boundary next cycle
                end else begin
                    bit_count <= bit_count + 4'd1;
                end
            end

            // Latch new TX data from FIFO when available
            if (tx_valid && !tx_valid_hold) begin
                tx_data_hold <= tx_data;
                tx_valid_hold <= 1'b1;
            end
            // Clear TX valid after word boundary (data was loaded into shift reg)
            // or after JSHIFT falls (end of scan)
            if (tx_valid_hold && (word_boundary || first_shift)) begin
                tx_valid_hold <= 1'b0;
            end
        end
    end

    // TX ready - can accept new data when not holding valid data
    assign tx_ready = !tx_valid_hold;

endmodule

`default_nettype wire
