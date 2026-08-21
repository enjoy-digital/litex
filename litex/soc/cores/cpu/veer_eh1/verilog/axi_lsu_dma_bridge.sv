
// connects LSI master to external AXI slave and DMA slave
module axi_lsu_dma_bridge
#(
parameter M_ID_WIDTH = 8,
parameter S0_ID_WIDTH = 8
)
(
input                   clk,
input                   reset_l,

// master read bus
input                   m_arvalid,
input [M_ID_WIDTH-1:0]  m_arid,
input[31:0]             m_araddr,
output                  m_arready,

output                  m_rvalid,
input                   m_rready,
output [63:0]           m_rdata,
output [M_ID_WIDTH-1:0] m_rid,
output [1:0]            m_rresp,
output                  m_rlast,

// master write bus
input                   m_awvalid,
input [M_ID_WIDTH-1:0]  m_awid,
input[31:0]             m_awaddr,
output                  m_awready,

input                   m_wvalid,
output                  m_wready,

output[1:0]             m_bresp,
output                  m_bvalid,
output[M_ID_WIDTH-1:0]  m_bid,
input                   m_bready,

// slave 0 if general ext memory
output                  s0_arvalid,
input                   s0_arready,

input                   s0_rvalid,
input[S0_ID_WIDTH-1:0]  s0_rid,
input[1:0]              s0_rresp,
input[63:0]             s0_rdata,
input                   s0_rlast,
output                  s0_rready,

output                  s0_awvalid,
input                   s0_awready,

output                  s0_wvalid,
input                   s0_wready,

input[1:0]              s0_bresp,
input                   s0_bvalid,
input[S0_ID_WIDTH-1:0]  s0_bid,
output                  s0_bready,

// slave 1 if DMA port
output                  s1_arvalid,
input                   s1_arready,

input                   s1_rvalid,
input[1:0]              s1_rresp,
input[63:0]             s1_rdata,
input                   s1_rlast,
output                  s1_rready,

output                  s1_awvalid,
input                   s1_awready,

output                  s1_wvalid,
input                   s1_wready,

input[1:0]              s1_bresp,
input                   s1_bvalid,
output                  s1_bready
);

parameter ICCM_BASE = `RV_ICCM_BITS; // in LSBs
localparam IDFIFOSZ = $clog2(`RV_DMA_BUF_DEPTH);
bit[31:0] iccm_real_base_addr = `RV_ICCM_SADR ;

wire ar_slave_select;
wire aw_slave_select;
wire w_slave_select;

wire rresp_select;
wire bresp_select;
wire ar_iccm_select;
wire aw_iccm_select;

reg [1:0] wsel_iptr, wsel_optr;
reg [2:0] wsel_count;
reg [3:0] wsel;


reg [M_ID_WIDTH-1:0] arid [1<<IDFIFOSZ];
reg [M_ID_WIDTH-1:0] awid [1<<IDFIFOSZ];
reg [IDFIFOSZ-1:0] arid_cnt;
reg [IDFIFOSZ-1:0] awid_cnt;
reg [IDFIFOSZ-1:0] rid_cnt;
reg [IDFIFOSZ-1:0] bid_cnt;


// 1 select slave 1; 0 - slave 0
assign ar_slave_select = ar_iccm_select;
assign aw_slave_select = aw_iccm_select;

assign ar_iccm_select = m_araddr[31:ICCM_BASE] == iccm_real_base_addr[31:ICCM_BASE];
assign aw_iccm_select = m_awaddr[31:ICCM_BASE] == iccm_real_base_addr[31:ICCM_BASE];

assign s0_arvalid = m_arvalid & ~ar_slave_select;
assign s1_arvalid = m_arvalid &  ar_slave_select;
assign m_arready = ar_slave_select ? s1_arready : s0_arready;


assign s0_awvalid = m_awvalid & ~aw_slave_select;
assign s1_awvalid = m_awvalid & aw_slave_select;
assign m_awready = aw_slave_select ? s1_awready : s0_awready;


assign s0_wvalid = m_wvalid & ~w_slave_select;
assign s1_wvalid = m_wvalid &  w_slave_select;
assign m_wready = w_slave_select ? s1_wready : s0_wready;
assign w_slave_select = (wsel_count == 0 || wsel_count[2]) ? aw_slave_select : wsel[wsel_optr];

assign m_rvalid = s0_rvalid | s1_rvalid;
assign s0_rready = m_rready & ~rresp_select;
assign s1_rready = m_rready &  rresp_select;
assign m_rdata = rresp_select ? s1_rdata : s0_rdata;
assign m_rresp = rresp_select ? s1_rresp : s0_rresp;
assign m_rid = rresp_select ? arid[rid_cnt] : s0_rid;
assign m_rlast = rresp_select ? s1_rlast : s0_rlast;

assign rresp_select = s1_rvalid & ~s0_rvalid;

assign m_bvalid = s0_bvalid | s1_bvalid;
assign s0_bready = m_bready & ~bresp_select;
assign s1_bready = m_bready &  bresp_select;
assign m_bid = bresp_select ? awid[bid_cnt] : s0_bid;
assign m_bresp = bresp_select ? s1_bresp : s0_bresp;


assign bresp_select = s1_bvalid & ~s0_bvalid;


// W-channel select fifo
always @ (posedge clk or negedge reset_l)
    if(!reset_l) begin
        wsel_count <= '0;
        wsel_iptr <= '0;
        wsel_optr <= '0;
    end
    else begin
        if(m_awvalid & m_awready) begin
            wsel[wsel_iptr] <= aw_slave_select;
            if(!(m_wready & m_wvalid )) wsel_count <= wsel_count + 1;
            wsel_iptr <= wsel_iptr + 1;
        end
        if(m_wvalid & m_wready) begin
           if(!(m_awready & m_awvalid ) ) wsel_count <= wsel_count - 1;
           wsel_optr <= wsel_optr + 1;
        end
    end

// id replacement for narrow ID slave
always @ (posedge clk or negedge reset_l)
    if(!reset_l) begin
        arid_cnt <= '0;
        rid_cnt <= '0;
    end
    else begin
        if(ar_slave_select & m_arready & m_arvalid) begin
            arid[arid_cnt] <= m_arid;
            arid_cnt <= arid_cnt + 1;
        end
        if(rresp_select & m_rready & m_rvalid) begin
            rid_cnt <= rid_cnt + 1;
        end

    end

always @ (posedge clk or negedge reset_l)
    if(!reset_l) begin
        awid_cnt <= '0;
        bid_cnt <= '0;
    end
    else begin
        if(aw_slave_select & m_awready & m_awvalid) begin
            awid[awid_cnt] <= m_awid;
            awid_cnt <= awid_cnt + 1;
        end
        if(bresp_select & m_bready & m_bvalid) begin
            bid_cnt <= bid_cnt + 1;
        end
    end

endmodule
