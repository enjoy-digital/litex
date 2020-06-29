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
 #(parameter bp_params_e bp_params_p = e_bp_softcore_no_l2_cfg// e_bp_softcore_cfg
   `declare_bp_proc_params(bp_params_p)
   `declare_bp_fe_be_if_widths(vaddr_width_p, paddr_width_p, asid_width_p, branch_metadata_fwd_width_p)
   `declare_bp_me_if_widths(paddr_width_p, cce_block_width_p, lce_id_width_p, lce_assoc_p)

   // Tracing parameters
   , parameter calc_trace_p                = 0
   , parameter cce_trace_p                 = 0
   , parameter cmt_trace_p                 = 0
   , parameter dram_trace_p                = 0
   , parameter npc_trace_p                 = 0
   , parameter icache_trace_p              = 0
   , parameter dcache_trace_p              = 0
   , parameter vm_trace_p                  = 0
   , parameter core_profile_p              = 0
   , parameter preload_mem_p               = 0
   , parameter load_nbf_p                  = 0
   , parameter skip_init_p                 = 0
   , parameter cosim_p                     = 0
   , parameter cosim_cfg_file_p            = "prog.cfg"
   , parameter cosim_instr_p               = 0
   , parameter warmup_instr_p              = 0
   , parameter mem_zero_p         = 1
   , parameter mem_file_p         = "prog.mem"
   , parameter mem_cap_in_bytes_p = 2**28
   , parameter [paddr_width_p-1:0] mem_offset_p = dram_base_addr_gp
 
   // Number of elements in the fake BlackParrot memory
  /*, parameter use_max_latency_p      = 0
   , parameter use_random_latency_p   = 0
   , parameter use_dramsim2_latency_p = 0

   , parameter max_latency_p = 15

   , parameter dram_clock_period_in_ps_p = `BP_SIM_CLK_PERIOD
   , parameter dram_cfg_p                = "dram_ch.ini"
   , parameter dram_sys_cfg_p            = "dram_sys.ini"
   , parameter dram_capacity_p           = 16384 
  */
   )
  (input clk_i
   , input reset_i
     //Wishbone interface
   , input  [63:0]  wbm_dat_i
   , output [63:0]  wbm_dat_o
   , input          wbm_ack_i
   , input          wbm_err_i
// , input          wbm_rty_i
   , output [36:0]  wbm_adr_o //TODO parametrize this
   , output         wbm_stb_o
   , output         wbm_cyc_o
   , output [7:0]   wbm_sel_o 
   , output         wbm_we_o
   , output [2:0]   wbm_cti_o //TODO:
   , output [1:0]   wbm_bte_o
// , input  [3:0]   interrupts
   );

`declare_bp_me_if(paddr_width_p, cce_block_width_p, lce_id_width_p, lce_assoc_p)

initial begin
  if (num_core_p > 1) begin
    assert (cosim_p == 0) else $error("cosim_p not supported for num_core_p > 1");
  end
end

logic [num_core_p-1:0] program_finish_lo;
logic cosim_finish_lo;

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

bp_cce_mem_msg_s nbf_cmd_lo;
logic nbf_cmd_v_lo, nbf_cmd_yumi_li;
bp_cce_mem_msg_s nbf_resp_li;
logic nbf_resp_v_li, nbf_resp_ready_lo;

bp_cce_mem_msg_s cfg_cmd_lo;
logic cfg_cmd_v_lo, cfg_cmd_yumi_li;
bp_cce_mem_msg_s cfg_resp_li;
logic cfg_resp_v_li, cfg_resp_ready_lo;

bp_cce_mem_msg_s load_cmd_lo;
logic load_cmd_v_lo, load_cmd_yumi_li;
bp_cce_mem_msg_s load_resp_li;
logic load_resp_v_li, load_resp_ready_lo;

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

   ,.io_cmd_i(load_cmd_lo)
   ,.io_cmd_v_i(load_cmd_v_lo)
   ,.io_cmd_yumi_o(load_cmd_yumi_li)

   ,.io_resp_o(load_resp_li)
   ,.io_resp_v_o(load_resp_v_li)
   ,.io_resp_ready_i(load_resp_ready_lo)

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
     ,.mem_cmd_v_i(proc_mem_cmd_ready_li & proc_mem_cmd_v_lo)
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
 

assign proc_io_cmd_ready_li = 1;//TODO: make sure this is necessary

logic nbf_done_lo, cfg_done_lo;
if (load_nbf_p)
  begin : nbf
    bp_nonsynth_nbf_loader
     #(.bp_params_p(bp_params_p))
     nbf_loader
      (.clk_i(clk_i)
       ,.reset_i(reset_i | ~cfg_done_lo)
    
       ,.lce_id_i(lce_id_width_p'('b10))
    
       ,.io_cmd_o(nbf_cmd_lo)
       ,.io_cmd_v_o(nbf_cmd_v_lo)
       ,.io_cmd_yumi_i(nbf_cmd_yumi_li)
    
       ,.io_resp_i(nbf_resp_li)
       ,.io_resp_v_i(nbf_resp_v_li)
       ,.io_resp_ready_o(nbf_resp_ready_lo)
    
       ,.done_o(nbf_done_lo)
       );
  end
else
  begin : no_nbf
    assign nbf_resp_ready_lo = 1'b1;
    assign nbf_cmd_v_lo = '0;
    assign nbf_cmd_lo = '0;

    assign nbf_done_lo = 1'b1;
  end

localparam cce_instr_ram_addr_width_lp = `BSG_SAFE_CLOG2(num_cce_instr_ram_els_p);
bp_cce_mmio_cfg_loader
  #(.bp_params_p(bp_params_p)
    ,.inst_width_p($bits(bp_cce_inst_s))
    ,.inst_ram_addr_width_p(cce_instr_ram_addr_width_lp)
    ,.inst_ram_els_p(num_cce_instr_ram_els_p)
    ,.skip_ram_init_p(skip_init_p)
    ,.clear_freeze_p(!load_nbf_p)
    ,.cce_ucode_filename_p("/tmp/cce_ucode.mem")
    )
  cfg_loader
  (.clk_i(clk_i)
   ,.reset_i(reset_i)

   ,.lce_id_i(lce_id_width_p'('b10))
    
   ,.io_cmd_o(cfg_cmd_lo)
   ,.io_cmd_v_o(cfg_cmd_v_lo)
   ,.io_cmd_yumi_i(cfg_cmd_yumi_li)

   ,.io_resp_i(cfg_resp_li)
   ,.io_resp_v_i(cfg_resp_v_li)
   ,.io_resp_ready_o(cfg_resp_ready_lo)

   ,.done_o(cfg_done_lo)
  );

// CFG and NBF are mutex, so we can just use fixed arbitration here
always_comb
  if (~cfg_done_lo)
    begin
      load_cmd_lo = cfg_cmd_lo;
      load_cmd_v_lo = cfg_cmd_v_lo;

      nbf_cmd_yumi_li = '0; 
      cfg_cmd_yumi_li = load_cmd_yumi_li;

      load_resp_ready_lo = cfg_resp_ready_lo;

      nbf_resp_li = '0;
      nbf_resp_v_li = '0;

      cfg_resp_li = load_resp_li;
      cfg_resp_v_li = load_resp_v_li;
    end
  else
    begin
      load_cmd_lo = nbf_cmd_lo;
      load_cmd_v_lo = nbf_cmd_v_lo;

      nbf_cmd_yumi_li = load_cmd_yumi_li; 
      cfg_cmd_yumi_li = '0;

      load_resp_ready_lo = nbf_resp_ready_lo;

      nbf_resp_li = load_resp_li;
      nbf_resp_v_li = load_resp_v_li;

      cfg_resp_li = '0;
      cfg_resp_v_li = '0;
    end

/*bp_nonsynth_host
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
*/
bind bp_be_top
  bp_nonsynth_commit_tracer
   #(.bp_params_p(bp_params_p))
   commit_tracer
    (.clk_i(clk_i & (ExampleBlackParrotSystem.cmt_trace_p == 1))
     ,.reset_i(reset_i)
     ,.freeze_i(be_checker.scheduler.int_regfile.cfg_bus.freeze)

     ,.mhartid_i('0)

     ,.decode_i(be_calculator.reservation_n.decode)

     ,.commit_v_i(be_calculator.commit_pkt.instret)
     ,.commit_pc_i(be_calculator.commit_pkt.pc)
     ,.commit_instr_i(be_calculator.commit_pkt.instr)

     ,.rd_w_v_i(be_checker.scheduler.wb_pkt.rd_w_v)
     ,.rd_addr_i(be_checker.scheduler.wb_pkt.rd_addr)
     ,.rd_data_i(be_checker.scheduler.wb_pkt.rd_data)
     );

/*  if (num_core_p == 1)
    begin : cosim
      bind bp_be_top
        bp_nonsynth_cosim
         #(.bp_params_p(bp_params_p))
          cosim
          (.clk_i(clk_i)
           ,.reset_i(reset_i)
           ,.freeze_i(be_checker.scheduler.int_regfile.cfg_bus.freeze)
           ,.en_i(ExampleBlackParrotSystem.cosim_p == 1)
           ,.cosim_instr_i(ExampleBlackParrotSystem.cosim_instr_p)

           ,.mhartid_i(be_checker.scheduler.int_regfile.cfg_bus.core_id)
           // Want to pass config file as a parameter, but cannot in Verilator 4.025
           // Parameter-resolved constants must not use dotted references
           ,.config_file_i(ExampleBlackParrotSystem.cosim_cfg_file_p)

           ,.decode_i(be_calculator.reservation_n.decode)

           ,.commit_v_i(be_calculator.commit_pkt.instret)
           ,.commit_pc_i(be_calculator.commit_pkt.pc)
           ,.commit_instr_i(be_calculator.commit_pkt.instr)

           ,.rd_w_v_i(be_checker.scheduler.wb_pkt.rd_w_v)
           ,.rd_addr_i(be_checker.scheduler.wb_pkt.rd_addr)
           ,.rd_data_i(be_checker.scheduler.wb_pkt.rd_data)

           ,.interrupt_v_i(be_mem.csr.trap_pkt_cast_o._interrupt)
           ,.cause_i(be_mem.csr.trap_pkt_cast_o.cause)

           ,.finish_o(ExampleBlackParrotSystem.cosim_finish_lo)
           );
    end
  else
    begin : no_cosim*/
      assign cosim_finish_lo = '0;
 //   end

/*bind bp_be_top
  bp_be_nonsynth_perf
   #(.bp_params_p(bp_params_p))
   perf
    (.clk_i(clk_i)
     ,.reset_i(reset_i)
     ,.freeze_i(be_checker.scheduler.int_regfile.cfg_bus.freeze)
     ,.warmup_instr_i(ExampleBlackParrotSystem.warmup_instr_p)

     ,.mhartid_i(be_checker.scheduler.int_regfile.cfg_bus.core_id)

     ,.commit_v_i(be_calculator.commit_pkt.instret)

     ,.program_finish_i(ExampleBlackParrotSystem.program_finish_lo | ExampleBlackParrotSystem.cosim_finish_lo)
     );
*/
/*  bind bp_be_top
    bp_nonsynth_watchdog
     #(.bp_params_p(bp_params_p)
       ,.timeout_cycles_p(100000)
       ,.heartbeat_instr_p(100000)
       )
     watchdog
      (.clk_i(clk_i)
       ,.reset_i(reset_i)
       ,.freeze_i(be_checker.scheduler.int_regfile.cfg_bus.freeze)

       ,.mhartid_i(be_checker.scheduler.int_regfile.cfg_bus.core_id)

       ,.npc_i(be_checker.director.npc_r)
       ,.instret_i(be_calculator.commit_pkt.instret)
       );
*/
/*  bind bp_be_director
    bp_be_nonsynth_npc_tracer
     #(.bp_params_p(bp_params_p))
     npc_tracer
      (.clk_i(clk_i & (ExampleBlackParrotSystem.npc_trace_p == 1))
       ,.reset_i(reset_i)
       ,.freeze_i(be_checker.scheduler.int_regfile.cfg_bus.freeze)

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
/*  bind bp_be_dcache
    bp_nonsynth_cache_tracer
     #(.bp_params_p(bp_params_p)
      ,.assoc_p(dcache_assoc_p)
      ,.sets_p(dcache_sets_p)
      ,.block_width_p(dcache_block_width_p)
      ,.trace_file_p("dcache"))
     dcache_tracer
      (.clk_i(clk_i & (ExampleBlackParrotSystem.dcache_trace_p == 1))
       ,.reset_i(reset_i)
       ,.freeze_i(cfg_bus_cast_i.freeze)

       ,.mhartid_i(cfg_bus_cast_i.core_id)

       ,.v_tl_r(v_tl_r)
       
       ,.v_tv_r(v_tv_r)
       ,.addr_tv_r(paddr_tv_r)
       ,.lr_miss_tv(lr_miss_tv)
       ,.sc_op_tv_r(sc_op_tv_r)
       ,.sc_success(sc_success)
        
       ,.cache_req_v_o(cache_req_v_o)
       ,.cache_req_o(cache_req_o)

       ,.cache_req_metadata_o(cache_req_metadata_o)
       ,.cache_req_metadata_v_o(cache_req_metadata_v_o)
        
       ,.cache_req_complete_i(cache_req_complete_i)

       ,.v_o(v_o)
       ,.load_data(data_o)
       ,.cache_miss_o(dcache_miss_o)
       ,.wt_req(wt_req)
       ,.store_data(data_tv_r)

       ,.data_mem_pkt_v_i(data_mem_pkt_v_i)
       ,.data_mem_pkt_i(data_mem_pkt_i)
       ,.data_mem_pkt_yumi_o(data_mem_pkt_yumi_o)
       
       ,.tag_mem_pkt_v_i(tag_mem_pkt_v_i)
       ,.tag_mem_pkt_i(tag_mem_pkt_i)
       ,.tag_mem_pkt_yumi_o(tag_mem_pkt_yumi_o)

       ,.stat_mem_pkt_v_i(stat_mem_pkt_v_i)
       ,.stat_mem_pkt_i(stat_mem_pkt_i)
       ,.stat_mem_pkt_yumi_o(stat_mem_pkt_yumi_o)
       );
*/
/*  bind bp_fe_icache
    bp_nonsynth_cache_tracer
     #(.bp_params_p(bp_params_p)
      ,.assoc_p(icache_assoc_p)
      ,.sets_p(icache_sets_p)
      ,.block_width_p(icache_block_width_p)
      ,.trace_file_p("icache"))
     icache_tracer
      (.clk_i(clk_i & (ExampleBlackParrotSystem.icache_trace_p == 1))
       ,.reset_i(reset_i)
       
       ,.freeze_i(cfg_bus_cast_i.freeze)
       ,.mhartid_i(cfg_bus_cast_i.core_id)

       ,.v_tl_r(v_tl_r)
       
       ,.v_tv_r(v_tv_r)
       ,.addr_tv_r(addr_tv_r)
       ,.lr_miss_tv(1'b0)
       ,.sc_op_tv_r(1'b0)
       ,.sc_success(1'b0)
        
       ,.cache_req_v_o(cache_req_v_o)
       ,.cache_req_o(cache_req_o)

       ,.cache_req_metadata_o(cache_req_metadata_o)
       ,.cache_req_metadata_v_o(cache_req_metadata_v_o)
        
       ,.cache_req_complete_i(cache_req_complete_i)

       ,.v_o(data_v_o)
       ,.load_data(dword_width_p'(data_o))
       ,.cache_miss_o(miss_o)
       ,.wt_req()
       ,.store_data(dword_width_p'(0))

       ,.data_mem_pkt_v_i(data_mem_pkt_v_i)
       ,.data_mem_pkt_i(data_mem_pkt_i)
       ,.data_mem_pkt_yumi_o(data_mem_pkt_yumi_o)
       
       ,.tag_mem_pkt_v_i(tag_mem_pkt_v_i)
       ,.tag_mem_pkt_i(tag_mem_pkt_i)
       ,.tag_mem_pkt_yumi_o(tag_mem_pkt_yumi_o)

       ,.stat_mem_pkt_v_i(stat_mem_pkt_v_i)
       ,.stat_mem_pkt_i(stat_mem_pkt_i)
       ,.stat_mem_pkt_yumi_o(stat_mem_pkt_yumi_o)
       );
*/
/*  bind bp_core_minimal
    bp_be_nonsynth_vm_tracer
    #(.bp_params_p(bp_params_p))
    vm_tracer
      (.clk_i(clk_i & (ExampleBlackParrotSystem.vm_trace_p == 1))
       ,.reset_i(reset_i)
       ,.freeze_i(be.be_checker.scheduler.int_regfile.cfg_bus.freeze)

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
  bp_mem_nonsynth_tracer
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

/*  bind bp_core_minimal
    bp_nonsynth_core_profiler
     #(.bp_params_p(bp_params_p))
     core_profiler
      (.clk_i(clk_i & (ExampleBlackParrotSystem.core_profile_p == 1))
       ,.reset_i(reset_i)
       ,.freeze_i(be.be_checker.scheduler.int_regfile.cfg_bus.freeze)

       ,.mhartid_i(be.be_checker.scheduler.int_regfile.cfg_bus.core_id)

       ,.fe_wait_stall(fe.pc_gen.is_wait)
       ,.fe_queue_stall(~fe.pc_gen.fe_queue_ready_i)

       ,.itlb_miss(fe.mem.itlb_miss_r)
       ,.icache_miss(~fe.mem.icache.vaddr_ready_o | fe.pc_gen.icache_miss)
       ,.icache_fence(fe.mem.icache.fencei_req)
       ,.branch_override(fe.pc_gen.ovr_taken & ~fe.pc_gen.ovr_ret)
       ,.ret_override(fe.pc_gen.ovr_ret)

       ,.fe_cmd(fe.pc_gen.fe_cmd_yumi_o & ~fe.pc_gen.attaboy_v)

       ,.mispredict(be.be_checker.director.npc_mismatch_v)
       ,.target(be.be_checker.director.isd_status.isd_pc)

       ,.dtlb_miss(be.be_mem.dtlb_miss_r)
       ,.dcache_miss(~be.be_mem.dcache.ready_o)
       ,.long_haz(be.be_checker.detector.long_haz_v)
       ,.exception(be.be_checker.director.trap_pkt.exception)
       ,.eret(be.be_checker.director.trap_pkt.eret)
       ,._interrupt(be.be_checker.director.trap_pkt._interrupt)
       ,.control_haz(be.be_checker.detector.control_haz_v)
       ,.data_haz(be.be_checker.detector.data_haz_v)
       ,.load_dep((be.be_checker.detector.dep_status_li[0].mem_iwb_v
                   | be.be_checker.detector.dep_status_li[1].mem_iwb_v
                   ) & be.be_checker.detector.data_haz_v
                  )
       ,.mul_dep((be.be_checker.detector.dep_status_li[0].mul_iwb_v
                  | be.be_checker.detector.dep_status_li[1].mul_iwb_v
                  | be.be_checker.detector.dep_status_li[2].mul_iwb_v
                  ) & be.be_checker.detector.data_haz_v
                 )
       ,.struct_haz(be.be_checker.detector.struct_haz_v)

       ,.reservation(be.be_calculator.reservation_n)
       ,.commit_pkt(be.be_calculator.commit_pkt)
       ,.trap_pkt(be.be_mem.csr.trap_pkt_o)
       );
*/
/*  bind bp_core_minimal
    bp_nonsynth_pc_profiler
     #(.bp_params_p(bp_params_p))
     pc_profiler
      (.clk_i(clk_i & (ExampleBlackParrotSystem.core_profile_p == 1))
       ,.reset_i(reset_i)
       ,.freeze_i(be.be_checker.scheduler.int_regfile.cfg_bus.freeze)

       ,.mhartid_i(be.be_checker.scheduler.int_regfile.cfg_bus.core_id)

       ,.commit_pkt(be.be_calculator.commit_pkt)

       ,.program_finish_i(ExampleBlackParrotSystem.program_finish_lo)
       );
*/
/*  bind bp_be_director
    bp_nonsynth_branch_profiler
     #(.bp_params_p(bp_params_p))
     pc_profiler
      (.clk_i(clk_i & (ExampleBlackParrotSystem.core_profile_p == 1))
       ,.reset_i(reset_i)
       ,.freeze_i(cfg_bus_cast_i.freeze)

       ,.mhartid_i(cfg_bus_cast_i.core_id)

       ,.fe_cmd_o(fe_cmd_o)
       ,.fe_cmd_v_o(fe_cmd_v_o)
       ,.fe_cmd_ready_i(fe_cmd_ready_i)

       ,.commit_v_i(commit_pkt.instret)

       ,.program_finish_i(ExampleBlackParrotSystem.program_finish_lo)
       );
*/
/* bp_nonsynth_if_verif
  #(.bp_params_p(bp_params_p))
  if_verif
   ();
*/
 endmodule
 
