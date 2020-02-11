/* 
 * bp_common_pkg.vh
 *
 * Contains the interface structures used for communicating between FE, BE, ME in BlackParrot.
 * Additionally contains global parameters used to configure the system. In the future, when 
 *   multiple configurations are supported, these global parameters will belong to groups 
 *   e.g. SV39, VM-disabled, ...
 *
 */

package bp_common_pkg;

  `include "bsg_defines.v"
  `include "bp_common_defines.vh"
  `include "bp_common_fe_be_if.vh"
  `include "bp_common_me_if.vh"

  /*
   * RV64 specifies a 64b effective address and 32b instruction.
   * BlackParrot supports SV39 virtual memory, which specifies 39b virtual / 56b physical address.
   * Effective addresses must have bits 39-63 match bit 38 
   *   or a page fault exception will occur during translation.
   * Currently, we only support a very limited number of parameter configurations.
   * Thought: We could have a `define surrounding core instantiations of each parameter and then
   * when they import this package, `declare the if structs. No more casting!
   */

  localparam bp_eaddr_width_gp = 64;
  localparam bp_instr_width_gp = 32;

  parameter bp_sv39_page_table_depth_gp = 3;
  parameter bp_sv39_pte_width_gp = 64;
  parameter bp_sv39_vaddr_width_gp = 39;
  parameter bp_sv39_paddr_width_gp = 56;
  parameter bp_sv39_ppn_width_gp = 44;
  parameter bp_page_size_in_bytes_gp = 4096;
  parameter bp_page_offset_width_gp = `BSG_SAFE_CLOG2(bp_page_size_in_bytes_gp);

  parameter bp_data_resp_num_flit_gp = 4;
  parameter bp_data_cmd_num_flit_gp = 4;
 
  localparam dram_base_addr_gp         = 32'h5000_0000;
 
  localparam cfg_link_dev_base_addr_gp = 32'h01??_????;
  localparam clint_dev_base_addr_gp    = 32'h02??_????;
  localparam host_dev_base_addr_gp     = 32'h03??_????;
  localparam plic_dev_base_addr_gp     = 32'h0c??_????;
  
  localparam mipi_reg_base_addr_gp     = 32'h0200_0???;
  localparam mtimecmp_reg_base_addr_gp = 32'h0200_4???;
  localparam mtime_reg_addr_gp         = 32'h0200_bff8;
  localparam plic_reg_base_addr_gp     = 32'h0c00_0???;

endpackage : bp_common_pkg

