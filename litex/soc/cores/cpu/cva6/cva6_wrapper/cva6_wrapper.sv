`include "axi/typedef.svh"
`include "axi/assign.svh"
`include "register_interface/typedef.svh"
`include "register_interface/assign.svh"

import cva6_wrapper_pkg::*;

module cva6_wrapper (
    input  logic         clk_i   ,
    input  logic         rst_n  ,

    input logic [31:0] irq_sources,

    // AXI i/f
    
    //AXI write address bus ------------------------------------
    output  logic [AxiIdWidthSlaves-1:0]       AWID_o     ,
    output  logic [AxiAddrWidth-1:0]  AWADDR_o   ,
    output  logic [ 7:0]                    AWLEN_o    ,
    output  logic [ 2:0]                    AWSIZE_o   ,
    output  logic [ 1:0]                    AWBURST_o  ,
    output  logic                           AWLOCK_o   ,
    output  logic [ 3:0]                    AWCACHE_o  ,
    output  logic [ 2:0]                    AWPROT_o   ,
    output  logic [ 3:0]                    AWREGION_o ,
    output  logic [ AxiUserWidth-1:0]    AWUSER_o   ,
    output  logic [ 3:0]                    AWQOS_o    ,
    output  logic                           AWVALID_o  ,
    input logic                             AWREADY_i  ,
    // ---------------------------------------------------------

    //AXI write data bus ---------------------------------------
    output  logic [AxiDataWidth-1:0]   WDATA_o    ,
    output  logic [AxiDataWidth/8-1:0]        WSTRB_o    ,
    output  logic                           WLAST_o    ,
    output  logic [AxiUserWidth-1:0]     WUSER_o    ,
    output  logic                           WVALID_o   ,
    input logic                             WREADY_i   ,
    // ---------------------------------------------------------

    //AXI write response bus -----------------------------------
    input logic   [AxiIdWidthSlaves-1:0]       BID_i      ,
    input logic   [ 1:0]                    BRESP_i    ,
    input logic                             BVALID_i   ,
    input logic   [AxiUserWidth-1:0]     BUSER_i    ,
    output  logic                           BREADY_o   ,
    // ---------------------------------------------------------

    //AXI read address bus -------------------------------------
    output  logic [AxiIdWidthSlaves-1:0]       ARID_o     ,
    output  logic [AxiAddrWidth-1:0]  ARADDR_o   ,
    output  logic [ 7:0]                    ARLEN_o    ,
    output  logic [ 2:0]                    ARSIZE_o   ,
    output  logic [ 1:0]                    ARBURST_o  ,
    output  logic                           ARLOCK_o   ,
    output  logic [ 3:0]                    ARCACHE_o  ,
    output  logic [ 2:0]                    ARPROT_o   ,
    output  logic [ 3:0]                    ARREGION_o ,
    output  logic [ AxiUserWidth-1:0]    ARUSER_o   ,
    output  logic [ 3:0]                    ARQOS_o    ,
    output  logic                           ARVALID_o  ,
    input logic                             ARREADY_i  ,
    // ---------------------------------------------------------

    //AXI read data bus ----------------------------------------
    input  logic [AxiIdWidthSlaves-1:0]        RID_i      ,
    input  logic [AxiDataWidth-1:0]     RDATA_i    ,
    input  logic [ 1:0]                     RRESP_i    ,
    input  logic                            RLAST_i    ,
    input  logic [AxiUserWidth-1:0]      RUSER_i    ,
    input  logic                            RVALID_i   ,
    output   logic                          RREADY_o   ,

    // common part
    input logic      trst_n      ,
    input  logic        tck         ,
    input  logic        tms         ,
    input  logic        tdi         ,
    output wire         tdo         ,
    output wire         tdo_oe         
);

`AXI_TYPEDEF_ALL(axi_slave,
                 logic [    AxiAddrWidth-1:0],
                 logic [AxiIdWidthSlaves-1:0],
                 logic [    AxiDataWidth-1:0],
                 logic [(AxiDataWidth/8)-1:0],
                 logic [    AxiUserWidth-1:0])

AXI_BUS #(
    .AXI_ADDR_WIDTH ( AxiAddrWidth     ),
    .AXI_DATA_WIDTH ( AxiDataWidth     ),
    .AXI_ID_WIDTH   ( AxiIdWidthMaster ),
    .AXI_USER_WIDTH ( AxiUserWidth     )
) slave[NBSlave-1:0]();

AXI_BUS #(
    .AXI_ADDR_WIDTH ( AxiAddrWidth     ),
    .AXI_DATA_WIDTH ( AxiDataWidth     ),
    .AXI_ID_WIDTH   ( AxiIdWidthSlaves ),
    .AXI_USER_WIDTH ( AxiUserWidth     )
) master[NBMaster-1:0]();

AXI_BUS #(
    .AXI_ADDR_WIDTH ( riscv::XLEN      ),
    .AXI_DATA_WIDTH ( riscv::XLEN      ),
    .AXI_ID_WIDTH   ( AxiIdWidthSlaves ),
    .AXI_USER_WIDTH ( AxiUserWidth     )
) master_to_dm[0:0]();

// disable test-enable
logic test_en;
logic ndmreset;
logic ndmreset_n;
logic debug_req_irq;
logic timer_irq;
logic ipi;

logic rtc;

// Debug
logic          debug_req_valid;
logic          debug_req_ready;
dm::dmi_req_t  debug_req;
logic          debug_resp_valid;
logic          debug_resp_ready;
dm::dmi_resp_t debug_resp;

logic dmactive;

// IRQ
logic [1:0] irq;
assign test_en    = 1'b0;

assign ndmreset_n = ~ndmreset;

// ---------------
// AXI Xbar
// ---------------

axi_pkg::xbar_rule_64_t [NBMaster-1:0] addr_map;

assign addr_map = '{
  '{ idx: cva6_wrapper_pkg::Debug,    start_addr: cva6_wrapper_pkg::DebugBase,    end_addr: cva6_wrapper_pkg::DebugBase + cva6_wrapper_pkg::DebugLength       },
  '{ idx: cva6_wrapper_pkg::CLINT,    start_addr: cva6_wrapper_pkg::CLINTBase,    end_addr: cva6_wrapper_pkg::CLINTBase + cva6_wrapper_pkg::CLINTLength       },
  '{ idx: cva6_wrapper_pkg::PLIC,     start_addr: cva6_wrapper_pkg::PLICBase,     end_addr: cva6_wrapper_pkg::PLICBase + cva6_wrapper_pkg::PLICLength         },
  '{ idx: cva6_wrapper_pkg::External, start_addr: cva6_wrapper_pkg::ExternalBase, end_addr: cva6_wrapper_pkg::ExternalBase + cva6_wrapper_pkg::ExternalLength }
};

localparam axi_pkg::xbar_cfg_t AXI_XBAR_CFG = '{
  NoSlvPorts:         NBSlave,
  NoMstPorts:         NBMaster,
  MaxMstTrans:        1, // Probably requires update
  MaxSlvTrans:        1, // Probably requires update
  FallThrough:        1'b0,
  LatencyMode:        axi_pkg::CUT_ALL_PORTS,
  AxiIdWidthSlvPorts: AxiIdWidthMaster,
  AxiIdUsedSlvPorts:  AxiIdWidthMaster,
  UniqueIds:          1'b0,
  AxiAddrWidth:       AxiAddrWidth,
  AxiDataWidth:       AxiDataWidth,
  NoAddrRules:        NBSlave
};

axi_xbar_intf #(
  .AXI_USER_WIDTH ( AxiUserWidth            ),
  .Cfg            ( AXI_XBAR_CFG            ),
  .rule_t         ( axi_pkg::xbar_rule_64_t )
) i_axi_xbar (
  .clk_i                 ( clk_i      ),
  .rst_ni                ( ndmreset_n ),
  .test_i                ( test_en    ),
  .slv_ports             ( slave      ),
  .mst_ports             ( master     ),
  .addr_map_i            ( addr_map   ),
  .en_default_mst_port_i ( '0         ),
  .default_mst_port_i    ( '0         )
);

// ---------------
// Debug Module
// ---------------
dmi_jtag i_dmi_jtag (
    .clk_i                ( clk_i                ),
    .rst_ni               ( rst_n                ),
    .dmi_rst_no           (                      ), // keep open
    .testmode_i           ( test_en              ),
    .dmi_req_valid_o      ( debug_req_valid      ),
    .dmi_req_ready_i      ( debug_req_ready      ),
    .dmi_req_o            ( debug_req            ),
    .dmi_resp_valid_i     ( debug_resp_valid     ),
    .dmi_resp_ready_o     ( debug_resp_ready     ),
    .dmi_resp_i           ( debug_resp           ),
    .tck_i                ( tck    ),
    .tms_i                ( tms    ),
    .trst_ni              ( trst_n ),
    .td_i                 ( tdi    ),
    .td_o                 ( tdo    ),
    .tdo_oe_o             ( tdo_oe )
);

ariane_axi::req_t    dm_axi_m_req;
ariane_axi::resp_t   dm_axi_m_resp;

logic                      dm_slave_req;
logic                      dm_slave_we;
logic [riscv::XLEN-1:0]    dm_slave_addr;
logic [riscv::XLEN/8-1:0]  dm_slave_be;
logic [riscv::XLEN-1:0]    dm_slave_wdata;
logic [riscv::XLEN-1:0]    dm_slave_rdata;

logic                      dm_master_req;
logic [riscv::XLEN-1:0]    dm_master_add;
logic                      dm_master_we;
logic [riscv::XLEN-1:0]    dm_master_wdata;
logic [riscv::XLEN/8-1:0]  dm_master_be;
logic                      dm_master_gnt;
logic                      dm_master_r_valid;
logic [riscv::XLEN-1:0]    dm_master_r_rdata;

// debug module
dm_top #(
    .NrHarts          ( 1                 ),
    .BusWidth         ( riscv::XLEN      ),
    .SelectableHarts  ( 1'b1              )
) i_dm_top (
    .clk_i            ( clk_i             ),
    .rst_ni           ( rst_n             ), // PoR
    .testmode_i       ( test_en           ),
    .ndmreset_o       ( ndmreset          ),
    .dmactive_o       ( dmactive          ), // active debug session
    .debug_req_o      ( debug_req_irq     ),
    .unavailable_i    ( '0                ),
    .hartinfo_i       ( {ariane_pkg::DebugHartInfo} ),
    .slave_req_i      ( dm_slave_req      ),
    .slave_we_i       ( dm_slave_we       ),
    .slave_addr_i     ( dm_slave_addr     ),
    .slave_be_i       ( dm_slave_be       ),
    .slave_wdata_i    ( dm_slave_wdata    ),
    .slave_rdata_o    ( dm_slave_rdata    ),
    .master_req_o     ( dm_master_req     ),
    .master_add_o     ( dm_master_add     ),
    .master_we_o      ( dm_master_we      ),
    .master_wdata_o   ( dm_master_wdata   ),
    .master_be_o      ( dm_master_be      ),
    .master_gnt_i     ( dm_master_gnt     ),
    .master_r_valid_i ( dm_master_r_valid ),
    .master_r_rdata_i ( dm_master_r_rdata ),
    .dmi_rst_ni       ( rst_n             ),
    .dmi_req_valid_i  ( debug_req_valid   ),
    .dmi_req_ready_o  ( debug_req_ready   ),
    .dmi_req_i        ( debug_req         ),
    .dmi_resp_valid_o ( debug_resp_valid  ),
    .dmi_resp_ready_i ( debug_resp_ready  ),
    .dmi_resp_o       ( debug_resp        )
);

axi2mem #(
    .AXI_ID_WIDTH   ( AxiIdWidthSlaves    ),
    .AXI_ADDR_WIDTH ( riscv::XLEN        ),
    .AXI_DATA_WIDTH ( riscv::XLEN        ),
    .AXI_USER_WIDTH ( AxiUserWidth        )
) i_dm_axi2mem (
    .clk_i      ( clk_i                     ),
    .rst_ni     ( rst_n                     ),
    .slave      ( master_to_dm[0]           ),
    .req_o      ( dm_slave_req              ),
    .we_o       ( dm_slave_we               ),
    .addr_o     ( dm_slave_addr             ),
    .be_o       ( dm_slave_be               ),
    .data_o     ( dm_slave_wdata            ),
    .data_i     ( dm_slave_rdata            )
);

if (riscv::XLEN==32 ) begin

    assign master_to_dm[0].aw_user = '0;
    assign master_to_dm[0].w_user = '0;
    assign master_to_dm[0].ar_user = '0;

    assign master_to_dm[0].aw_id = dm_axi_m_req.aw.id;
    assign master_to_dm[0].ar_id = dm_axi_m_req.ar.id;

    assign master[cva6_wrapper_pkg::Debug].r_user ='0;
    assign master[cva6_wrapper_pkg::Debug].b_user ='0;
 
    xlnx_axi_dwidth_converter_dm_slave  i_axi_dwidth_converter_dm_slave( 
        .s_axi_aclk(clk_i),
        .s_axi_aresetn(ndmreset_n),
        .s_axi_awid(master[cva6_wrapper_pkg::Debug].aw_id),
        .s_axi_awaddr(master[cva6_wrapper_pkg::Debug].aw_addr[31:0]),
        .s_axi_awlen(master[cva6_wrapper_pkg::Debug].aw_len),
        .s_axi_awsize(master[cva6_wrapper_pkg::Debug].aw_size),
        .s_axi_awburst(master[cva6_wrapper_pkg::Debug].aw_burst),
        .s_axi_awlock(master[cva6_wrapper_pkg::Debug].aw_lock),
        .s_axi_awcache(master[cva6_wrapper_pkg::Debug].aw_cache),
        .s_axi_awprot(master[cva6_wrapper_pkg::Debug].aw_prot),
        .s_axi_awregion(master[cva6_wrapper_pkg::Debug].aw_region),
        .s_axi_awqos(master[cva6_wrapper_pkg::Debug].aw_qos),
        .s_axi_awvalid(master[cva6_wrapper_pkg::Debug].aw_valid),
        .s_axi_awready(master[cva6_wrapper_pkg::Debug].aw_ready),
        .s_axi_wdata(master[cva6_wrapper_pkg::Debug].w_data),
        .s_axi_wstrb(master[cva6_wrapper_pkg::Debug].w_strb),
        .s_axi_wlast(master[cva6_wrapper_pkg::Debug].w_last),
        .s_axi_wvalid(master[cva6_wrapper_pkg::Debug].w_valid),
        .s_axi_wready(master[cva6_wrapper_pkg::Debug].w_ready),
        .s_axi_bid(master[cva6_wrapper_pkg::Debug].b_id),
        .s_axi_bresp(master[cva6_wrapper_pkg::Debug].b_resp),
        .s_axi_bvalid(master[cva6_wrapper_pkg::Debug].b_valid),
        .s_axi_bready(master[cva6_wrapper_pkg::Debug].b_ready),
        .s_axi_arid(master[cva6_wrapper_pkg::Debug].ar_id),
        .s_axi_araddr(master[cva6_wrapper_pkg::Debug].ar_addr[31:0]),
        .s_axi_arlen(master[cva6_wrapper_pkg::Debug].ar_len),
        .s_axi_arsize(master[cva6_wrapper_pkg::Debug].ar_size),
        .s_axi_arburst(master[cva6_wrapper_pkg::Debug].ar_burst),
        .s_axi_arlock(master[cva6_wrapper_pkg::Debug].ar_lock),
        .s_axi_arcache(master[cva6_wrapper_pkg::Debug].ar_cache),
        .s_axi_arprot(master[cva6_wrapper_pkg::Debug].ar_prot),
        .s_axi_arregion(master[cva6_wrapper_pkg::Debug].ar_region),
        .s_axi_arqos(master[cva6_wrapper_pkg::Debug].ar_qos),
        .s_axi_arvalid(master[cva6_wrapper_pkg::Debug].ar_valid),
        .s_axi_arready(master[cva6_wrapper_pkg::Debug].ar_ready),
        .s_axi_rid(master[cva6_wrapper_pkg::Debug].r_id),
        .s_axi_rdata(master[cva6_wrapper_pkg::Debug].r_data),
        .s_axi_rresp(master[cva6_wrapper_pkg::Debug].r_resp),
        .s_axi_rlast(master[cva6_wrapper_pkg::Debug].r_last),
        .s_axi_rvalid(master[cva6_wrapper_pkg::Debug].r_valid),
        .s_axi_rready(master[cva6_wrapper_pkg::Debug].r_ready),
        .m_axi_awaddr(master_to_dm[0].aw_addr),
        .m_axi_awlen(master_to_dm[0].aw_len),
        .m_axi_awsize(master_to_dm[0].aw_size),
        .m_axi_awburst(master_to_dm[0].aw_burst),
        .m_axi_awlock(master_to_dm[0].aw_lock),
        .m_axi_awcache(master_to_dm[0].aw_cache),
        .m_axi_awprot(master_to_dm[0].aw_prot),
        .m_axi_awregion(master_to_dm[0].aw_region),
        .m_axi_awqos(master_to_dm[0].aw_qos),
        .m_axi_awvalid(master_to_dm[0].aw_valid),
        .m_axi_awready(master_to_dm[0].aw_ready),
        .m_axi_wdata(master_to_dm[0].w_data ),
        .m_axi_wstrb(master_to_dm[0].w_strb),
        .m_axi_wlast(master_to_dm[0].w_last),
        .m_axi_wvalid(master_to_dm[0].w_valid),
        .m_axi_wready(master_to_dm[0].w_ready),
        .m_axi_bresp(master_to_dm[0].b_resp),
        .m_axi_bvalid(master_to_dm[0].b_valid),
        .m_axi_bready(master_to_dm[0].b_ready),
        .m_axi_araddr(master_to_dm[0].ar_addr),
        .m_axi_arlen(master_to_dm[0].ar_len),
        .m_axi_arsize(master_to_dm[0].ar_size),
        .m_axi_arburst(master_to_dm[0].ar_burst),
        .m_axi_arlock(master_to_dm[0].ar_lock),
        .m_axi_arcache(master_to_dm[0].ar_cache),
        .m_axi_arprot(master_to_dm[0].ar_prot),
        .m_axi_arregion(master_to_dm[0].ar_region),
        .m_axi_arqos(master_to_dm[0].ar_qos),
        .m_axi_arvalid(master_to_dm[0].ar_valid),
        .m_axi_arready(master_to_dm[0].ar_ready),
        .m_axi_rdata(master_to_dm[0].r_data),
        .m_axi_rresp(master_to_dm[0].r_resp),
        .m_axi_rlast(master_to_dm[0].r_last),
        .m_axi_rvalid(master_to_dm[0].r_valid),
        .m_axi_rready(master_to_dm[0].r_ready)
    );

end else begin

    assign master[cva6_wrapper_pkg::Debug].aw_id = master_to_dm[0].aw_id;
    assign master[cva6_wrapper_pkg::Debug].aw_addr = master_to_dm[0].aw_addr;
    assign master[cva6_wrapper_pkg::Debug].aw_len = master_to_dm[0].aw_len;
    assign master[cva6_wrapper_pkg::Debug].aw_size = master_to_dm[0].aw_size;
    assign master[cva6_wrapper_pkg::Debug].aw_burst = master_to_dm[0].aw_burst;
    assign master[cva6_wrapper_pkg::Debug].aw_lock = master_to_dm[0].aw_lock;
    assign master[cva6_wrapper_pkg::Debug].aw_cache = master_to_dm[0].aw_cache;
    assign master[cva6_wrapper_pkg::Debug].aw_prot = master_to_dm[0].aw_prot;
    assign master[cva6_wrapper_pkg::Debug].aw_qos = master_to_dm[0].aw_qos;
    assign master[cva6_wrapper_pkg::Debug].aw_atop = master_to_dm[0].aw_atop;
    assign master[cva6_wrapper_pkg::Debug].aw_region = master_to_dm[0].aw_region;
    assign master[cva6_wrapper_pkg::Debug].aw_user = master_to_dm[0].aw_user;
    assign master[cva6_wrapper_pkg::Debug].aw_valid = master_to_dm[0].aw_valid;

    assign master_to_dm[0].aw_ready =master[cva6_wrapper_pkg::Debug].aw_ready;

    assign master[cva6_wrapper_pkg::Debug].w_data = master_to_dm[0].w_data;
    assign master[cva6_wrapper_pkg::Debug].w_strb = master_to_dm[0].w_strb;
    assign master[cva6_wrapper_pkg::Debug].w_last = master_to_dm[0].w_last;
    assign master[cva6_wrapper_pkg::Debug].w_user = master_to_dm[0].w_user;
    assign master[cva6_wrapper_pkg::Debug].w_valid = master_to_dm[0].w_valid;

    assign master_to_dm[0].w_ready =master[cva6_wrapper_pkg::Debug].w_ready;

    assign master_to_dm[0].b_id =master[cva6_wrapper_pkg::Debug].b_id;
    assign master_to_dm[0].b_resp =master[cva6_wrapper_pkg::Debug].b_resp;
    assign master_to_dm[0].b_user =master[cva6_wrapper_pkg::Debug].b_user;
    assign master_to_dm[0].b_valid =master[cva6_wrapper_pkg::Debug].b_valid;

    assign master[cva6_wrapper_pkg::Debug].b_ready = master_to_dm[0].b_ready;

    assign master[cva6_wrapper_pkg::Debug].ar_id = master_to_dm[0].ar_id;
    assign master[cva6_wrapper_pkg::Debug].ar_addr = master_to_dm[0].ar_addr;
    assign master[cva6_wrapper_pkg::Debug].ar_len = master_to_dm[0].ar_len;
    assign master[cva6_wrapper_pkg::Debug].ar_size = master_to_dm[0].ar_size;
    assign master[cva6_wrapper_pkg::Debug].ar_burst = master_to_dm[0].ar_burst;
    assign master[cva6_wrapper_pkg::Debug].ar_lock = master_to_dm[0].ar_lock;
    assign master[cva6_wrapper_pkg::Debug].ar_cache = master_to_dm[0].ar_cache;
    assign master[cva6_wrapper_pkg::Debug].ar_prot = master_to_dm[0].ar_prot;
    assign master[cva6_wrapper_pkg::Debug].ar_qos = master_to_dm[0].ar_qos;
    assign master[cva6_wrapper_pkg::Debug].ar_region = master_to_dm[0].ar_region;
    assign master[cva6_wrapper_pkg::Debug].ar_user = master_to_dm[0].ar_user;
    assign master[cva6_wrapper_pkg::Debug].ar_valid = master_to_dm[0].ar_valid;

    assign master_to_dm[0].ar_ready =master[cva6_wrapper_pkg::Debug].ar_ready;

    assign master_to_dm[0].r_id =master[cva6_wrapper_pkg::Debug].r_id;
    assign master_to_dm[0].r_data =master[cva6_wrapper_pkg::Debug].r_data;
    assign master_to_dm[0].r_resp =master[cva6_wrapper_pkg::Debug].r_resp;
    assign master_to_dm[0].r_last =master[cva6_wrapper_pkg::Debug].r_last;
    assign master_to_dm[0].r_user =master[cva6_wrapper_pkg::Debug].r_user;
    assign master_to_dm[0].r_valid =master[cva6_wrapper_pkg::Debug].r_valid;

    assign master[cva6_wrapper_pkg::Debug].r_ready = master_to_dm[0].r_ready;

end 

logic [1:0]    axi_adapter_size;

assign axi_adapter_size = (riscv::XLEN == 64) ? 2'b11 : 2'b10;


axi_adapter #(
    .DATA_WIDTH            ( riscv::XLEN      ),
    .AXI_DATA_WIDTH        ( AxiDataWidth     ),
    .AXI_ID_WIDTH          ( AxiIdWidthSlaves ),
    .axi_req_t             ( axi_slave_req_t  ),
    .axi_rsp_t             ( axi_slave_resp_t )
) i_dm_axi_master (
    .clk_i                 ( clk_i                     ),
    .rst_ni                ( rst_n                     ),
    .req_i                 ( dm_master_req             ),
    .type_i                ( ariane_axi::SINGLE_REQ    ),
    .amo_i                 ( ariane_pkg::AMO_NONE      ),
    .gnt_o                 ( dm_master_gnt             ),
    .addr_i                ( dm_master_add             ),
    .we_i                  ( dm_master_we              ),
    .wdata_i               ( dm_master_wdata           ),
    .be_i                  ( dm_master_be              ),
    .size_i                ( axi_adapter_size          ),
    .id_i                  ( '0                        ),
    .valid_o               ( dm_master_r_valid         ),
    .rdata_o               ( dm_master_r_rdata         ),
    .id_o                  (                           ),
    .critical_word_o       (                           ),
    .critical_word_valid_o (                           ),
    .axi_req_o             ( dm_axi_m_req              ),
    .axi_resp_i            ( dm_axi_m_resp             )
);

if (riscv::XLEN==32 ) begin
    logic [31 : 0] dm_master_m_awaddr;
    logic [31 : 0] dm_master_m_araddr;

    assign slave[1].aw_addr = {32'h0000_0000, dm_master_m_awaddr};
    assign slave[1].ar_addr = {32'h0000_0000, dm_master_m_araddr};

    logic [31 : 0] dm_master_s_rdata;

    assign dm_axi_m_resp.r.data = {32'h0000_0000, dm_master_s_rdata}; 

    assign slave[1].aw_user = '0;
    assign slave[1].w_user = '0;
    assign slave[1].ar_user = '0;

    assign slave[1].aw_id = dm_axi_m_req.aw.id;
    assign slave[1].ar_id = dm_axi_m_req.ar.id;
    assign slave[1].aw_atop = dm_axi_m_req.aw.atop;

    xlnx_axi_dwidth_converter_dm_master  i_axi_dwidth_converter_dm_master( 
        .s_axi_aclk(clk_i),
        .s_axi_aresetn(ndmreset_n),
        .s_axi_awid(dm_axi_m_req.aw.id),
        .s_axi_awaddr(dm_axi_m_req.aw.addr[31:0]),
        .s_axi_awlen(dm_axi_m_req.aw.len),
        .s_axi_awsize(dm_axi_m_req.aw.size),
        .s_axi_awburst(dm_axi_m_req.aw.burst),
        .s_axi_awlock(dm_axi_m_req.aw.lock),
        .s_axi_awcache(dm_axi_m_req.aw.cache),
        .s_axi_awprot(dm_axi_m_req.aw.prot),
        .s_axi_awregion(dm_axi_m_req.aw.region),
        .s_axi_awqos(dm_axi_m_req.aw.qos),
        .s_axi_awvalid(dm_axi_m_req.aw_valid),
        .s_axi_awready(dm_axi_m_resp.aw_ready),
        .s_axi_wdata(dm_axi_m_req.w.data[31:0]),
        .s_axi_wstrb(dm_axi_m_req.w.strb[3:0]),
        .s_axi_wlast(dm_axi_m_req.w.last),
        .s_axi_wvalid(dm_axi_m_req.w_valid),
        .s_axi_wready(dm_axi_m_resp.w_ready),
        .s_axi_bid(dm_axi_m_resp.b.id),
        .s_axi_bresp(dm_axi_m_resp.b.resp),
        .s_axi_bvalid(dm_axi_m_resp.b_valid),
        .s_axi_bready(dm_axi_m_req.b_ready),
        .s_axi_arid(dm_axi_m_req.ar.id),
        .s_axi_araddr(dm_axi_m_req.ar.addr[31:0]),
        .s_axi_arlen(dm_axi_m_req.ar.len),
        .s_axi_arsize(dm_axi_m_req.ar.size),
        .s_axi_arburst(dm_axi_m_req.ar.burst),
        .s_axi_arlock(dm_axi_m_req.ar.lock),
        .s_axi_arcache(dm_axi_m_req.ar.cache),
        .s_axi_arprot(dm_axi_m_req.ar.prot),
        .s_axi_arregion(dm_axi_m_req.ar.region),
        .s_axi_arqos(dm_axi_m_req.ar.qos),
        .s_axi_arvalid(dm_axi_m_req.ar_valid),
        .s_axi_arready(dm_axi_m_resp.ar_ready),
        .s_axi_rid(dm_axi_m_resp.r.id),
        .s_axi_rdata(dm_master_s_rdata),
        .s_axi_rresp(dm_axi_m_resp.r.resp),
        .s_axi_rlast(dm_axi_m_resp.r.last),
        .s_axi_rvalid(dm_axi_m_resp.r_valid),
        .s_axi_rready(dm_axi_m_req.r_ready),
        .m_axi_awaddr(dm_master_m_awaddr),
        .m_axi_awlen(slave[1].aw_len),
        .m_axi_awsize(slave[1].aw_size),
        .m_axi_awburst(slave[1].aw_burst),
        .m_axi_awlock(slave[1].aw_lock),
        .m_axi_awcache(slave[1].aw_cache),
        .m_axi_awprot(slave[1].aw_prot),
        .m_axi_awregion(slave[1].aw_region),
        .m_axi_awqos(slave[1].aw_qos),
        .m_axi_awvalid(slave[1].aw_valid),
        .m_axi_awready(slave[1].aw_ready),
        .m_axi_wdata(slave[1].w_data ),
        .m_axi_wstrb(slave[1].w_strb),
        .m_axi_wlast(slave[1].w_last),
        .m_axi_wvalid(slave[1].w_valid),
        .m_axi_wready(slave[1].w_ready),
        .m_axi_bresp(slave[1].b_resp),
        .m_axi_bvalid(slave[1].b_valid),
        .m_axi_bready(slave[1].b_ready),
        .m_axi_araddr(dm_master_m_araddr),
        .m_axi_arlen(slave[1].ar_len),
        .m_axi_arsize(slave[1].ar_size),
        .m_axi_arburst(slave[1].ar_burst),
        .m_axi_arlock(slave[1].ar_lock),
        .m_axi_arcache(slave[1].ar_cache),
        .m_axi_arprot(slave[1].ar_prot),
        .m_axi_arregion(slave[1].ar_region),
        .m_axi_arqos(slave[1].ar_qos),
        .m_axi_arvalid(slave[1].ar_valid),
        .m_axi_arready(slave[1].ar_ready),
        .m_axi_rdata(slave[1].r_data),
        .m_axi_rresp(slave[1].r_resp),
        .m_axi_rlast(slave[1].r_last),
        .m_axi_rvalid(slave[1].r_valid),
        .m_axi_rready(slave[1].r_ready)
      );
end else begin
    `AXI_ASSIGN_FROM_REQ(slave[1], dm_axi_m_req)
    `AXI_ASSIGN_TO_RESP(dm_axi_m_resp, slave[1])
end


// ---------------
// Core
// ---------------
ariane_axi::req_t    axi_ariane_req;
ariane_axi::resp_t   axi_ariane_resp;

ariane #(
    .ArianeCfg ( cva6_wrapper_pkg::CVA6Cfg )
) i_ariane (
    .clk_i        ( clk_i               ),
    .rst_ni       ( rst_n /*ndmreset_n*/          ),
    .boot_addr_i  ( cva6_wrapper_pkg::ExternalBase ),
    .hart_id_i    ( '0                  ),
    .irq_i        ( irq                 ),
    .ipi_i        ( ipi                 ),
    .time_irq_i   ( timer_irq           ),
    .debug_req_i  ( debug_req_irq       ),
    .axi_req_o    ( axi_ariane_req      ),
    .axi_resp_i   ( axi_ariane_resp     )
);

`AXI_ASSIGN_FROM_REQ(slave[0], axi_ariane_req)
`AXI_ASSIGN_TO_RESP(axi_ariane_resp, slave[0])

// ---------------
// CLINT
// ---------------
// divide clock by two
always_ff @(posedge clk_i or negedge ndmreset_n) begin
  if (~ndmreset_n) begin
    rtc <= 0;
  end else begin
    rtc <= rtc ^ 1'b1;
  end
end

axi_slave_req_t  axi_clint_req;
axi_slave_resp_t axi_clint_resp;

clint #(
    .AXI_ADDR_WIDTH ( AxiAddrWidth     ),
    .AXI_DATA_WIDTH ( AxiDataWidth     ),
    .AXI_ID_WIDTH   ( AxiIdWidthSlaves ),
    .NR_CORES       ( 1                ),
    .axi_req_t      ( axi_slave_req_t  ),
    .axi_resp_t     ( axi_slave_resp_t )
) i_clint (
    .clk_i       ( clk_i          ),
    .rst_ni      ( ndmreset_n     ),
    .testmode_i  ( test_en        ),
    .axi_req_i   ( axi_clint_req  ),
    .axi_resp_o  ( axi_clint_resp ),
    .rtc_i       ( rtc            ),
    .timer_irq_o ( timer_irq      ),
    .ipi_o       ( ipi            )
);

`AXI_ASSIGN_TO_REQ(axi_clint_req, master[cva6_wrapper_pkg::CLINT])
`AXI_ASSIGN_FROM_RESP(master[cva6_wrapper_pkg::CLINT], axi_clint_resp)

    // ---------------
    // PLIC
    // ---------------

    REG_BUS #(
        .ADDR_WIDTH ( 32 ),
        .DATA_WIDTH ( 32 )
    ) reg_bus (clk_i);

    logic         plic_penable;
    logic         plic_pwrite;
    logic [31:0]  plic_paddr;
    logic         plic_psel;
    logic [31:0]  plic_pwdata;
    logic [31:0]  plic_prdata;
    logic         plic_pready;
    logic         plic_pslverr;

    axi2apb_64_32 #(
        .AXI4_ADDRESS_WIDTH ( AxiAddrWidth  ),
        .AXI4_RDATA_WIDTH   ( AxiDataWidth  ),
        .AXI4_WDATA_WIDTH   ( AxiDataWidth  ),
        .AXI4_ID_WIDTH      ( AxiIdWidthSlaves    ),
        .AXI4_USER_WIDTH    ( AxiUserWidth  ),
        .BUFF_DEPTH_SLAVE   ( 2             ),
        .APB_ADDR_WIDTH     ( 32            )
    ) i_axi2apb_64_32_plic (
        .ACLK      ( clk_i          ),
        .ARESETn   ( ndmreset_n         ),
        .test_en_i ( 1'b0           ),
        .AWID_i    ( master[cva6_wrapper_pkg::PLIC].aw_id     ),
        .AWADDR_i  ( master[cva6_wrapper_pkg::PLIC].aw_addr   ),
        .AWLEN_i   ( master[cva6_wrapper_pkg::PLIC].aw_len    ),
        .AWSIZE_i  ( master[cva6_wrapper_pkg::PLIC].aw_size   ),
        .AWBURST_i ( master[cva6_wrapper_pkg::PLIC].aw_burst  ),
        .AWLOCK_i  ( master[cva6_wrapper_pkg::PLIC].aw_lock   ),
        .AWCACHE_i ( master[cva6_wrapper_pkg::PLIC].aw_cache  ),
        .AWPROT_i  ( master[cva6_wrapper_pkg::PLIC].aw_prot   ),
        .AWREGION_i( master[cva6_wrapper_pkg::PLIC].aw_region ),
        .AWUSER_i  ( master[cva6_wrapper_pkg::PLIC].aw_user   ),
        .AWQOS_i   ( master[cva6_wrapper_pkg::PLIC].aw_qos    ),
        .AWVALID_i ( master[cva6_wrapper_pkg::PLIC].aw_valid  ),
        .AWREADY_o ( master[cva6_wrapper_pkg::PLIC].aw_ready  ),
        .WDATA_i   ( master[cva6_wrapper_pkg::PLIC].w_data    ),
        .WSTRB_i   ( master[cva6_wrapper_pkg::PLIC].w_strb    ),
        .WLAST_i   ( master[cva6_wrapper_pkg::PLIC].w_last    ),
        .WUSER_i   ( master[cva6_wrapper_pkg::PLIC].w_user    ),
        .WVALID_i  ( master[cva6_wrapper_pkg::PLIC].w_valid   ),
        .WREADY_o  ( master[cva6_wrapper_pkg::PLIC].w_ready   ),
        .BID_o     ( master[cva6_wrapper_pkg::PLIC].b_id      ),
        .BRESP_o   ( master[cva6_wrapper_pkg::PLIC].b_resp    ),
        .BVALID_o  ( master[cva6_wrapper_pkg::PLIC].b_valid   ),
        .BUSER_o   ( master[cva6_wrapper_pkg::PLIC].b_user    ),
        .BREADY_i  ( master[cva6_wrapper_pkg::PLIC].b_ready   ),
        .ARID_i    ( master[cva6_wrapper_pkg::PLIC].ar_id     ),
        .ARADDR_i  ( master[cva6_wrapper_pkg::PLIC].ar_addr   ),
        .ARLEN_i   ( master[cva6_wrapper_pkg::PLIC].ar_len    ),
        .ARSIZE_i  ( master[cva6_wrapper_pkg::PLIC].ar_size   ),
        .ARBURST_i ( master[cva6_wrapper_pkg::PLIC].ar_burst  ),
        .ARLOCK_i  ( master[cva6_wrapper_pkg::PLIC].ar_lock   ),
        .ARCACHE_i ( master[cva6_wrapper_pkg::PLIC].ar_cache  ),
        .ARPROT_i  ( master[cva6_wrapper_pkg::PLIC].ar_prot   ),
        .ARREGION_i( master[cva6_wrapper_pkg::PLIC].ar_region ),
        .ARUSER_i  ( master[cva6_wrapper_pkg::PLIC].ar_user   ),
        .ARQOS_i   ( master[cva6_wrapper_pkg::PLIC].ar_qos    ),
        .ARVALID_i ( master[cva6_wrapper_pkg::PLIC].ar_valid  ),
        .ARREADY_o ( master[cva6_wrapper_pkg::PLIC].ar_ready  ),
        .RID_o     ( master[cva6_wrapper_pkg::PLIC].r_id      ),
        .RDATA_o   ( master[cva6_wrapper_pkg::PLIC].r_data    ),
        .RRESP_o   ( master[cva6_wrapper_pkg::PLIC].r_resp    ),
        .RLAST_o   ( master[cva6_wrapper_pkg::PLIC].r_last    ),
        .RUSER_o   ( master[cva6_wrapper_pkg::PLIC].r_user    ),
        .RVALID_o  ( master[cva6_wrapper_pkg::PLIC].r_valid   ),
        .RREADY_i  ( master[cva6_wrapper_pkg::PLIC].r_ready   ),
        .PENABLE   ( plic_penable   ),
        .PWRITE    ( plic_pwrite    ),
        .PADDR     ( plic_paddr     ),
        .PSEL      ( plic_psel      ),
        .PWDATA    ( plic_pwdata    ),
        .PRDATA    ( plic_prdata    ),
        .PREADY    ( plic_pready    ),
        .PSLVERR   ( plic_pslverr   )
    );

    apb_to_reg i_apb_to_reg (
        .clk_i     ( clk_i        ),
        .rst_ni    ( ndmreset_n   ),
        .penable_i ( plic_penable ),
        .pwrite_i  ( plic_pwrite  ),
        .paddr_i   ( plic_paddr   ),
        .psel_i    ( plic_psel    ),
        .pwdata_i  ( plic_pwdata  ),
        .prdata_o  ( plic_prdata  ),
        .pready_o  ( plic_pready  ),
        .pslverr_o ( plic_pslverr ),
        .reg_o     ( reg_bus      )
    );

    // define reg type according to REG_BUS above
    `REG_BUS_TYPEDEF_ALL(plic, logic[31:0], logic[31:0], logic[3:0])
    plic_req_t plic_req;
    plic_rsp_t plic_rsp;

    // assign REG_BUS.out to (req_t, rsp_t) pair
    `REG_BUS_ASSIGN_TO_REQ(plic_req, reg_bus)
    `REG_BUS_ASSIGN_FROM_RSP(reg_bus, plic_rsp)

    plic_top #(
      .N_SOURCE    ( cva6_wrapper_pkg::NumSources  ),
      .N_TARGET    ( cva6_wrapper_pkg::NumTargets  ),
      .MAX_PRIO    ( cva6_wrapper_pkg::MaxPriority ),
      .reg_req_t   ( plic_req_t              ),
      .reg_rsp_t   ( plic_rsp_t              )
    ) i_plic (
      .clk_i,
      .rst_ni (ndmreset_n),
      .req_i         ( plic_req    ),
      .resp_o        ( plic_rsp   ),
      .le_i          ( '0          ), // 0:level 1:edge
      .irq_sources_i ( irq_sources ),
      .eip_targets_o ( irq       )
    );

// ---------------
// AXI to the outside world
// ---------------

    assign AWID_o     = master[cva6_wrapper_pkg::External].aw_id;
    assign AWADDR_o   = master[cva6_wrapper_pkg::External].aw_addr;
    assign AWLEN_o    = master[cva6_wrapper_pkg::External].aw_len;
    assign AWSIZE_o   = master[cva6_wrapper_pkg::External].aw_size;
    assign AWBURST_o  = master[cva6_wrapper_pkg::External].aw_burst;
    assign AWLOCK_o   = master[cva6_wrapper_pkg::External].aw_lock;
    assign AWCACHE_o  = master[cva6_wrapper_pkg::External].aw_cache;
    assign AWPROT_o   = master[cva6_wrapper_pkg::External].aw_prot;
    assign AWREGION_o = master[cva6_wrapper_pkg::External].aw_region;
    assign AWUSER_o   = '0;
    assign AWQOS_o    = master[cva6_wrapper_pkg::External].aw_qos;
    assign AWVALID_o  = master[cva6_wrapper_pkg::External].aw_valid;
    assign master[cva6_wrapper_pkg::External].aw_ready = AWREADY_i;
    assign WDATA_o    = master[cva6_wrapper_pkg::External].w_data;
    assign WSTRB_o    = master[cva6_wrapper_pkg::External].w_strb;
    assign WLAST_o    = master[cva6_wrapper_pkg::External].w_last;
    assign WUSER_o    = '0;
    assign WVALID_o   = master[cva6_wrapper_pkg::External].w_valid;
    assign master[cva6_wrapper_pkg::External].w_ready = WREADY_i;
    assign master[cva6_wrapper_pkg::External].b_id = BID_i;
    assign master[cva6_wrapper_pkg::External].b_resp = BRESP_i;
    assign master[cva6_wrapper_pkg::External].b_valid = BVALID_i;
    assign BREADY_o   = master[cva6_wrapper_pkg::External].b_ready;
    assign ARID_o     = master[cva6_wrapper_pkg::External].ar_id;
    assign ARADDR_o   = master[cva6_wrapper_pkg::External].ar_addr;
    assign ARLEN_o    = master[cva6_wrapper_pkg::External].ar_len;
    assign ARSIZE_o   = master[cva6_wrapper_pkg::External].ar_size;
    assign ARBURST_o  = master[cva6_wrapper_pkg::External].ar_burst;
    assign ARLOCK_o   = master[cva6_wrapper_pkg::External].ar_lock;
    assign ARCACHE_o  = master[cva6_wrapper_pkg::External].ar_cache;
    assign ARPROT_o   = master[cva6_wrapper_pkg::External].ar_prot;
    assign ARREGION_o = master[cva6_wrapper_pkg::External].ar_region;
    assign ARUSER_o   = '0;
    assign ARQOS_o    = master[cva6_wrapper_pkg::External].ar_qos;
    assign ARVALID_o  = master[cva6_wrapper_pkg::External].ar_valid;
    assign master[cva6_wrapper_pkg::External].ar_ready = ARREADY_i;
    assign master[cva6_wrapper_pkg::External].r_id = RID_i;
    assign master[cva6_wrapper_pkg::External].r_data = RDATA_i;
    assign master[cva6_wrapper_pkg::External].r_resp = RRESP_i;
    assign master[cva6_wrapper_pkg::External].r_last = RLAST_i;
    assign master[cva6_wrapper_pkg::External].r_valid = RVALID_i;
    assign RREADY_o   = master[cva6_wrapper_pkg::External].r_ready;

endmodule
