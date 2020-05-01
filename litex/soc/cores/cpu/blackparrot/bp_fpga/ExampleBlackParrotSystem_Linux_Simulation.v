/**
  *
  * ExampleBlackParrotSystem.v
  *
  */
  
`include "bsg_noc_links.vh"

module ExampleBlackParrotSystem
 import bp_common_pkg::*;
 import bp_common_aviary_pkg::*;
 import bp_be_pkg::*;
 import bp_common_rv64_pkg::*;
 import bp_cce_pkg::*;
 import bp_me_pkg::*;
 import bp_common_cfg_link_pkg::*;
 import bsg_noc_pkg::*;
 #(parameter bp_params_e bp_params_p = e_bp_softcore_cfg
   `declare_bp_proc_params(bp_params_p)
   `declare_bp_me_if_widths(paddr_width_p, cce_block_width_p, lce_id_width_p, lce_assoc_p)

   // Tracing parameters
   , parameter calc_trace_p                = 0
   , parameter cce_trace_p                 = 0
   , parameter cmt_trace_p                 = 0
   , parameter dram_trace_p                = 0
   , parameter npc_trace_p                 = 0
   , parameter dcache_trace_p              = 0
   , parameter vm_trace_p                  = 0
   , parameter preload_mem_p               = 1
   , parameter load_nbf_p                  = 0
   , parameter skip_init_p                 = 0
   , parameter cosim_p                     = 0
   , parameter cosim_cfg_file_p            = "prog.cfg"

   , parameter mem_zero_p         = 1
   , parameter mem_file_p         = "prog.mem"
   , parameter mem_cap_in_bytes_p = 2**25
   , parameter [paddr_width_p-1:0] mem_offset_p = paddr_width_p'(32'h8000_0000)

   // Number of elements in the fake BlackParrot memory
   , parameter use_max_latency_p      = 1
   , parameter use_random_latency_p   = 0
   , parameter use_dramsim2_latency_p = 0

   , parameter max_latency_p = 15

   , parameter dram_clock_period_in_ps_p = 1000
   , parameter dram_cfg_p                = "dram_ch.ini"
   , parameter dram_sys_cfg_p            = "dram_sys.ini"
   , parameter dram_capacity_p           = 16384
   )
  (input clk_i
   , input reset_i
      //Wishbone interface
   , input  [63:0]  wbm_dat_i
   , output [63:0]  wbm_dat_o
   , input          wbm_ack_i
   , input          wbm_err_i
//   , input          wbm_rty_i
   , output [36:0]  wbm_adr_o //TODO parametrize this
   , output         wbm_stb_o
   , output         wbm_cyc_o
   , output [7:0]   wbm_sel_o //TODO: how many  bits ? check
   , output         wbm_we_o
   , output [2:0]   wbm_cti_o //TODO:
   , output [1:0]   wbm_bte_o
  // , input  [3:0]   interrupts
   );

`declare_bp_me_if(paddr_width_p, cce_block_width_p, lce_id_width_p, lce_assoc_p)

bp_cce_mem_msg_s proc_mem_cmd_lo;
logic proc_mem_cmd_v_lo, proc_mem_cmd_ready_li;
bp_cce_mem_msg_s proc_mem_resp_li;
logic proc_mem_resp_v_li, proc_mem_resp_yumi_lo;

bp_cce_mem_msg_s proc_io_cmd_lo;
logic proc_io_cmd_v_lo, proc_io_cmd_ready_li;
bp_cce_mem_msg_s proc_io_resp_li;
logic proc_io_resp_v_li, proc_io_resp_yumi_lo;

bp_cce_mem_msg_s io_cmd_lo;
logic io_cmd_v_lo, io_cmd_ready_li;
bp_cce_mem_msg_s io_resp_li;
logic io_resp_v_li, io_resp_yumi_lo;
bp_softcore
 #(.bp_params_p(bp_params_p))
 softcore
  (.clk_i(clk_i)
   ,.reset_i(reset_i)

   ,.io_cmd_o(proc_io_cmd_lo)
   ,.io_cmd_v_o(proc_io_cmd_v_lo)
   ,.io_cmd_ready_i(proc_io_cmd_ready_li)

   ,.io_resp_i(proc_io_resp_li)
   ,.io_resp_v_i(proc_io_resp_v_li)
   ,.io_resp_yumi_o(proc_io_resp_yumi_lo)

   ,.mem_cmd_o(proc_mem_cmd_lo)
   ,.mem_cmd_v_o(proc_mem_cmd_v_lo)
   ,.mem_cmd_ready_i(proc_mem_cmd_ready_li)

   ,.mem_resp_i(proc_mem_resp_li)
   ,.mem_resp_v_i(proc_mem_resp_v_li)
   ,.mem_resp_yumi_o(proc_mem_resp_yumi_lo)
   );

 bp2wb_convertor
   #(.bp_params_p(bp_params_p))
   bp2wb
    (.clk_i(clk_i)
     ,.reset_i(reset_i)
    ,.mem_cmd_i(proc_mem_cmd_lo)
     ,.mem_cmd_v_i(proc_mem_cmd_v_lo & proc_mem_cmd_ready_li)
     ,.mem_cmd_ready_o(proc_mem_cmd_ready_li)

     ,.mem_resp_o(proc_mem_resp_li)
     ,.mem_resp_v_o(proc_mem_resp_v_li)
     ,.mem_resp_yumi_i(proc_mem_resp_yumi_lo)

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
    // ,.rty_i(wbm_rty_i)
     ,.err_i(wbm_err_i)
     );

/*
bp_mem
 mem
  (.clk_i(clk_i)
   ,.reset_i(reset_i)
 
   ,.mem_cmd_i(proc_mem_cmd_lo)
   ,.mem_cmd_v_i(proc_mem_cmd_v_lo & proc_mem_cmd_ready_li)
   ,.mem_cmd_ready_o(proc_mem_cmd_ready_li)
 
   ,.mem_resp_o(proc_mem_resp_li)
   ,.mem_resp_v_o(proc_mem_resp_v_li)
   ,.mem_resp_yumi_i(proc_mem_resp_yumi_lo)
   );
*/
logic program_finish_lo;
bp_nonsynth_host
 #(.bp_params_p(bp_params_p))
 host
  (.clk_i(clk_i)
   ,.reset_i(reset_i)

   ,.io_cmd_i(proc_io_cmd_lo)
   ,.io_cmd_v_i(proc_io_cmd_v_lo & proc_io_cmd_ready_li)
   ,.io_cmd_ready_o(proc_io_cmd_ready_li)

   ,.io_resp_o(proc_io_resp_li)
   ,.io_resp_v_o(proc_io_resp_v_li)
   ,.io_resp_yumi_i(proc_io_resp_yumi_lo)

   ,.program_finish_o(program_finish_lo)
   );

/*bind bp_be_top
  bp_nonsynth_commit_tracer
   #(.bp_params_p(bp_params_p))
   commit_tracer
    (.clk_i(clk_i & (ExampleBlackParrotSystem.cmt_trace_p == 1))
     ,.reset_i(reset_i)
     ,.freeze_i('0)

     ,.mhartid_i('0)

     ,.commit_v_i(be_calculator.commit_pkt.instret)
     ,.commit_pc_i(be_calculator.commit_pkt.pc)
     ,.commit_instr_i(be_calculator.commit_pkt.instr)

     ,.rd_w_v_i(be_calculator.wb_pkt.rd_w_v)
     ,.rd_addr_i(be_calculator.wb_pkt.rd_addr)
     ,.rd_data_i(be_calculator.wb_pkt.rd_data)
     );
*/
/*  bind bp_be_top
    bp_nonsynth_cosim
     #(.bp_params_p(bp_params_p))
      cosim
      (.clk_i(clk_i)
       ,.reset_i(reset_i)
       ,.en_i(ExampleBlackParrotSystem.cosim_p == 1)

       ,.mhartid_i(be_checker.scheduler.int_regfile.cfg_bus.core_id)
       // Want to pass config file as a parameter, but cannot in Verilator 4.025
       // Parameter-resolved constants must not use dotted references
       ,.config_file_i(ExampleBlackParrotSystem.cosim_cfg_file_p)

       ,.commit_v_i(be_calculator.commit_pkt.instret)
       ,.commit_pc_i(be_calculator.commit_pkt.pc)
       ,.commit_instr_i(be_calculator.commit_pkt.instr)

       ,.rd_w_v_i(be_calculator.wb_pkt.rd_w_v)
       ,.rd_addr_i(be_calculator.wb_pkt.rd_addr)
       ,.rd_data_i(be_calculator.wb_pkt.rd_data)

       ,.interrupt_v_i(be_mem.csr.trap_pkt_cast_o._interrupt)
       ,.cause_i(be_mem.csr.trap_pkt_cast_o.cause)
       );
*/
/*bind bp_be_top
  bp_be_nonsynth_perf
   #(.bp_params_p(bp_params_p))
   perf
    (.clk_i(clk_i)
     ,.reset_i(reset_i)

     ,.mhartid_i(be_checker.scheduler.int_regfile.cfg_bus.core_id)

     ,.fe_nop_i(be_calculator.exc_stage_r[2].fe_nop_v)
     ,.be_nop_i(be_calculator.exc_stage_r[2].be_nop_v)
     ,.me_nop_i(be_calculator.exc_stage_r[2].me_nop_v)
     ,.poison_i(be_calculator.exc_stage_r[2].poison_v)
     ,.roll_i(be_calculator.exc_stage_r[2].roll_v)

     ,.instr_cmt_i(be_calculator.commit_pkt.instret)

     ,.program_finish_i(ExampleBlackParrotSystem.program_finish_lo)
     );
*/
 /* bind bp_be_director
    bp_be_nonsynth_npc_tracer
     #(.bp_params_p(bp_params_p))
     npc_tracer
      (.clk_i(clk_i & (ExampleBlackParrotSystem.npc_trace_p == 1))
       ,.reset_i(reset_i)
       ,.freeze_i('0)

       ,.mhartid_i(be_checker.scheduler.int_regfile.cfg_bus.core_id)

       ,.npc_w_v(npc_w_v)
       ,.npc_n(npc_n)
       ,.npc_r(npc_r)
       ,.expected_npc_o(expected_npc_o)

       ,.fe_cmd_i(fe_cmd)
       ,.fe_cmd_v(fe_cmd_v)

       ,.commit_pkt_i(commit_pkt)
       );
*/
  /*bind bp_be_dcache
    bp_be_nonsynth_dcache_tracer
     #(.bp_params_p(bp_params_p))
     dcache_tracer
      (.clk_i(clk_i & (ExampleBlackParrotSystem.dcache_trace_p == 1))
       ,.reset_i(reset_i)
       ,.freeze_i('0)

       ,.mhartid_i(cfg_bus_cast_i.core_id)

       ,.v_tv_r(v_tv_r)
       //,.cache_miss_i(cache_miss_i)

       ,.paddr_tv_r(paddr_tv_r)
       ,.uncached_tv_r(uncached_tv_r)
       ,.load_op_tv_r(load_op_tv_r)
       ,.store_op_tv_r(store_op_tv_r)
       ,.lr_op_tv_r(lr_op_tv_r)
       ,.sc_op_tv_r(sc_op_tv_r)
       ,.store_data(data_tv_r)
       ,.load_data(data_o)
       );*/
/*
  bind bp_be_top
    bp_be_nonsynth_calc_tracer
     #(.bp_params_p(bp_params_p))
     calc_tracer
      (.clk_i(clk_i & (ExampleBlackParrotSystem.calc_trace_p == 1))
       ,.reset_i(reset_i)
       ,.freeze_i('0)

       ,.mhartid_i(be_checker.scheduler.int_regfile.cfg_bus.core_id)

       ,.issue_pkt_i(be_checker.scheduler.issue_pkt)
       ,.issue_pkt_v_i(be_checker.scheduler.fe_queue_yumi_o)

       ,.fe_nop_v_i(be_calculator.exc_stage_n[0].fe_nop_v)
       ,.be_nop_v_i(be_calculator.exc_stage_n[0].be_nop_v)
       ,.me_nop_v_i(be_calculator.exc_stage_n[0].me_nop_v)
       ,.dispatch_pkt_i(be_calculator.dispatch_pkt)

       ,.ex1_br_tgt_i(be_calculator.calc_status.ex1_npc)
       ,.ex1_btaken_i(be_calculator.pipe_int.btaken)
       ,.iwb_result_i(be_calculator.comp_stage_n[3])
       ,.fwb_result_i(be_calculator.comp_stage_n[4])

       ,.cmt_trace_exc_i(be_calculator.exc_stage_n[1+:5])

       ,.trap_v_i(be_mem.csr.trap_pkt_cast_o._interrupt | be_mem.csr.trap_pkt_cast_o.exception)
       ,.mtvec_i(be_mem.csr.mtvec_n)
       ,.mtval_i(be_mem.csr.mtval_n[0+:vaddr_width_p])
       ,.ret_v_i(be_mem.csr.trap_pkt_cast_o.eret)
       ,.mepc_i(be_mem.csr.mepc_n[0+:vaddr_width_p])
       ,.mcause_i(be_mem.csr.mcause_n)

       ,.priv_mode_i(be_mem.csr.priv_mode_n)
       ,.mpp_i(be_mem.csr.mstatus_n.mpp)
       );

  bind bp_core_minimal
    bp_be_nonsynth_vm_tracer
    #(.bp_params_p(bp_params_p))
    vm_tracer
      (.clk_i(clk_i & (ExampleBlackParrotSystem.vm_trace_p == 1))
       ,.reset_i(reset_i)
       ,.freeze_i('0)

       ,.mhartid_i(be.be_checker.scheduler.int_regfile.cfg_bus.core_id)

       ,.itlb_clear_i(fe.mem.itlb.flush_i)
       ,.itlb_fill_v_i(fe.mem.itlb.v_i & fe.mem.itlb.w_i)
       ,.itlb_vtag_i(fe.mem.itlb.vtag_i)
       ,.itlb_entry_i(fe.mem.itlb.entry_i)

       ,.dtlb_clear_i(be.be_mem.dtlb.flush_i)
       ,.dtlb_fill_v_i(be.be_mem.dtlb.v_i & be.be_mem.dtlb.w_i)
       ,.dtlb_vtag_i(be.be_mem.dtlb.vtag_i)
       ,.dtlb_entry_i(be.be_mem.dtlb.entry_i)
       );
*/
  /*bp_mem_nonsynth_tracer
   #(.bp_params_p(bp_params_p))
   bp_mem_tracer
    (.clk_i(clk_i & (ExampleBlackParrotSystem.dram_trace_p == 1))
     ,.reset_i(reset_i)

     ,.mem_cmd_i(proc_mem_cmd_lo)
     ,.mem_cmd_v_i(proc_mem_cmd_v_lo & proc_mem_cmd_ready_li)
     ,.mem_cmd_ready_i(proc_mem_cmd_ready_li)

     ,.mem_resp_i(proc_mem_resp_li)
     ,.mem_resp_v_i(proc_mem_resp_v_li)
     ,.mem_resp_yumi_i(proc_mem_resp_yumi_lo)
     );
*/
/*bp_nonsynth_if_verif
 #(.bp_params_p(bp_params_p))
 if_verif
  ();
*/
endmodule

