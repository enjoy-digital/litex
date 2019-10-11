/**
  *
  * ExampleBlackParrotSystem For Simulating With Litex
  *
  */
  
`include "bsg_noc_links.vh"

module ExampleBlackParrotSystem
 import bp_common_pkg::*;
 import bp_common_aviary_pkg::*;
 import bp_be_pkg::*;
 import bp_common_rv64_pkg::*;
 import bp_cce_pkg::*;
 import bp_cfg_link_pkg::*;
 #(parameter bp_cfg_e cfg_p = e_bp_single_core_cfg // Replaced by the flow with a specific bp_cfg
   `declare_bp_proc_params(cfg_p)
   `declare_bp_me_if_widths(paddr_width_p, cce_block_width_p, num_lce_p, lce_assoc_p)

   // Tracing parameters
   , parameter calc_trace_p                = 1
   , parameter cce_trace_p                 = 0
   , parameter cmt_trace_p                 = 0
   , parameter dram_trace_p                = 0
   , parameter skip_init_p                 = 0

   , parameter mem_load_p         = 1
   , parameter mem_file_p         = "prog.mem"
   , parameter mem_cap_in_bytes_p = 2**20
   , parameter [paddr_width_p-1:0] mem_offset_p = paddr_width_p'(32'h8000_0000)

   )
  (input clk_i
   , input reset_i
   //Wishbone interface 
   , input  [63:0]  wbm_dat_i
   , output [63:0]  wbm_dat_o
   , input          wbm_ack_i
  // , input          wbm_err_i
  // , input          wbm_rty_i
   , output [36:0]  wbm_adr_o //TODO parametrize this
   , output         wbm_stb_o
   , output         wbm_cyc_o
   , output         wbm_sel_o //TODO: how many bits ? check 3.5 table 3-1
   , output         wbm_we_o
   , output [2:0]   wbm_cti_o //TODO: hardwire in Litex
   , output [1:0]   wbm_bte_o //TODO: hardwire in Litex
   , output         all_finished_debug_o //SC_add
   , output         core_passed_debug
   , output         core_failed_debug
   , input  [3:0]   interrupts 
  );

`declare_bsg_ready_and_link_sif_s(mem_noc_flit_width_p, bsg_ready_and_link_sif_s);
`declare_bp_me_if(paddr_width_p, cce_block_width_p, num_lce_p, lce_assoc_p)

bsg_ready_and_link_sif_s cmd_link_li, cmd_link_lo;
bsg_ready_and_link_sif_s resp_link_li, resp_link_lo;

bsg_ready_and_link_sif_s mem_cmd_link_li, mem_cmd_link_lo, mem_resp_link_li, mem_resp_link_lo;
bsg_ready_and_link_sif_s cfg_cmd_link_li, cfg_cmd_link_lo, cfg_resp_link_li, cfg_resp_link_lo;

assign mem_cmd_link_li = cmd_link_li;
assign cfg_cmd_link_li = '{ready_and_rev: cmd_link_li.ready_and_rev, default: '0};
assign cmd_link_lo = '{data: cfg_cmd_link_lo.data
                       ,v  : cfg_cmd_link_lo.v
                       ,ready_and_rev: mem_cmd_link_lo.ready_and_rev
                       };

assign mem_resp_link_li = '{ready_and_rev: resp_link_li.ready_and_rev, default: '0};
assign cfg_resp_link_li = resp_link_li;
assign resp_link_lo = '{data: mem_resp_link_lo.data
                        ,v  : mem_resp_link_lo.v
                        ,ready_and_rev: cfg_resp_link_lo.ready_and_rev
                        };

bp_cce_mem_msg_s       mem_resp_li;
logic                  mem_resp_v_li, mem_resp_ready_lo;
bp_cce_mem_msg_s       mem_cmd_lo;
logic                  mem_cmd_v_lo, mem_cmd_yumi_li;

bp_cce_mem_msg_s       dram_resp_lo;
logic                  dram_resp_v_lo, dram_resp_ready_li;
bp_cce_mem_msg_s       dram_cmd_li;
logic                  dram_cmd_v_li, dram_cmd_yumi_lo;

bp_cce_mem_msg_s       host_resp_lo;
logic                  host_resp_v_lo, host_resp_ready_li;
bp_cce_mem_msg_s       host_cmd_li;
logic                  host_cmd_v_li, host_cmd_yumi_lo;

bp_cce_mem_msg_s       cfg_cmd_lo;
logic                  cfg_cmd_v_lo, cfg_cmd_ready_li;
bp_cce_mem_msg_s       cfg_resp_li;
logic                  cfg_resp_v_li, cfg_resp_ready_lo;

logic [mem_noc_cord_width_p-1:0] dram_cord_lo, mmio_cord_lo, host_cord_lo;
logic [num_core_p-1:0][mem_noc_cord_width_p-1:0] tile_cord_lo;
logic [num_mem_p-1:0][mem_noc_cord_width_p-1:0] mem_cord_lo;

assign mmio_cord_lo[0+:mem_noc_x_cord_width_p]                      = mmio_x_pos_p;
assign mmio_cord_lo[mem_noc_x_cord_width_p+:mem_noc_y_cord_width_p] = '0;
assign dram_cord_lo[0+:mem_noc_x_cord_width_p]                      = mem_noc_x_dim_p+2;
assign dram_cord_lo[mem_noc_x_cord_width_p+:mem_noc_y_cord_width_p] = '0;
assign host_cord_lo[0+:mem_noc_x_cord_width_p]                      = mem_noc_x_dim_p+2;
assign host_cord_lo[mem_noc_x_cord_width_p+:mem_noc_y_cord_width_p] = '0;

for (genvar j = 0; j < mem_noc_y_dim_p; j++)
  begin : y
    for (genvar i = 0; i < mem_noc_x_dim_p; i++)
      begin : x
        localparam idx = j*mem_noc_x_dim_p + i;
        assign tile_cord_lo[idx][0+:mem_noc_x_cord_width_p] = i+1;
        assign tile_cord_lo[idx][mem_noc_x_cord_width_p+:mem_noc_y_cord_width_p] = j+1;
      end
  end
for (genvar i = 0; i < num_mem_p; i++)
  begin : x
    assign mem_cord_lo[i][0+:mem_noc_x_cord_width_p] = i;
    assign mem_cord_lo[i][mem_noc_x_cord_width_p+:mem_noc_y_cord_width_p] = '0;
  end

// Chip
bp_chip
 #(.cfg_p(cfg_p))
 chip
  (.core_clk_i(clk_i)
   ,.core_reset_i(reset_i)
   
   ,.coh_clk_i(clk_i)
   ,.coh_reset_i(reset_i)

   ,.mem_clk_i(clk_i)
   ,.mem_reset_i(reset_i)

   ,.mem_cord_i(mem_cord_lo)
   ,.tile_cord_i(tile_cord_lo)
   ,.dram_cord_i(dram_cord_lo)
   ,.mmio_cord_i(mmio_cord_lo)
   ,.host_cord_i(host_cord_lo)

   ,.prev_cmd_link_i('0)
   ,.prev_cmd_link_o()

   ,.prev_resp_link_i('0)
   ,.prev_resp_link_o()

   ,.next_cmd_link_i(cmd_link_lo)
   ,.next_cmd_link_o(cmd_link_li)

   ,.next_resp_link_i(resp_link_lo)
   ,.next_resp_link_o(resp_link_li)
   );

  bind bp_be_top
    bp_nonsynth_commit_tracer
     #(.cfg_p(cfg_p))
     commit_tracer
      (.clk_i(clk_i & (ExampleBlackParrotSystem.cmt_trace_p == 1))
       ,.reset_i(reset_i)

       ,.mhartid_i('0)

       ,.commit_v_i(be_calculator.instret_mem3_o)
       ,.commit_pc_i(be_calculator.pc_mem3_o)
       ,.commit_instr_i(be_calculator.instr_mem3_o)

       ,.rd_w_v_i(be_calculator.int_regfile.rd_w_v_i)
       ,.rd_addr_i(be_calculator.int_regfile.rd_addr_i)
       ,.rd_data_i(be_calculator.int_regfile.rd_data_i)
       );


  bind bp_be_top
    bp_be_nonsynth_tracer
     #(.cfg_p(cfg_p))
     tracer
       // Workaround for verilator binding by accident
       // TODO: Figure out why tracing is always enabled
      (.clk_i(clk_i & (ExampleBlackParrotSystem.calc_trace_p == 1))
       ,.reset_i(reset_i)
  
       ,.mhartid_i(be_calculator.proc_cfg.core_id)

       ,.issue_pkt_i(be_calculator.issue_pkt)
       ,.issue_pkt_v_i(be_calculator.issue_pkt_v_i)
  
       ,.fe_nop_v_i(be_calculator.fe_nop_v)
       ,.be_nop_v_i(be_calculator.be_nop_v)
       ,.me_nop_v_i(be_calculator.me_nop_v)
       ,.dispatch_pkt_i(be_calculator.dispatch_pkt)
  
       ,.ex1_br_tgt_i(be_calculator.calc_status.int1_br_tgt)
       ,.ex1_btaken_i(be_calculator.calc_status.int1_btaken)
       ,.iwb_result_i(be_calculator.comp_stage_n[3])
       ,.fwb_result_i(be_calculator.comp_stage_n[4])
  
       ,.cmt_trace_exc_i(be_calculator.exc_stage_n[1+:5])
  
       ,.trap_v_i(be_mem.csr.trap_v_o)
       ,.mtvec_i(be_mem.csr.mtvec_n)
       ,.mtval_i(be_mem.csr.mtval_n[0+:vaddr_width_p])
       ,.ret_v_i(be_mem.csr.ret_v_o)
       ,.mepc_i(be_mem.csr.mepc_n[0+:vaddr_width_p])
       ,.mcause_i(be_mem.csr.mcause_n)
  
       ,.priv_mode_i(be_mem.csr.priv_mode_n)
       ,.mpp_i(be_mem.csr.mstatus_n.mpp)
       );

/*bind bp_be_top
  bp_be_nonsynth_perf
   #(.cfg_p(cfg_p))
   perf
    (.clk_i(clk_i)
     ,.reset_i(reset_i)

     ,.mhartid_i(be_calculator.proc_cfg.core_id)

     ,.fe_nop_i(be_calculator.exc_stage_r[2].fe_nop_v)
     ,.be_nop_i(be_calculator.exc_stage_r[2].be_nop_v)
     ,.me_nop_i(be_calculator.exc_stage_r[2].me_nop_v)
     ,.poison_i(be_calculator.exc_stage_r[2].poison_v)
     ,.roll_i(be_calculator.exc_stage_r[2].roll_v)
     ,.instr_cmt_i(be_calculator.calc_status.mem3_cmt_v)

     ,.program_finish_i(testbench.program_finish)
     );
*/
/*if (dram_trace_p)
  bp_mem_nonsynth_tracer
   #(.cfg_p(cfg_p))
   bp_mem_tracer
    (.clk_i(clk_i & (testbench.dram_trace_p == 1))
     ,.reset_i(reset_i)

     ,.mem_cmd_i(dram_cmd_li)
     ,.mem_cmd_v_i(dram_cmd_v_li)
     ,.mem_cmd_yumi_i(dram_cmd_yumi_lo)

     ,.mem_resp_i(dram_resp_lo)
     ,.mem_resp_v_i(dram_resp_v_lo)
     ,.mem_resp_ready_i(dram_resp_ready_li)
     );

if (cce_trace_p)
  bind bp_cce_top
    bp_cce_nonsynth_tracer
      #(.cfg_p(cfg_p))
      bp_cce_tracer
       (.clk_i(clk_i & (testbench.cce_trace_p == 1))
        ,.reset_i(reset_i)
  
        ,.cce_id_i(cce_id_i)
  
        // To CCE
        ,.lce_req_i(lce_req_to_cce)
        ,.lce_req_v_i(lce_req_v_to_cce)
        ,.lce_req_yumi_i(lce_req_yumi_from_cce)
        ,.lce_resp_i(lce_resp_to_cce)
        ,.lce_resp_v_i(lce_resp_v_to_cce)
        ,.lce_resp_yumi_i(lce_resp_yumi_from_cce)
  
        // From CCE
        ,.lce_cmd_i(lce_cmd_o)
        ,.lce_cmd_v_i(lce_cmd_v_o)
        ,.lce_cmd_ready_i(lce_cmd_ready_i)
  
        // To CCE
        ,.mem_resp_i(mem_resp_to_cce)
        ,.mem_resp_v_i(mem_resp_v_to_cce)
        ,.mem_resp_yumi_i(mem_resp_yumi_from_cce)
  
        // From CCE
        ,.mem_cmd_i(mem_cmd_from_cce)
        ,.mem_cmd_v_i(mem_cmd_v_from_cce)
        ,.mem_cmd_ready_i(mem_cmd_ready_to_cce)
        );
*/
// DRAM + link 
bp_me_cce_to_wormhole_link_client
 #(.cfg_p(cfg_p))
  client_link
  (.clk_i(clk_i)
  ,.reset_i(reset_i)

  ,.mem_cmd_o(mem_cmd_lo)
  ,.mem_cmd_v_o(mem_cmd_v_lo)
  ,.mem_cmd_yumi_i(mem_cmd_yumi_li)

  ,.mem_resp_i(mem_resp_li)
  ,.mem_resp_v_i(mem_resp_v_li)
  ,.mem_resp_ready_o(mem_resp_ready_lo)

  ,.my_cord_i(dram_cord_lo)
  ,.my_cid_i(mem_noc_cid_width_p'(0))
     
  ,.cmd_link_i(mem_cmd_link_li)
  ,.cmd_link_o(mem_cmd_link_lo)

  ,.resp_link_i(mem_resp_link_li)
  ,.resp_link_o(mem_resp_link_lo)
  );

bp2wb_convertor
  #(.cfg_p(cfg_p))
bp2wb
  (.clk_i(clk_i)
  ,.reset_i(reset_i)
  ,.mem_cmd_i(dram_cmd_li)
  ,.mem_cmd_v_i(dram_cmd_v_li)
  ,.mem_cmd_yumi_o(dram_cmd_yumi_lo)
  ,.mem_resp_o(dram_resp_lo)
  ,.mem_resp_v_o(dram_resp_v_lo)
  ,.mem_resp_ready_i(dram_resp_ready_li)
  ,.dat_i(wbm_dat_i)
  ,.dat_o(wbm_dat_o)
  ,.ack_i(wbm_ack_i)
  ,.adr_o(wbm_adr_o)
  ,.stb_o(wbm_stb_o)
  ,.cyc_o(wbm_cyc_o)
  ,.sel_o(wbm_sel_o )
  ,.we_o(wbm_we_o)
  ,.cti_o(wbm_cti_o)
  ,.bte_o(wbm_bte_o )
  );

logic [num_core_p-1:0] program_finish;

bp_nonsynth_host
 #(.cfg_p(cfg_p))
 host_mmio
  (.clk_i(clk_i)
   ,.reset_i(reset_i)

   ,.mem_cmd_i(host_cmd_li)
   ,.mem_cmd_v_i(host_cmd_v_li)
   ,.mem_cmd_yumi_o(host_cmd_yumi_lo)

   ,.mem_resp_o(host_resp_lo)
   ,.mem_resp_v_o(host_resp_v_lo)
   ,.mem_resp_ready_i(host_resp_ready_li)

   ,.program_finish_o(program_finish)
   ,.all_finished_debug_o(all_finished_debug_o)
   ,.core_passed_debug(core_passed_debug)
   ,.core_failed_debug(core_failed_debug)
   );

/*bp_nonsynth_if_verif
 #(.cfg_p(cfg_p))
 if_verif
  ();
*/
// MMIO arbitration 
//   Should this be on its own I/O router?
logic req_outstanding_r;
bsg_dff_reset_en
 #(.width_p(1))
 req_outstanding_reg
  (.clk_i(clk_i)
   ,.reset_i(reset_i)
   ,.en_i(mem_cmd_yumi_li | mem_resp_v_li)

   ,.data_i(mem_cmd_yumi_li)
   ,.data_o(req_outstanding_r)
   );

wire host_cmd_not_dram      = mem_cmd_v_lo & (mem_cmd_lo.addr < 39'h00_4000_0000 );//dram_base_addr_gp

assign host_cmd_li          = mem_cmd_lo;
assign host_cmd_v_li        = mem_cmd_v_lo & host_cmd_not_dram & ~req_outstanding_r;
assign dram_cmd_li          = mem_cmd_lo;
assign dram_cmd_v_li        = mem_cmd_v_lo & ~host_cmd_not_dram & ~req_outstanding_r;
assign mem_cmd_yumi_li      = host_cmd_not_dram 
                              ? host_cmd_yumi_lo 
                              : dram_cmd_yumi_lo;

assign mem_resp_li = host_resp_v_lo ? host_resp_lo : dram_resp_lo;
assign mem_resp_v_li = host_resp_v_lo | dram_resp_v_lo;
assign host_resp_ready_li = mem_resp_ready_lo;
assign dram_resp_ready_li = mem_resp_ready_lo;

// CFG loader + rom + link
bp_me_cce_to_wormhole_link_master
 #(.cfg_p(cfg_p))
  master_link
  (.clk_i(clk_i)
  ,.reset_i(reset_i)

  ,.mem_cmd_i(cfg_cmd_lo)
  ,.mem_cmd_v_i(cfg_cmd_ready_li & cfg_cmd_v_lo)
  ,.mem_cmd_ready_o(cfg_cmd_ready_li)

  ,.mem_resp_o(cfg_resp_li)
  ,.mem_resp_v_o(cfg_resp_v_li)
  ,.mem_resp_yumi_i(cfg_resp_ready_lo & cfg_resp_v_li)

  ,.my_cord_i(dram_cord_lo)
  ,.my_cid_i(mem_noc_cid_width_p'(0))
  ,.dram_cord_i(dram_cord_lo)
  ,.mmio_cord_i(mmio_cord_lo)
  ,.host_cord_i(host_cord_lo)
  
  ,.cmd_link_i(cfg_cmd_link_li)
  ,.cmd_link_o(cfg_cmd_link_lo)

  ,.resp_link_i(cfg_resp_link_li)
  ,.resp_link_o(cfg_resp_link_lo)
  );

localparam cce_instr_ram_addr_width_lp = `BSG_SAFE_CLOG2(num_cce_instr_ram_els_p);
bp_cce_mmio_cfg_loader
  #(.cfg_p(cfg_p)
    ,.inst_width_p(`bp_cce_inst_width)
    ,.inst_ram_addr_width_p(cce_instr_ram_addr_width_lp)
    ,.inst_ram_els_p(num_cce_instr_ram_els_p)
    ,.skip_ram_init_p(skip_init_p)
  )
  cfg_loader
  (.clk_i(clk_i)
   ,.reset_i(reset_i)
   
   ,.mem_cmd_o(cfg_cmd_lo)
   ,.mem_cmd_v_o(cfg_cmd_v_lo)
   ,.mem_cmd_yumi_i(cfg_cmd_ready_li & cfg_cmd_v_lo)
   
   ,.mem_resp_i(cfg_resp_li)
   ,.mem_resp_v_i(cfg_resp_v_li)
   ,.mem_resp_ready_o(cfg_resp_ready_lo)
  );

endmodule

