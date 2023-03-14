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

`AXI_TYPEDEF_ALL(axi_dm_slave,
                 logic [    AxiAddrWidth-1:0],
                 logic [AxiIdWidthSlaves-1:0],
                 logic [    riscv::XLEN-1:0],
                 logic [(riscv::XLEN/8)-1:0],
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

always @(posedge clk_i)
    ndmreset_n <= ~ndmreset && rst_n;

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
  NoAddrRules:        NBMaster
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

    axi_dw_converter_intf #(
        .AXI_MAX_READS          (1                    ),
        .AXI_ADDR_WIDTH         (64                   ),
        .AXI_ID_WIDTH           (AxiIdWidthSlaves     ),
        .AXI_SLV_PORT_DATA_WIDTH(64                   ),
        .AXI_MST_PORT_DATA_WIDTH(32                   ),
        .AXI_USER_WIDTH         (AxiUserWidth         )
    ) i_dw_converter (
        .clk_i (clk_i),
        .rst_ni(ndmreset_n),
        .slv   (master[cva6_wrapper_pkg::Debug]),
        .mst   (master_to_dm[0])
    );

end else begin

    assign master_to_dm[0].aw_id = master[cva6_wrapper_pkg::Debug].aw_id;
    assign master_to_dm[0].aw_addr = master[cva6_wrapper_pkg::Debug].aw_addr;
    assign master_to_dm[0].aw_len = master[cva6_wrapper_pkg::Debug].aw_len;
    assign master_to_dm[0].aw_size = master[cva6_wrapper_pkg::Debug].aw_size;
    assign master_to_dm[0].aw_burst = master[cva6_wrapper_pkg::Debug].aw_burst;
    assign master_to_dm[0].aw_lock = master[cva6_wrapper_pkg::Debug].aw_lock;
    assign master_to_dm[0].aw_cache = master[cva6_wrapper_pkg::Debug].aw_cache;
    assign master_to_dm[0].aw_prot = master[cva6_wrapper_pkg::Debug].aw_prot;
    assign master_to_dm[0].aw_qos = master[cva6_wrapper_pkg::Debug].aw_qos;
    assign master_to_dm[0].aw_atop = master[cva6_wrapper_pkg::Debug].aw_atop;
    assign master_to_dm[0].aw_region = master[cva6_wrapper_pkg::Debug].aw_region;
    assign master_to_dm[0].aw_user = master[cva6_wrapper_pkg::Debug].aw_user;
    assign master_to_dm[0].aw_valid = master[cva6_wrapper_pkg::Debug].aw_valid;

    assign master[cva6_wrapper_pkg::Debug].aw_ready = master_to_dm[0].aw_ready;

    assign master_to_dm[0].w_data = master[cva6_wrapper_pkg::Debug].w_data;
    assign master_to_dm[0].w_strb = master[cva6_wrapper_pkg::Debug].w_strb;
    assign master_to_dm[0].w_last = master[cva6_wrapper_pkg::Debug].w_last;
    assign master_to_dm[0].w_user = master[cva6_wrapper_pkg::Debug].w_user;
    assign master_to_dm[0].w_valid = master[cva6_wrapper_pkg::Debug].w_valid;

    assign master[cva6_wrapper_pkg::Debug].w_ready = master_to_dm[0].w_ready;

    assign master[cva6_wrapper_pkg::Debug].b_id = master_to_dm[0].b_id;
    assign master[cva6_wrapper_pkg::Debug].b_resp = master_to_dm[0].b_resp;
    assign master[cva6_wrapper_pkg::Debug].b_user = master_to_dm[0].b_user;
    assign master[cva6_wrapper_pkg::Debug].b_valid = master_to_dm[0].b_valid;

    assign master_to_dm[0].b_ready = master[cva6_wrapper_pkg::Debug].b_ready;

    assign master_to_dm[0].ar_id = master[cva6_wrapper_pkg::Debug].ar_id;
    assign master_to_dm[0].ar_addr = master[cva6_wrapper_pkg::Debug].ar_addr;
    assign master_to_dm[0].ar_len = master[cva6_wrapper_pkg::Debug].ar_len;
    assign master_to_dm[0].ar_size = master[cva6_wrapper_pkg::Debug].ar_size;
    assign master_to_dm[0].ar_burst = master[cva6_wrapper_pkg::Debug].ar_burst;
    assign master_to_dm[0].ar_lock = master[cva6_wrapper_pkg::Debug].ar_lock;
    assign master_to_dm[0].ar_cache = master[cva6_wrapper_pkg::Debug].ar_cache;
    assign master_to_dm[0].ar_prot = master[cva6_wrapper_pkg::Debug].ar_prot;
    assign master_to_dm[0].ar_qos = master[cva6_wrapper_pkg::Debug].ar_qos;
    assign master_to_dm[0].ar_region = master[cva6_wrapper_pkg::Debug].ar_region;
    assign master_to_dm[0].ar_user = master[cva6_wrapper_pkg::Debug].ar_user;
    assign master_to_dm[0].ar_valid = master[cva6_wrapper_pkg::Debug].ar_valid;

    assign master[cva6_wrapper_pkg::Debug].ar_ready = master_to_dm[0].ar_ready;

    assign master[cva6_wrapper_pkg::Debug].r_id = master_to_dm[0].r_id;
    assign master[cva6_wrapper_pkg::Debug].r_data = master_to_dm[0].r_data;
    assign master[cva6_wrapper_pkg::Debug].r_resp = master_to_dm[0].r_resp;
    assign master[cva6_wrapper_pkg::Debug].r_last = master_to_dm[0].r_last;
    assign master[cva6_wrapper_pkg::Debug].r_user = master_to_dm[0].r_user;
    assign master[cva6_wrapper_pkg::Debug].r_valid = master_to_dm[0].r_valid;

    assign master_to_dm[0].r_ready = master[cva6_wrapper_pkg::Debug].r_ready;

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

`AXI_ASSIGN_FROM_REQ(slave[1], dm_axi_m_req)
`AXI_ASSIGN_TO_RESP(dm_axi_m_resp, slave[1])

// ---------------
// Core
// ---------------
ariane_axi::req_t    axi_ariane_req;
ariane_axi::resp_t   axi_ariane_resp;

ariane #(
    .ArianeCfg ( cva6_wrapper_pkg::CVA6Cfg )
) i_ariane (
    .clk_i        ( clk_i               ),
    .rst_ni       ( ndmreset_n          ),
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
