-- ================================================================================ --
-- NEORV32 CPU - Arithmetic/Logic Unit                                              --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_cpu_alu is
  generic (
    -- RISC-V CPU Extensions --
    RISCV_ISA_M      : boolean; -- mul/div extension
    RISCV_ISA_Zba    : boolean; -- address-generation instruction
    RISCV_ISA_Zbb    : boolean; -- basic bit-manipulation instruction
    RISCV_ISA_Zbkb   : boolean; -- bit-manipulation instructions for cryptography
    RISCV_ISA_Zbkc   : boolean; -- carry-less multiplication instructions
    RISCV_ISA_Zbkx   : boolean; -- cryptography crossbar permutation extension
    RISCV_ISA_Zbs    : boolean; -- single-bit instructions
    RISCV_ISA_Zfinx  : boolean; -- 32-bit floating-point extension
    RISCV_ISA_Zibi   : boolean; -- branch with immediate
    RISCV_ISA_Zicond : boolean; -- integer conditional operations
    RISCV_ISA_Zknd   : boolean; -- cryptography NIST AES decryption extension
    RISCV_ISA_Zkne   : boolean; -- cryptography NIST AES encryption extension
    RISCV_ISA_Zknh   : boolean; -- cryptography NIST hash extension
    RISCV_ISA_Zksed  : boolean; -- ShangMi block cipher extension
    RISCV_ISA_Zksh   : boolean; -- ShangMi hash extension
    RISCV_ISA_Zmmul  : boolean; -- multiply-only M sub-extension
    RISCV_ISA_Zxcfu  : boolean; -- custom (instr.) functions unit
    -- Tuning Options --
    FAST_MUL_EN      : boolean; -- use DSPs for M extension's multiplier
    FAST_SHIFT_EN    : boolean  -- use barrel shifter for shift operations
  );
  port (
    -- global control --
    clk_i  : in  std_ulogic; -- global clock, rising edge
    rstn_i : in  std_ulogic; -- global reset, low-active, async
    ctrl_i : in  ctrl_bus_t; -- main control bus
    -- data input --
    rs1_i  : in  std_ulogic_vector(31 downto 0); -- rf source 1
    rs2_i  : in  std_ulogic_vector(31 downto 0); -- rf source 2
    -- data output --
    cmp_o  : out std_ulogic_vector(1 downto 0);  -- comparator status
    res_o  : out std_ulogic_vector(31 downto 0); -- ALU result
    add_o  : out std_ulogic_vector(31 downto 0); -- address computation result
    csr_o  : out std_ulogic_vector(31 downto 0); -- CSR read data
    -- status --
    done_o : out std_ulogic -- co-processor operation done?
  );
end neorv32_cpu_alu;

architecture neorv32_cpu_alu_rtl of neorv32_cpu_alu is

  -- Zibi ISA extension: compare with immediate --
  function zibi_cmp_f(sel : std_ulogic_vector(4 downto 0); cmp : std_ulogic_vector) return std_ulogic is
    variable imm_v : std_ulogic_vector(cmp'length-1 downto 0);
  begin
    -- immediate selection --
    if (sel = "00000") then
      imm_v := (others => '1');
    else
      imm_v := (others => '0');
      imm_v(4 downto 0) := sel;
    end if;
    -- equal? --
    if (imm_v = cmp) then
      return '1';
    else
      return '0';
    end if;
  end function zibi_cmp_f;

  -- comparator --
  signal cmp_rs1, cmp_rs2 : std_ulogic_vector(32 downto 0);
  signal cmp_eq,  cmp_ls  : std_ulogic;

  -- operands --
  signal opa,   opb   : std_ulogic_vector(31 downto 0);
  signal opa_x, opb_x : std_ulogic_vector(32 downto 0);

  -- intermediate results --
  signal addsub_res : std_ulogic_vector(32 downto 0);
  signal cp_res     : std_ulogic_vector(31 downto 0);

  -- co-processor interface --
  type cp_data_t  is array (0 to 6) of std_ulogic_vector(31 downto 0);
  signal cp_result : cp_data_t;
  signal cp_valid  : std_ulogic_vector(6 downto 0);

  -- proxy logic --
  signal fpu_csr_en, fpu_csr_we, cfu_done, cfu_busy : std_ulogic;
  signal fpu_csr_rd, cfu_res : std_ulogic_vector(31 downto 0);

begin

  -- Comparator Unit ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  cmp_rs1 <= (rs1_i(rs1_i'left) and (not ctrl_i.alu_unsigned)) & rs1_i; -- sign-extend
  cmp_rs2 <= (rs2_i(rs2_i'left) and (not ctrl_i.alu_unsigned)) & rs2_i; -- sign-extend

  cmp_eq <= '1' when (rs1_i = rs2_i) else '0';
  cmp_ls <= '1' when (signed(cmp_rs1) < signed(cmp_rs2)) else '0'; -- signed or unsigned comparison

  cmp_o(cmp_equal_c) <= zibi_cmp_f(ctrl_i.rf_rs2, rs1_i) when (ctrl_i.ir_funct3(2 downto 1) = "01") and RISCV_ISA_Zibi else cmp_eq;
  cmp_o(cmp_less_c)  <= cmp_ls;


  -- ALU Input Operand Select ---------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  opa <= ctrl_i.pc_cur  when (ctrl_i.alu_opa_mux = '1') else rs1_i;
  opb <= ctrl_i.alu_imm when (ctrl_i.alu_opb_mux = '1') else rs2_i;


  -- Adder/Subtractor Core ------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  opa_x <= (opa(opa'left) and (not ctrl_i.alu_unsigned)) & opa; -- sign-extend
  opb_x <= (opb(opb'left) and (not ctrl_i.alu_unsigned)) & opb; -- sign-extend

  addsub_res <= std_ulogic_vector(unsigned(opa_x) - unsigned(opb_x)) when (ctrl_i.alu_sub = '1') else
                std_ulogic_vector(unsigned(opa_x) + unsigned(opb_x));

  add_o <= addsub_res(31 downto 0); -- direct output


  -- ALU Operation Select -------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  alu_core: process(ctrl_i, addsub_res, cp_res, rs1_i, opb)
  begin
    res_o <= (others => '0');
    case ctrl_i.alu_op is
      when alu_op_zero_c => res_o <= (others => '0');
      when alu_op_add_c  => res_o <= addsub_res(31 downto 0);
      when alu_op_cp_c   => res_o <= cp_res;
      when alu_op_slt_c  => res_o(0) <= addsub_res(addsub_res'left); -- carry/borrow
      when alu_op_movb_c => res_o <= opb;
      when alu_op_xor_c  => res_o <= opb xor rs1_i;
      when alu_op_or_c   => res_o <= opb or  rs1_i;
      when alu_op_and_c  => res_o <= opb and rs1_i;
      when others        => res_o <= (others => '0');
    end case;
  end process alu_core;


  -- **************************************************************************************************************************
  -- ALU Co-Processors
  -- **************************************************************************************************************************

  -- multi-cycle co-processor operation done? --
  -- > "cp_valid" signal has to be set (for one cycle) one cycle before CP output data (cp_result) is valid
  done_o <= cp_valid(0) or cp_valid(1) or cp_valid(2) or cp_valid(3) or cp_valid(4) or cp_valid(5) or cp_valid(6);

  -- co-processor result --
  -- > "cp_result" data has to be always zero unless the specific co-processor has been actually triggered
  cp_res <= cp_result(0) or cp_result(1) or cp_result(2) or cp_result(3) or cp_result(4) or cp_result(5) or cp_result(6);


  -- ALU[I]-Opcode Co-Processor: Shifter Unit (Base ISA) ------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_cp_shifter_inst: entity neorv32.neorv32_cpu_cp_shifter
  generic map (
    FAST_SHIFT_EN => FAST_SHIFT_EN -- use barrel shifter for shift operations
  )
  port map (
    -- global control --
    clk_i   => clk_i,           -- global clock, rising edge
    rstn_i  => rstn_i,          -- global reset, low-active, async
    ctrl_i  => ctrl_i,          -- main control bus
    -- data input --
    rs1_i   => rs1_i,           -- rf source 1
    shamt_i => opb(4 downto 0), -- shift amount
    -- result and status --
    res_o   => cp_result(0),    -- operation result
    valid_o => cp_valid(0)      -- data output valid
  );


  -- ALU-Opcode Co-Processor: Integer Multiplication/Division Unit ('M' ISA Extension) ------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_cp_muldiv_inst_true:
  if RISCV_ISA_M or RISCV_ISA_Zmmul generate
    neorv32_cpu_cp_muldiv_inst: entity neorv32.neorv32_cpu_cp_muldiv
    generic map (
      FAST_MUL_EN => FAST_MUL_EN, -- use DSPs for faster multiplication
      DIVISION_EN => RISCV_ISA_M  -- implement divider hardware
    )
    port map (
      -- global control --
      clk_i   => clk_i,        -- global clock, rising edge
      rstn_i  => rstn_i,       -- global reset, low-active, async
      ctrl_i  => ctrl_i,       -- main control bus
      -- data input --
      rs1_i   => rs1_i,        -- rf source 1
      rs2_i   => rs2_i,        -- rf source 2
      -- result and status --
      res_o   => cp_result(1), -- operation result
      valid_o => cp_valid(1)   -- data output valid
    );
  end generate;

  neorv32_cpu_cp_muldiv_inst_false:
  if (not RISCV_ISA_M) and (not RISCV_ISA_Zmmul) generate
    cp_result(1) <= (others => '0');
    cp_valid(1)  <= '0';
  end generate;


  -- ALU[I]-Opcode Co-Processor: Bit-Manipulation Unit ('B' ISA Extension) ------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_cp_bitmanip_inst_true:
  if RISCV_ISA_Zba or RISCV_ISA_Zbb or RISCV_ISA_Zbkb or RISCV_ISA_Zbs or RISCV_ISA_Zbkc generate
    neorv32_cpu_cp_bitmanip_inst: entity neorv32.neorv32_cpu_cp_bitmanip
    generic map (
      EN_FAST_SHIFT => FAST_SHIFT_EN,  -- use barrel shifter for shift operations
      EN_ZBA        => RISCV_ISA_Zba,  -- enable address-generation instruction
      EN_ZBB        => RISCV_ISA_Zbb,  -- enable basic bit-manipulation instruction
      EN_ZBKB       => RISCV_ISA_Zbkb, -- enable bit-manipulation instructions for cryptography
      EN_ZBKC       => RISCV_ISA_Zbkc, -- enable carry-less multiplication instructions
      EN_ZBKX       => RISCV_ISA_Zbkx, -- crossbar permutation instructions for cryptography
      EN_ZBS        => RISCV_ISA_Zbs   -- enable single-bit instructions
    )
    port map (
      -- global control --
      clk_i   => clk_i,           -- global clock, rising edge
      rstn_i  => rstn_i,          -- global reset, low-active, async
      ctrl_i  => ctrl_i,          -- main control bus
      -- data input --
      less_i  => cmp_ls,          -- compare less
      rs1_i   => rs1_i,           -- rf source 1
      rs2_i   => rs2_i,           -- rf source 2
      shamt_i => opb(4 downto 0), -- shift amount
      -- result and status --
      res_o   => cp_result(2),    -- operation result
      valid_o => cp_valid(2)      -- data output valid
    );
  end generate;

  neorv32_cpu_cp_bitmanip_inst_false:
  if not (RISCV_ISA_Zba or RISCV_ISA_Zbb or RISCV_ISA_Zbkb or RISCV_ISA_Zbs or RISCV_ISA_Zbkc) generate
    cp_result(2) <= (others => '0');
    cp_valid(2)  <= '0';
  end generate;


  -- FLOAT-Opcode Co-Processor: Single-Precision FPUUnit ('Zfinx' ISA Extension) ------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_cp_fpu_inst_true:
  if RISCV_ISA_Zfinx generate
    neorv32_cpu_cp_fpu_inst: entity neorv32.neorv32_cpu_cp_fpu
    port map (
      -- global control --
      clk_i       => clk_i,                       -- global clock, rising edge
      rstn_i      => rstn_i,                      -- global reset, low-active, async
      ctrl_i      => ctrl_i,                      -- main control bus
      -- CSR interface --
      csr_we_i    => fpu_csr_we,                  -- write enable
      csr_addr_i  => ctrl_i.csr_addr(1 downto 0), -- address
      csr_wdata_i => ctrl_i.csr_wdata,            -- write data
      csr_rdata_o => fpu_csr_rd,                  -- read data
      -- data input --
      equal_i     => cmp_eq,                      -- compare equal
      less_i      => cmp_ls,                      -- compare less
      rs1_i       => rs1_i,                       -- rf source 1
      rs2_i       => rs2_i,                       -- rf source 2
      -- result and status --
      res_o       => cp_result(3),                -- operation result
      valid_o     => cp_valid(3)                  -- data output valid
    );

    -- CSR proxy --
    fpu_csr_en <= '1' when (ctrl_i.csr_addr(11 downto 2) = csr_fflags_c(11 downto 2)) else '0';
    fpu_csr_we <= fpu_csr_en and ctrl_i.csr_we;
    csr_o      <= fpu_csr_rd when (fpu_csr_en = '1') else (others => '0');
  end generate;

  neorv32_cpu_cp_fpu_inst_false:
  if not RISCV_ISA_Zfinx generate
    fpu_csr_en   <= '0';
    fpu_csr_we   <= '0';
    fpu_csr_rd   <= (others => '0');
    csr_o        <= (others => '0');
    cp_result(3) <= (others => '0');
    cp_valid(3)  <= '0';
  end generate;


  -- CUSTOM-Opcode Co-Processor: Custom Functions Unit ('Zxcfu' ISA Extension) --------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_cp_cfu_inst_true:
  if RISCV_ISA_Zxcfu generate
    neorv32_cpu_cp_cfu_inst: entity neorv32.neorv32_cpu_cp_cfu
    port map (
      -- global control --
      clk_i    => clk_i,                          -- global clock, rising edge
      rstn_i   => rstn_i,                         -- global reset, low-active, async
      -- operation trigger --
      start_i  => ctrl_i.alu_cp_cfu,              -- start trigger, single-shot
      -- operands --
      type_i   => ctrl_i.ir_opcode(5),            -- instruction type
      funct3_i => ctrl_i.ir_funct3,               -- "funct3" bit-field
      funct7_i => ctrl_i.ir_funct12(11 downto 5), -- "funct7" bit-field
      imm12_i  => ctrl_i.ir_funct12(11 downto 0), -- "imm12" bit-field
      rs1_i    => rs1_i,                          -- rf source 1
      rs2_i    => rs2_i,                          -- rf source 2
      -- result and status --
      result_o => cfu_res,                        -- operation result
      valid_o  => cfu_done                        -- result valid, operation done
    );

    -- response proxy --
    cfu_proxy: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        cfu_busy     <= '0';
        cp_result(4) <= (others => '0');
      elsif rising_edge(clk_i) then
        if (cfu_done = '1') or (ctrl_i.cpu_trap = '1') then -- terminate also on trap
          cfu_busy <= '0';
        elsif (ctrl_i.alu_cp_cfu = '1') then
          cfu_busy <= '1';
        end if;
        if (cp_valid(4) = '1') then
          cp_result(4) <= cfu_res;
        else -- output zero if there is no CFU operation
          cp_result(4) <= (others => '0');
        end if;
      end if;
    end process cfu_proxy;
    cp_valid(4) <= cfu_done and (ctrl_i.alu_cp_cfu or cfu_busy);
  end generate;

  neorv32_cpu_cp_cfu_inst_false:
  if not RISCV_ISA_Zxcfu generate
    cfu_done     <= '0';
    cfu_res      <= (others => '0');
    cfu_busy     <= '0';
    cp_result(4) <= (others => '0');
    cp_valid(4)  <= '0';
  end generate;


  -- ALU-Opcode Co-Processor: Conditional Operations Unit ('Zicond' ISA Extension) ----------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_cp_cond_inst_true:
  if RISCV_ISA_Zicond generate
    neorv32_cpu_cp_cond_inst: entity neorv32.neorv32_cpu_cp_cond
    port map (
      -- global control --
      clk_i   => clk_i,        -- global clock, rising edge
      rstn_i  => rstn_i,       -- global reset, low-active, async
      ctrl_i  => ctrl_i,       -- main control bus
      -- data input --
      rs1_i   => rs1_i,        -- rf source 1
      rs2_i   => rs2_i,        -- rf source 2
      -- result and status --
      res_o   => cp_result(5), -- operation result
      valid_o => cp_valid(5)   -- data output valid
    );
  end generate;

  neorv32_cpu_cp_cond_inst_false:
  if not RISCV_ISA_Zicond generate
    cp_result(5) <= (others => '0');
    cp_valid(5)  <= '0';
  end generate;


  -- ALU[I]-Opcode Co-Processor: Scalar Cryptography Unit ('Zk*' ISA Extensions) ------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_cp_crypto_inst_true:
  if RISCV_ISA_Zbkx or RISCV_ISA_Zknh or RISCV_ISA_Zkne or RISCV_ISA_Zknd or RISCV_ISA_Zksh or RISCV_ISA_Zksed generate
    neorv32_cpu_cp_crypto_inst: entity neorv32.neorv32_cpu_cp_crypto
    generic map (
      EN_ZKNH  => RISCV_ISA_Zknh,  -- enable NIST hash extension
      EN_ZKNE  => RISCV_ISA_Zkne,  -- enable NIST AES encryption extension
      EN_ZKND  => RISCV_ISA_Zknd,  -- enable NIST AES decryption extension
      EN_ZKSED => RISCV_ISA_Zksed, -- enable ShangMi block cypher extension
      EN_ZKSH  => RISCV_ISA_Zksh   -- enable ShangMi hash extension
    )
    port map (
      -- global control --
      clk_i   => clk_i,        -- global clock, rising edge
      rstn_i  => rstn_i,       -- global reset, low-active, async
      ctrl_i  => ctrl_i,       -- main control bus
      -- data input --
      rs1_i   => rs1_i,        -- rf source 1
      rs2_i   => rs2_i,        -- rf source 2
      -- result and status --
      res_o   => cp_result(6), -- operation result
      valid_o => cp_valid(6)   -- data output valid
    );
  end generate;

  neorv32_cpu_cp_crypto_inst_false:
  if not (RISCV_ISA_Zbkx or RISCV_ISA_Zknh or RISCV_ISA_Zkne or RISCV_ISA_Zknd or RISCV_ISA_Zksh or RISCV_ISA_Zksed) generate
    cp_result(6) <= (others => '0');
    cp_valid(6)  <= '0';
  end generate;


end neorv32_cpu_alu_rtl;
