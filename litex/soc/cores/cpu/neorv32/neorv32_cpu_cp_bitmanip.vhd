-- ================================================================================ --
-- NEORV32 CPU - Co-Processor: Bit Manipulation Unit (RISC-V "Zb*" ISA Extensions)  --
-- -------------------------------------------------------------------------------- --
-- Supported sub-extensions:                                                        --
-- + Zba:  Address-generation instructions                                          --
-- + Zbb:  Basic bit-manipulation instructions                                      --
-- + Zbs:  Single-bit instructions                                                  --
-- + Zbkb: Bit-manipulation instructions for cryptography                           --
-- + Zbkc: Carry-less multiplication instructions for cryptography                  --
-- + Zbkx: Crossbar permutation instructions for cryptography                       --
-- [NOTE] RISC-V "B" ISA Extension = Zba + Zbb + Zbs                                --
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

entity neorv32_cpu_cp_bitmanip is
  generic (
    EN_FAST_SHIFT : boolean; -- use barrel shifter for shift operations
    EN_ZBA        : boolean; -- address-generation instructions
    EN_ZBB        : boolean; -- basic bit-manipulation instructions
    EN_ZBKC       : boolean; -- carry-less multiplication instructions for cryptography
    EN_ZBKB       : boolean; -- bit-manipulation instructions for cryptography
    EN_ZBKX       : boolean; -- crossbar permutation instructions for cryptography
    EN_ZBS        : boolean  -- single-bit instructions
  );
  port (
    -- global control --
    clk_i   : in  std_ulogic; -- global clock, rising edge
    rstn_i  : in  std_ulogic; -- global reset, low-active, async
    ctrl_i  : in  ctrl_bus_t; -- main control bus
    -- data input --
    less_i  : in  std_ulogic;                     -- compare less
    rs1_i   : in  std_ulogic_vector(31 downto 0); -- rf source 1
    rs2_i   : in  std_ulogic_vector(31 downto 0); -- rf source 2
    shamt_i : in  std_ulogic_vector(4 downto 0);  -- shift amount
    -- result and status --
    res_o   : out std_ulogic_vector(31 downto 0); -- operation result
    valid_o : out std_ulogic                      -- data output valid
  );
end neorv32_cpu_cp_bitmanip;

architecture neorv32_cpu_cp_bitmanip_rtl of neorv32_cpu_cp_bitmanip is

  -- count leading zeros --
  function leading_zeros_f(input : std_ulogic_vector) return natural is
    variable cnt_v : natural range 0 to input'length;
  begin
    cnt_v := 0;
    for i in input'length-1 downto 0 loop
      if (input(i) = '0') then
        cnt_v := cnt_v + 1;
      else
        exit;
      end if;
    end loop;
    return cnt_v;
  end function leading_zeros_f;

  -- population count (number of set bits) --
  function popcount_f(input : std_ulogic_vector) return natural is
    variable cnt_v : natural range 0 to input'length;
  begin
    cnt_v := 0;
    for i in 0 to input'length-1 loop
      if (input(i) = '1') then
        cnt_v := cnt_v + 1;
      end if;
    end loop;
    return cnt_v;
  end function popcount_f;

  -- byte-wise vector look-up --
  function xperm8_f(vec : std_ulogic_vector(31 downto 0); sel : std_ulogic_vector(7 downto 0)) return std_ulogic_vector is
    variable res_v : std_ulogic_vector(7 downto 0);
  begin
    if (sel(7 downto 2) /= "000000") then -- index out of range
      res_v := (others => '0');
    else
      case sel(1 downto 0) is
        when "00"   => res_v := vec(7 downto 0);
        when "01"   => res_v := vec(15 downto 8);
        when "10"   => res_v := vec(23 downto 16);
        when others => res_v := vec(31 downto 24);
      end case;
    end if;
    return res_v;
  end function xperm8_f;

  -- nibble-wise vector look-up --
  function xperm4_f(vec : std_ulogic_vector(31 downto 0); sel : std_ulogic_vector(3 downto 0)) return std_ulogic_vector is
    variable res_v : std_ulogic_vector(3 downto 0);
  begin
    if (sel(3) /= '0') then -- index out of range
      res_v := (others => '0');
    else
      case sel(2 downto 0) is
        when "000"  => res_v := vec(3 downto 0);
        when "001"  => res_v := vec(7 downto 4);
        when "010"  => res_v := vec(11 downto 8);
        when "011"  => res_v := vec(15 downto 12);
        when "100"  => res_v := vec(19 downto 16);
        when "101"  => res_v := vec(23 downto 20);
        when "110"  => res_v := vec(27 downto 24);
        when others => res_v := vec(31 downto 28);
      end case;
    end if;
    return res_v;
  end function xperm4_f;

  -- instruction select (one-hot) --
  constant op_andn_c  : natural := 0;  -- logic with negate
  constant op_orn_c   : natural := 1;  -- logic with negate
  constant op_xnor_c  : natural := 2;  -- logic with negate
  constant op_cz_c    : natural := 3;  -- count leading/trailing zeros
  constant op_cpop_c  : natural := 4;  -- count population
  constant op_max_c   : natural := 5;  -- signed/unsigned minimum/maximum
  constant op_sext_c  : natural := 6;  -- sign extension
  constant op_zexth_c : natural := 7;  -- zero extension
  constant op_rot_c   : natural := 8;  -- bit-wise rotation
  constant op_orcb_c  : natural := 9;  -- or-combine
  constant op_rev8_c  : natural := 10; -- byte-reverse
  constant op_shadd_c : natural := 11; -- shifted-add
  constant op_bclr_c  : natural := 12; -- single bit clear
  constant op_bext_c  : natural := 13; -- single bit extract
  constant op_binv_c  : natural := 14; -- single bit invert
  constant op_bset_c  : natural := 15; -- single bit set
  constant op_pack_c  : natural := 16; -- pack bytes/halves
  constant op_zip_c   : natural := 17; -- (de)interleave
  constant op_brev8_c : natural := 18; -- byte-wise bit-reverse
  constant op_clmul_c : natural := 19; -- carry-less multiplication
  constant op_xperm_c : natural := 20; -- crossbar permutation
  constant op_width_c : natural := 21;

  -- controller --
  type ctrl_state_t is (S_IDLE, S_START, S_BUSY);
  signal ctrl_state : ctrl_state_t;
  signal valid_cmd  : std_ulogic;
  signal cmd        : std_ulogic_vector(op_width_c-1 downto 0);
  signal valid      : std_ulogic;

  -- operand buffers --
  signal rs1_reg  : std_ulogic_vector(31 downto 0);
  signal rs2_reg  : std_ulogic_vector(31 downto 0);
  signal sha_reg  : std_ulogic_vector(4 downto 0);
  signal less_reg : std_ulogic;

  -- serial shifter --
  type shifter_t is record
    start   : std_ulogic;
    run     : std_ulogic;
    nxt     : std_ulogic;
    bcnt    : std_ulogic_vector(5 downto 0); -- bit counter
    cnt     : std_ulogic_vector(5 downto 0); -- iteration counter
    cnt_max : std_ulogic_vector(5 downto 0);
    sreg    : std_ulogic_vector(31 downto 0);
  end record;
  signal shifter : shifter_t;

  -- serial carry-less multiplier --
  type clmul_t is record
    start : std_ulogic;
    run   : std_ulogic;
    cnt   : std_ulogic_vector(5 downto 0);
    res   : std_ulogic_vector(63 downto 0);
  end record;
  signal clmul : clmul_t;

  -- barrel shifter --
  type bs_level_t is array (5 downto 0) of std_ulogic_vector(31 downto 0);
  signal bs_level : bs_level_t;
  signal bs_shift : std_ulogic_vector(4 downto 0);

  -- operation/intermediate results --
  type res_t is array (0 to op_width_c-1) of std_ulogic_vector(31 downto 0);
  signal res_int, res_out : res_t;
  signal xperm4_res, xperm8_res, adder_res, one_hot_res, zip_res, unzip_res : std_ulogic_vector(31 downto 0);

begin

  -- Instruction Decoding -------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- Zbb - Basic bit-manipulation instructions --
  cmd(op_andn_c)  <= '1' when (EN_ZBB or EN_ZBKB) and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct12(11 downto 5) = "0100000") and (ctrl_i.ir_funct3 = "111") else '0'; -- ANDN
  cmd(op_orn_c)   <= '1' when (EN_ZBB or EN_ZBKB) and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct12(11 downto 5) = "0100000") and (ctrl_i.ir_funct3 = "110") else '0'; -- ORN
  cmd(op_xnor_c)  <= '1' when (EN_ZBB or EN_ZBKB) and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct12(11 downto 5) = "0100000") and (ctrl_i.ir_funct3 = "100") else '0'; -- XORN
  cmd(op_max_c)   <= '1' when (EN_ZBB or EN_ZBKB) and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct12(11 downto 5) = "0000101") and (ctrl_i.ir_funct3(2) = '1') else '0'; -- MAX[U], MIN[U]
  cmd(op_zexth_c) <= '1' when (EN_ZBB or EN_ZBKB) and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct12 = "000010000000") and (ctrl_i.ir_funct3 = "100") else '0'; -- ZEXT.H
  cmd(op_orcb_c)  <= '1' when (EN_ZBB or EN_ZBKB) and (ctrl_i.ir_opcode(5) = '0') and (ctrl_i.ir_funct12 = "001010000111") and (ctrl_i.ir_funct3 = "101") else '0'; -- ORC.B
  cmd(op_cz_c)    <= '1' when (EN_ZBB or EN_ZBKB) and (ctrl_i.ir_opcode(5) = '0') and (ctrl_i.ir_funct12(11 downto 1) = "01100000000") and (ctrl_i.ir_funct3 = "001") else '0'; -- CLZ, CTZ
  cmd(op_cpop_c)  <= '1' when (EN_ZBB or EN_ZBKB) and (ctrl_i.ir_opcode(5) = '0') and (ctrl_i.ir_funct12 = "011000000010") and (ctrl_i.ir_funct3 = "001") else '0'; -- CPOP
  cmd(op_sext_c)  <= '1' when (EN_ZBB or EN_ZBKB) and (ctrl_i.ir_opcode(5) = '0') and (ctrl_i.ir_funct12(11 downto 1) = "01100000010") and (ctrl_i.ir_funct3 = "001") else '0';
  cmd(op_rev8_c)  <= '1' when (EN_ZBB or EN_ZBKB) and (ctrl_i.ir_opcode(5) = '0') and (ctrl_i.ir_funct12 = "011010011000") and (ctrl_i.ir_funct3 = "101") else '0';
  cmd(op_rot_c)   <= '1' when (EN_ZBB or EN_ZBKB) and (ctrl_i.ir_funct12(11 downto 5) = "0110000") and
                                                      (((ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct3 = "001")) or (ctrl_i.ir_funct3 = "101")) else '0'; -- ROL, ROR[I]

  -- Zba - Address generation instructions --
  cmd(op_shadd_c) <= '1' when EN_ZBA and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct12(11 downto 5) = "0010000") and
                                         ((ctrl_i.ir_funct3 = "010") or (ctrl_i.ir_funct3 = "100") or (ctrl_i.ir_funct3 = "110")) else '0'; -- SH[1,2,3]ADD

  -- Zbs - Single-bit instructions --
  cmd(op_bclr_c)  <= '1' when EN_ZBS and (ctrl_i.ir_funct12(11 downto 5) = "0100100") and (ctrl_i.ir_funct3 = "001") else '0'; -- BCLR[I]
  cmd(op_bext_c)  <= '1' when EN_ZBS and (ctrl_i.ir_funct12(11 downto 5) = "0100100") and (ctrl_i.ir_funct3 = "101") else '0'; -- BEXT[I]
  cmd(op_binv_c)  <= '1' when EN_ZBS and (ctrl_i.ir_funct12(11 downto 5) = "0110100") and (ctrl_i.ir_funct3 = "001") else '0'; -- BINV[I]
  cmd(op_bset_c)  <= '1' when EN_ZBS and (ctrl_i.ir_funct12(11 downto 5) = "0010100") and (ctrl_i.ir_funct3 = "001") else '0'; -- BSET[I]

  -- Zbkb - Additional bit-manipulation instruction for cryptography (extending Zbb) --
  cmd(op_pack_c)  <= '1' when EN_ZBKB and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct12(11 downto 5) = "0000100") and ((ctrl_i.ir_funct3 = "100") or (ctrl_i.ir_funct3 = "111")) else '0'; -- PACK[H]
  cmd(op_zip_c)   <= '1' when EN_ZBKB and (ctrl_i.ir_opcode(5) = '0') and (ctrl_i.ir_funct12 = "000010001111") and ((ctrl_i.ir_funct3 = "001") or (ctrl_i.ir_funct3 = "101")) else '0'; -- [UN]ZIP
  cmd(op_brev8_c) <= '1' when EN_ZBKB and (ctrl_i.ir_opcode(5) = '0') and (ctrl_i.ir_funct12 = "011010000111") and (ctrl_i.ir_funct3 = "101") else '0'; -- BREV8

  -- Zbkc - Carry-less multiplication instructions --
  cmd(op_clmul_c) <= '1' when EN_ZBKC and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct12(11 downto 5) = "0000101") and (ctrl_i.ir_funct3(2) = '0') and (ctrl_i.ir_funct3(0) = '1') else '0'; -- CLMUL[H]

  -- Zbkx - Crossbar permutations --
  cmd(op_xperm_c) <= '1' when EN_ZBKX and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct12(11 downto 5) = "0010100") and ((ctrl_i.ir_funct3 = "100") or (ctrl_i.ir_funct3 = "010")) else '0'; -- XPERM[4/8]

  -- Valid Instruction? --
  valid_cmd <= '1' when (ctrl_i.alu_cp_alu = '1') and (or_reduce_f(cmd) = '1') else '0';


  -- Co-Processor Controller ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  controller: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ctrl_state    <= S_IDLE;
      rs1_reg       <= (others => '0');
      rs2_reg       <= (others => '0');
      sha_reg       <= (others => '0');
      less_reg      <= '0';
      shifter.start <= '0';
      clmul.start   <= '0';
      valid         <= '0';
    elsif rising_edge(clk_i) then
      -- defaults --
      shifter.start <= '0';
      clmul.start   <= '0';
      valid         <= '0';

      -- operand gating / buffering --
      if (ctrl_i.alu_cp_alu = '1') then
        less_reg <= less_i;
        rs1_reg  <= rs1_i;
        rs2_reg  <= rs2_i;
        sha_reg  <= shamt_i;
      end if;

      -- fsm --
      case ctrl_state is

        when S_IDLE => -- wait for operation trigger
        -- ------------------------------------------------------------
          if (valid_cmd = '1') then
            if (not EN_FAST_SHIFT) and ((cmd(op_cz_c) or cmd(op_cpop_c) or cmd(op_rot_c)) = '1') then -- multi-cycle shift operation
              shifter.start <= '1';
              ctrl_state    <= S_START;
            elsif (cmd(op_clmul_c) = '1') then -- multi-cycle carry-less multiplication operation
              clmul.start <= '1';
              ctrl_state  <= S_START;
            else
              valid      <= '1';
              ctrl_state <= S_IDLE;
            end if;
          end if;

        when S_START => -- one cycle delay to start iterative operation
        -- ------------------------------------------------------------
          ctrl_state <= S_BUSY;

        when others => -- S_BUSY: wait for multi-cycle operation to finish
        -- ------------------------------------------------------------
          if ((shifter.run = '0') and (clmul.run = '0')) or (ctrl_i.cpu_trap = '1') then -- abort on trap
            valid      <= '1';
            ctrl_state <= S_IDLE;
          end if;

      end case;
    end if;
  end process controller;


  -- Shifter Function Core (iterative: small but slow) --------------------------------------
  -- -------------------------------------------------------------------------------------------
  serial_shifter:
  if not EN_FAST_SHIFT generate

    serial_shifter_core: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        shifter.cnt     <= (others => '0');
        shifter.sreg    <= (others => '0');
        shifter.cnt_max <= (others => '0');
        shifter.bcnt    <= (others => '0');
      elsif rising_edge(clk_i) then
        if (shifter.start = '1') then -- trigger new shift
          shifter.cnt  <= (others => '0');
          shifter.sreg <= rs1_reg;
          if (cmd(op_cpop_c) = '1') then -- population count
            shifter.cnt_max <= std_ulogic_vector(to_unsigned(32, shifter.cnt_max'length));
          else
            shifter.cnt_max <= '0' & shamt_i;
          end if;
          shifter.bcnt <= (others => '0');
        elsif (shifter.run = '1') then
          if ((cmd(op_rot_c) = '1') and (ctrl_i.ir_funct3(2) = '0')) or -- rol
             ((cmd(op_cz_c) = '1') and (ctrl_i.ir_funct12(0) = '0')) then -- ctz
            shifter.sreg <= shifter.sreg(shifter.sreg'left-1 downto 0) & shifter.nxt; -- left-shift
          else
            shifter.sreg <= shifter.nxt & shifter.sreg(shifter.sreg'left downto 1); -- right-shift
          end if;
          shifter.cnt <= std_ulogic_vector(unsigned(shifter.cnt) + 1); -- iteration counter
          if (shifter.sreg(0) = '1') then
            shifter.bcnt <= std_ulogic_vector(unsigned(shifter.bcnt) + 1); -- set-bits counter
          end if;
        end if;
      end if;
    end process serial_shifter_core;

    -- shifted-in bit --
    shifter.nxt <= '1' when (cmd(op_cz_c) = '1') else -- count zeros
                   shifter.sreg(0) when (ctrl_i.ir_funct3(2) = '1') else -- right shift
                   shifter.sreg(31); -- left shift

    -- run control --
    serial_shifter_ctrl: process(cmd, ctrl_i, shifter)
    begin
      -- keep shifting until all bits are processed --
      if (cmd(op_cz_c) = '1') then -- count zeros
        if (ctrl_i.ir_funct12(0) = '0') then -- leading zeros
          shifter.run <= not shifter.sreg(31);
        else -- trailing zeros
          shifter.run <= not shifter.sreg(0);
        end if;
      else -- population count / rotate
        if (shifter.cnt = shifter.cnt_max) then
          shifter.run <= '0';
        else
          shifter.run <= '1';
        end if;
      end if;
    end process serial_shifter_ctrl;

  end generate;


  -- Shifter Function Core (parallel: fast but large) ---------------------------------------
  -- -------------------------------------------------------------------------------------------
  barrel_shifter:
  if EN_FAST_SHIFT generate

    -- rotator input layer: convert left-rotates to right-rotates (rotate by 32 - N positions) --
    bs_shift <= std_ulogic_vector(unsigned(not sha_reg) + 1) when (ctrl_i.ir_funct3(2) = '0') else sha_reg;

    -- rotator mux layers: right-rotates only --
    bs_level(0) <= rs1_reg;
    barrel_shifter_core:
    for i in 0 to 4 generate
      bs_level(i+1)(31 downto 32-(2**i))    <= bs_level(i)((2**i)-1 downto 0) when (bs_shift(i) = '1') else bs_level(i)(31 downto 32-(2**i));
      bs_level(i+1)((32-(2**i))-1 downto 0) <= bs_level(i)(31 downto 2**i)    when (bs_shift(i) = '1') else bs_level(i)((32-(2**i))-1 downto 0);
    end generate;
    shifter.sreg <= bs_level(bs_level'left); -- rol/ror[i]

    -- population count --
    shifter.bcnt <= std_ulogic_vector(to_unsigned(popcount_f(rs1_reg), shifter.bcnt'length)); -- cpop

    -- count leading/trailing zeros --
    shifter.cnt <= std_ulogic_vector(to_unsigned(leading_zeros_f(rs1_reg), shifter.cnt'length)) when (ctrl_i.ir_funct12(0) = '0') else -- clz
                   std_ulogic_vector(to_unsigned(leading_zeros_f(bit_rev_f(rs1_reg)), shifter.cnt'length)); -- ctz

    -- unused --
    shifter.run     <= '0';
    shifter.nxt     <= '0';
    shifter.cnt_max <= (others => '0');

  end generate;


  -- Shifted-Add ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  shift_adder: process(rs1_reg, rs2_reg, ctrl_i)
    variable tmp_v : std_ulogic_vector(31 downto 0);
  begin
    case ctrl_i.ir_funct3(2 downto 1) is
      when "01"   => tmp_v := rs1_reg(rs1_reg'left-1 downto 0) & '0';   -- << 1
      when "10"   => tmp_v := rs1_reg(rs1_reg'left-2 downto 0) & "00";  -- << 2
      when others => tmp_v := rs1_reg(rs1_reg'left-3 downto 0) & "000"; -- << 3
    end case;
    adder_res <= std_ulogic_vector(unsigned(rs2_reg) + unsigned(tmp_v));
  end process shift_adder;


  -- One-Hot Generator ----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  shift_one_hot: process(sha_reg)
  begin
    one_hot_res <= (others => '0');
    one_hot_res(to_integer(unsigned(sha_reg))) <= '1';
  end process shift_one_hot;


  -- Carry-Less Multiplier ------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  clmul_enable:
  if EN_ZBKC generate

    clmul_core: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        clmul.cnt <= (others => '0');
        clmul.res <= (others => '0');
      elsif rising_edge(clk_i) then
        if (clmul.start = '1') then -- start new multiplication
          clmul.cnt <= std_ulogic_vector(to_unsigned(32, clmul.cnt'length));
          clmul.res <= replicate_f('0', 32) & rs1_reg;
        elsif (clmul.run = '1') then -- operation in progress
          clmul.cnt <= std_ulogic_vector(unsigned(clmul.cnt) - 1);
          if (clmul.res(0) = '1') then
            clmul.res(62 downto 31) <= clmul.res(63 downto 32) xor rs2_reg;
          else
            clmul.res(62 downto 31) <= clmul.res(63 downto 32);
          end if;
          clmul.res(30 downto 0) <= clmul.res(31 downto 1);
        end if;
      end if;
    end process clmul_core;

    -- operation in progress --
    clmul.run <= '1' when (or_reduce_f(clmul.cnt) = '1') else '0';

  end generate;

  clmul_disable:
  if not EN_ZBKC generate
    clmul.cnt <= (others => '0');
    clmul.res <= (others => '0');
    clmul.run <= '0';
  end generate;


  -- Crossbar Permutations ------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  xperm_enable:
  if EN_ZBKX generate

    -- byte-wise vector look-up --
    xperm8_gen:
    for i in 0 to 3 generate
      xperm8_res(8*i+7 downto 8*i+0) <= xperm8_f(rs1_reg, rs2_reg(8*i+7 downto 8*i+0));
    end generate;

    -- nibble-wise vector look-up --
    xperm4_gen:
    for i in 0 to 7 generate
      xperm4_res(4*i+3 downto 4*i+0) <= xperm4_f(rs1_reg, rs2_reg(4*i+3 downto 4*i+0));
    end generate;

  end generate;

  xperm_disable:
  if not EN_ZBKX generate
    xperm8_res <= (others => '0');
    xperm4_res <= (others => '0');
  end generate;


  -- Operation Results ----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- logic with negate --
  res_int(op_andn_c) <= rs1_reg and (not rs2_reg);
  res_int(op_orn_c)  <= rs1_reg or  (not rs2_reg);
  res_int(op_xnor_c) <= rs1_reg xor (not rs2_reg);

  -- count leading/trailing zeros --
  res_int(op_cz_c)(31 downto shifter.cnt'left+1) <= (others => '0');
  res_int(op_cz_c)(shifter.cnt'left downto 0) <= shifter.cnt;

  -- population count --
  res_int(op_cpop_c)(31 downto shifter.bcnt'left+1) <= (others => '0');
  res_int(op_cpop_c)(shifter.bcnt'left downto 0) <= shifter.bcnt;

  -- min/max select --
  res_int(op_max_c) <= rs1_reg when ((less_reg xor ctrl_i.ir_funct3(1)) = '1') else rs2_reg;

  -- sign-extension --
  res_int(op_sext_c)(31 downto 16) <= (others => rs1_reg(15)) when (ctrl_i.ir_funct12(0) = '1') else (others => rs1_reg(7));
  res_int(op_sext_c)(15 downto 8)  <= rs1_reg(15 downto 8)    when (ctrl_i.ir_funct12(0) = '1') else (others => rs1_reg(7));
  res_int(op_sext_c)(7 downto 0)   <= rs1_reg(7 downto 0);

  -- zero-extension --
  res_int(op_zexth_c)(31 downto 16) <= (others => '0');
  res_int(op_zexth_c)(15 downto 0)  <= rs1_reg(15 downto 0);

  -- rotate right/left --
  res_int(op_rot_c) <= shifter.sreg;

  -- or-combine.byte --
  or_combine_gen:
  for i in 0 to 3 generate -- byte loop
    res_int(op_orcb_c)(i*8+7 downto i*8) <= (others => or_reduce_f(rs1_reg(i*8+7 downto i*8)));
  end generate;

  -- reversal.8 (byte swap) --
  byte_swap_gen:
  for i in 0 to 3 generate -- byte loop
    res_int(op_rev8_c)(i*8+7 downto i*8) <= rs1_reg((32-i*8)-1 downto 32-(i+1)*8);
  end generate;

  -- address generation instructions --
  res_int(op_shadd_c) <= adder_res;

  -- single-bit instructions --
  res_int(op_bclr_c) <= rs1_reg and (not one_hot_res);
  res_int(op_bext_c)(31 downto 1) <= (others => '0');
  res_int(op_bext_c)(0) <= '1' when (or_reduce_f(rs1_reg and one_hot_res) = '1') else '0';
  res_int(op_binv_c) <= rs1_reg xor one_hot_res;
  res_int(op_bset_c) <= rs1_reg or one_hot_res;

  -- pack --
  res_int(op_pack_c) <= rs2_reg(15 downto 0) & rs1_reg(15 downto 0) when (ctrl_i.ir_funct3(0) = '0') else
                        replicate_f('0', 16) & rs2_reg(7 downto 0) & rs1_reg(7 downto 0);

  -- zip/unzip --
  interleave_gen:
  for i in 0 to 15 generate
    zip_res(2*i+0)  <= rs1_reg(i);
    zip_res(2*i+1)  <= rs1_reg(16+i);
    unzip_res(i)    <= rs1_reg(2*i);
    unzip_res(16+i) <= rs1_reg(2*i+1);
  end generate;
  res_int(op_zip_c) <= zip_res when (ctrl_i.ir_funct3(2) = '0') else unzip_res;

  -- byte-wise bit-reversal --
  brev_gen:
  for i in 0 to 3 generate -- byte loop
    res_int(op_brev8_c)(i*8+7 downto i*8) <= bit_rev_f(rs1_reg(i*8+7 downto i*8));
  end generate;

  -- carry-less multiplication --
  res_int(op_clmul_c) <= clmul.res(63 downto 32) when (ctrl_i.ir_funct3(1) = '1') else clmul.res(31 downto 0);

  -- crossbar permutation --
  res_int(op_xperm_c) <= xperm8_res when (ctrl_i.ir_funct3(2) = '1') else xperm4_res;


  -- Output Select --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  res_out(op_andn_c)  <= res_int(op_andn_c)  when (EN_ZBB or EN_ZBKB) and (cmd(op_andn_c)  = '1') else (others => '0');
  res_out(op_orn_c)   <= res_int(op_orn_c)   when (EN_ZBB or EN_ZBKB) and (cmd(op_orn_c)   = '1') else (others => '0');
  res_out(op_xnor_c)  <= res_int(op_xnor_c)  when (EN_ZBB or EN_ZBKB) and (cmd(op_xnor_c)  = '1') else (others => '0');
  res_out(op_cz_c)    <= res_int(op_cz_c)    when (EN_ZBB or EN_ZBKB) and (cmd(op_cz_c)    = '1') else (others => '0');
  res_out(op_cpop_c)  <= res_int(op_cpop_c)  when (EN_ZBB or EN_ZBKB) and (cmd(op_cpop_c)  = '1') else (others => '0');
  res_out(op_max_c)   <= res_int(op_max_c)   when (EN_ZBB or EN_ZBKB) and (cmd(op_max_c)   = '1') else (others => '0');
  res_out(op_sext_c)  <= res_int(op_sext_c)  when (EN_ZBB or EN_ZBKB) and (cmd(op_sext_c)  = '1') else (others => '0');
  res_out(op_zexth_c) <= res_int(op_zexth_c) when (EN_ZBB or EN_ZBKB) and (cmd(op_zexth_c) = '1') else (others => '0');
  res_out(op_rot_c)   <= res_int(op_rot_c)   when (EN_ZBB or EN_ZBKB) and (cmd(op_rot_c)   = '1') else (others => '0');
  res_out(op_orcb_c)  <= res_int(op_orcb_c)  when (EN_ZBB or EN_ZBKB) and (cmd(op_orcb_c)  = '1') else (others => '0');
  res_out(op_rev8_c)  <= res_int(op_rev8_c)  when (EN_ZBB or EN_ZBKB) and (cmd(op_rev8_c)  = '1') else (others => '0');
  res_out(op_shadd_c) <= res_int(op_shadd_c) when EN_ZBA              and (cmd(op_shadd_c) = '1') else (others => '0');
  res_out(op_bclr_c)  <= res_int(op_bclr_c)  when EN_ZBS              and (cmd(op_bclr_c)  = '1') else (others => '0');
  res_out(op_bext_c)  <= res_int(op_bext_c)  when EN_ZBS              and (cmd(op_bext_c)  = '1') else (others => '0');
  res_out(op_binv_c)  <= res_int(op_binv_c)  when EN_ZBS              and (cmd(op_binv_c)  = '1') else (others => '0');
  res_out(op_bset_c)  <= res_int(op_bset_c)  when EN_ZBS              and (cmd(op_bset_c)  = '1') else (others => '0');
  res_out(op_pack_c)  <= res_int(op_pack_c)  when EN_ZBKB             and (cmd(op_pack_c)  = '1') else (others => '0');
  res_out(op_zip_c)   <= res_int(op_zip_c)   when EN_ZBKB             and (cmd(op_zip_c)   = '1') else (others => '0');
  res_out(op_brev8_c) <= res_int(op_brev8_c) when EN_ZBKB             and (cmd(op_brev8_c) = '1') else (others => '0');
  res_out(op_clmul_c) <= res_int(op_clmul_c) when EN_ZBKC             and (cmd(op_clmul_c) = '1') else (others => '0');
  res_out(op_xperm_c) <= res_int(op_xperm_c) when EN_ZBKX             and (cmd(op_xperm_c) = '1') else (others => '0');


  -- Output Gate ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  output_gate: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      res_o <= (others => '0');
    elsif rising_edge(clk_i) then
      res_o <= (others => '0');
      if (valid = '1') then
        res_o <= res_out(op_andn_c)  or res_out(op_orn_c)   or res_out(op_xnor_c)  or
                 res_out(op_cz_c)    or res_out(op_cpop_c)  or res_out(op_max_c)   or
                 res_out(op_sext_c)  or res_out(op_zexth_c) or res_out(op_rot_c)   or
                 res_out(op_orcb_c)  or res_out(op_rev8_c)  or res_out(op_shadd_c) or
                 res_out(op_bclr_c)  or res_out(op_bext_c)  or res_out(op_binv_c)  or
                 res_out(op_bset_c)  or res_out(op_pack_c)  or res_out(op_zip_c)   or
                 res_out(op_brev8_c) or res_out(op_clmul_c) or res_out(op_xperm_c);
      end if;
    end if;
  end process output_gate;

  -- valid output --
  valid_o <= valid;


end neorv32_cpu_cp_bitmanip_rtl;
