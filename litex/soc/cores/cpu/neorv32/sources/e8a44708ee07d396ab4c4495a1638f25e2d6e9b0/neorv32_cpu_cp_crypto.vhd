-- ================================================================================ --
-- NEORV32 CPU - Co-Processor: RISC-V Scalar Cryptography ('Zk*') ISA Extensions    --
-- -------------------------------------------------------------------------------- --
-- Supported sub-extensions:                                                        --
-- + Zknh:  NIST suite's hash functions                                             --
-- + Zkne:  NIST suite's AES encryption                                             --
-- + Zknd:  NIST suite's AES decryption                                             --
-- + Zksed: ShangMi suite's block cyphers                                           --
-- + Zksh:  ShangMi suite's hash functions                                          --
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

entity neorv32_cpu_cp_crypto is
  generic (
    EN_ZKNH  : boolean; -- enable NIST hash extension
    EN_ZKNE  : boolean; -- enable NIST AES encryption extension
    EN_ZKND  : boolean; -- enable NIST AES decryption extension
    EN_ZKSED : boolean; -- enable ShangMi block cypher extension
    EN_ZKSH  : boolean  -- enable ShangMi hash extension
  );
  port (
    -- global control --
    clk_i   : in  std_ulogic; -- global clock, rising edge
    rstn_i  : in  std_ulogic; -- global reset, low-active, async
    ctrl_i  : in  ctrl_bus_t; -- main control bus
    -- data input --
    rs1_i   : in  std_ulogic_vector(31 downto 0); -- rf source 1
    rs2_i   : in  std_ulogic_vector(31 downto 0); -- rf source 2
    -- result and status --
    res_o   : out std_ulogic_vector(31 downto 0); -- operation result
    valid_o : out std_ulogic                      -- data output valid
  );
end neorv32_cpu_cp_crypto;

architecture neorv32_cpu_cp_crypto_rtl of neorv32_cpu_cp_crypto is

  -- ----------------------------------------------------------------------------------------
  -- look-up tables (ROMs)
  -- ----------------------------------------------------------------------------------------

  type rom512x8_t is array (0 to 511) of std_ulogic_vector(7 downto 0);
  type rom256x8_t is array (0 to 255) of std_ulogic_vector(7 downto 0);

  -- AES s-box --
  constant aes_sbox_c : rom512x8_t := (
    -- forward --
    x"63", x"7C", x"77", x"7B", x"F2", x"6B", x"6F", x"C5", x"30", x"01", x"67", x"2B", x"FE", x"D7", x"AB", x"76",
    x"CA", x"82", x"C9", x"7D", x"FA", x"59", x"47", x"F0", x"AD", x"D4", x"A2", x"AF", x"9C", x"A4", x"72", x"C0",
    x"B7", x"FD", x"93", x"26", x"36", x"3F", x"F7", x"CC", x"34", x"A5", x"E5", x"F1", x"71", x"D8", x"31", x"15",
    x"04", x"C7", x"23", x"C3", x"18", x"96", x"05", x"9A", x"07", x"12", x"80", x"E2", x"EB", x"27", x"B2", x"75",
    x"09", x"83", x"2C", x"1A", x"1B", x"6E", x"5A", x"A0", x"52", x"3B", x"D6", x"B3", x"29", x"E3", x"2F", x"84",
    x"53", x"D1", x"00", x"ED", x"20", x"FC", x"B1", x"5B", x"6A", x"CB", x"BE", x"39", x"4A", x"4C", x"58", x"CF",
    x"D0", x"EF", x"AA", x"FB", x"43", x"4D", x"33", x"85", x"45", x"F9", x"02", x"7F", x"50", x"3C", x"9F", x"A8",
    x"51", x"A3", x"40", x"8F", x"92", x"9D", x"38", x"F5", x"BC", x"B6", x"DA", x"21", x"10", x"FF", x"F3", x"D2",
    x"CD", x"0C", x"13", x"EC", x"5F", x"97", x"44", x"17", x"C4", x"A7", x"7E", x"3D", x"64", x"5D", x"19", x"73",
    x"60", x"81", x"4F", x"DC", x"22", x"2A", x"90", x"88", x"46", x"EE", x"B8", x"14", x"DE", x"5E", x"0B", x"DB",
    x"E0", x"32", x"3A", x"0A", x"49", x"06", x"24", x"5C", x"C2", x"D3", x"AC", x"62", x"91", x"95", x"E4", x"79",
    x"E7", x"C8", x"37", x"6D", x"8D", x"D5", x"4E", x"A9", x"6C", x"56", x"F4", x"EA", x"65", x"7A", x"AE", x"08",
    x"BA", x"78", x"25", x"2E", x"1C", x"A6", x"B4", x"C6", x"E8", x"DD", x"74", x"1F", x"4B", x"BD", x"8B", x"8A",
    x"70", x"3E", x"B5", x"66", x"48", x"03", x"F6", x"0E", x"61", x"35", x"57", x"B9", x"86", x"C1", x"1D", x"9E",
    x"E1", x"F8", x"98", x"11", x"69", x"D9", x"8E", x"94", x"9B", x"1E", x"87", x"E9", x"CE", x"55", x"28", x"DF",
    x"8C", x"A1", x"89", x"0D", x"BF", x"E6", x"42", x"68", x"41", x"99", x"2D", x"0F", x"B0", x"54", x"BB", x"16",
    -- inverse --
    x"52", x"09", x"6A", x"D5", x"30", x"36", x"A5", x"38", x"BF", x"40", x"A3", x"9E", x"81", x"F3", x"D7", x"FB",
    x"7C", x"E3", x"39", x"82", x"9B", x"2F", x"FF", x"87", x"34", x"8E", x"43", x"44", x"C4", x"DE", x"E9", x"CB",
    x"54", x"7B", x"94", x"32", x"A6", x"C2", x"23", x"3D", x"EE", x"4C", x"95", x"0B", x"42", x"FA", x"C3", x"4E",
    x"08", x"2E", x"A1", x"66", x"28", x"D9", x"24", x"B2", x"76", x"5B", x"A2", x"49", x"6D", x"8B", x"D1", x"25",
    x"72", x"F8", x"F6", x"64", x"86", x"68", x"98", x"16", x"D4", x"A4", x"5C", x"CC", x"5D", x"65", x"B6", x"92",
    x"6C", x"70", x"48", x"50", x"FD", x"ED", x"B9", x"DA", x"5E", x"15", x"46", x"57", x"A7", x"8D", x"9D", x"84",
    x"90", x"D8", x"AB", x"00", x"8C", x"BC", x"D3", x"0A", x"F7", x"E4", x"58", x"05", x"B8", x"B3", x"45", x"06",
    x"D0", x"2C", x"1E", x"8F", x"CA", x"3F", x"0F", x"02", x"C1", x"AF", x"BD", x"03", x"01", x"13", x"8A", x"6B",
    x"3A", x"91", x"11", x"41", x"4F", x"67", x"DC", x"EA", x"97", x"F2", x"CF", x"CE", x"F0", x"B4", x"E6", x"73",
    x"96", x"AC", x"74", x"22", x"E7", x"AD", x"35", x"85", x"E2", x"F9", x"37", x"E8", x"1C", x"75", x"DF", x"6E",
    x"47", x"F1", x"1A", x"71", x"1D", x"29", x"C5", x"89", x"6F", x"B7", x"62", x"0E", x"AA", x"18", x"BE", x"1B",
    x"FC", x"56", x"3E", x"4B", x"C6", x"D2", x"79", x"20", x"9A", x"DB", x"C0", x"FE", x"78", x"CD", x"5A", x"F4",
    x"1F", x"DD", x"A8", x"33", x"88", x"07", x"C7", x"31", x"B1", x"12", x"10", x"59", x"27", x"80", x"EC", x"5F",
    x"60", x"51", x"7F", x"A9", x"19", x"B5", x"4A", x"0D", x"2D", x"E5", x"7A", x"9F", x"93", x"C9", x"9C", x"EF",
    x"A0", x"E0", x"3B", x"4D", x"AE", x"2A", x"F5", x"B0", x"C8", x"EB", x"BB", x"3C", x"83", x"53", x"99", x"61",
    x"17", x"2B", x"04", x"7E", x"BA", x"77", x"D6", x"26", x"E1", x"69", x"14", x"63", x"55", x"21", x"0C", x"7D"
  );

  -- ShangMi s-box --
  constant sm4_sbox_c : rom256x8_t := (
    x"D6", x"90", x"E9", x"FE", x"CC", x"E1", x"3D", x"B7", x"16", x"B6", x"14", x"C2", x"28", x"FB", x"2C", x"05",
    x"2B", x"67", x"9A", x"76", x"2A", x"BE", x"04", x"C3", x"AA", x"44", x"13", x"26", x"49", x"86", x"06", x"99",
    x"9C", x"42", x"50", x"F4", x"91", x"EF", x"98", x"7A", x"33", x"54", x"0B", x"43", x"ED", x"CF", x"AC", x"62",
    x"E4", x"B3", x"1C", x"A9", x"C9", x"08", x"E8", x"95", x"80", x"DF", x"94", x"FA", x"75", x"8F", x"3F", x"A6",
    x"47", x"07", x"A7", x"FC", x"F3", x"73", x"17", x"BA", x"83", x"59", x"3C", x"19", x"E6", x"85", x"4F", x"A8",
    x"68", x"6B", x"81", x"B2", x"71", x"64", x"DA", x"8B", x"F8", x"EB", x"0F", x"4B", x"70", x"56", x"9D", x"35",
    x"1E", x"24", x"0E", x"5E", x"63", x"58", x"D1", x"A2", x"25", x"22", x"7C", x"3B", x"01", x"21", x"78", x"87",
    x"D4", x"00", x"46", x"57", x"9F", x"D3", x"27", x"52", x"4C", x"36", x"02", x"E7", x"A0", x"C4", x"C8", x"9E",
    x"EA", x"BF", x"8A", x"D2", x"40", x"C7", x"38", x"B5", x"A3", x"F7", x"F2", x"CE", x"F9", x"61", x"15", x"A1",
    x"E0", x"AE", x"5D", x"A4", x"9B", x"34", x"1A", x"55", x"AD", x"93", x"32", x"30", x"F5", x"8C", x"B1", x"E3",
    x"1D", x"F6", x"E2", x"2E", x"82", x"66", x"CA", x"60", x"C0", x"29", x"23", x"AB", x"0D", x"53", x"4E", x"6F",
    x"D5", x"DB", x"37", x"45", x"DE", x"FD", x"8E", x"2F", x"03", x"FF", x"6A", x"72", x"6D", x"6C", x"5B", x"51",
    x"8D", x"1B", x"AF", x"92", x"BB", x"DD", x"BC", x"7F", x"11", x"D9", x"5C", x"41", x"1F", x"10", x"5A", x"D8",
    x"0A", x"C1", x"31", x"88", x"A5", x"CD", x"7B", x"BD", x"2D", x"74", x"D0", x"12", x"B8", x"E5", x"B4", x"B0",
    x"89", x"69", x"97", x"4A", x"0C", x"96", x"77", x"7E", x"65", x"B9", x"F1", x"09", x"C5", x"6E", x"C6", x"84",
    x"18", x"F0", x"7D", x"EC", x"3A", x"DC", x"4D", x"20", x"79", x"EE", x"5F", x"3E", x"D7", x"CB", x"39", x"48"
  );

  -- ----------------------------------------------------------------------------------------
  -- helper functions
  -- ----------------------------------------------------------------------------------------

  -- logical shift left --
  function lsl_f(data : std_ulogic_vector(31 downto 0); shamt : natural range 0 to 31) return std_ulogic_vector is
    variable res_v : std_ulogic_vector(31 downto 0);
  begin
    res_v := std_ulogic_vector(shift_left(unsigned(data), shamt));
    return res_v;
  end function lsl_f;

  -- logical shift right --
  function lsr_f(data : std_ulogic_vector(31 downto 0); shamt : natural range 0 to 31) return std_ulogic_vector is
    variable res_v : std_ulogic_vector(31 downto 0);
  begin
    res_v := std_ulogic_vector(shift_right(unsigned(data), shamt));
    return res_v;
  end function lsr_f;

  -- rotate right --
  function ror_f(data : std_ulogic_vector(31 downto 0); shamt : natural range 0 to 31) return std_ulogic_vector is
    variable res_v : std_ulogic_vector(31 downto 0);
  begin
    res_v := std_ulogic_vector(rotate_right(unsigned(data), shamt));
    return res_v;
  end function ror_f;

  -- rotate left --
  function rol_f(data : std_ulogic_vector(31 downto 0); shamt : natural range 0 to 31) return std_ulogic_vector is
    variable res_v : std_ulogic_vector(31 downto 0);
  begin
    res_v := std_ulogic_vector(rotate_left(unsigned(data), shamt));
    return res_v;
  end function rol_f;

  -- multiply by 2 in Galois field (2^8) --
  function xt2_f(a : std_ulogic_vector(7 downto 0)) return std_ulogic_vector is
    variable res_v : std_ulogic_vector(7 downto 0);
  begin
    res_v := (a(6 downto 0) & '0') xor ("000" & a(7) & a(7) & '0' & a(7) & a(7)); -- XOR with 0x1B if a(7) is set
    return res_v;
  end function xt2_f;

  -- multiply 8-bit field element by 4-bit value for AES MixCols step --
  function gfmul_f(x : std_ulogic_vector(7 downto 0); y : std_ulogic_vector(3 downto 0)) return std_ulogic_vector is
    variable a_v, b_v, c_v, d_v, res_v : std_ulogic_vector(7 downto 0);
  begin
    if (y(0) = '1') then a_v := x;                      else a_v := x"00"; end if;
    if (y(1) = '1') then b_v := xt2_f(x);               else b_v := x"00"; end if;
    if (y(2) = '1') then c_v := xt2_f(xt2_f(x));        else c_v := x"00"; end if;
    if (y(3) = '1') then d_v := xt2_f(xt2_f(xt2_f(x))); else d_v := x"00"; end if;
    res_v := a_v xor b_v xor c_v xor d_v;
    return res_v;
  end function gfmul_f;

  -- ----------------------------------------------------------------------------------------
  -- logic
  -- ----------------------------------------------------------------------------------------

  -- instruction decoder --
  constant cmd_sha256_c : natural := 0;
  constant cmd_sha512_c : natural := 1;
  constant cmd_aesenc_c : natural := 2;
  constant cmd_aesdec_c : natural := 3;
  constant cmd_sm3_c    : natural := 4;
  constant cmd_sm4_c    : natural := 5;
  --
  signal cmd       : std_ulogic_vector(5 downto 0);
  signal cmd_valid : std_ulogic;

  -- controller --
  type state_t is (S_IDLE, S_BUSY, S_DONE);
  signal state   : state_t;
  signal done    : std_ulogic;
  signal rs1     : std_ulogic_vector(31 downto 0);
  signal rs2     : std_ulogic_vector(31 downto 0);
  signal funct12 : std_ulogic_vector(11 downto 0);
  signal funct3  : std_ulogic_vector(2 downto 0);
  signal out_sel : std_ulogic_vector(2 downto 0);

  -- helper logic --
  signal rs2_sel : std_ulogic_vector(7 downto 0);
  signal rol_in  : std_ulogic_vector(31 downto 0);
  signal rol_res : std_ulogic_vector(31 downto 0);
  signal blk_res : std_ulogic_vector(31 downto 0);

  -- aes core --
  type aes_t is record
    dec  : std_ulogic;
    so   : std_ulogic_vector(7 downto 0);
    mix1 : std_ulogic_vector(31 downto 0);
    mix2 : std_ulogic_vector(31 downto 0);
  end record;
  signal aes : aes_t;

  -- sha core, sm3 core --
  signal sha_res, sm3_res, hash_res : std_ulogic_vector(31 downto 0);

  -- ShangMi core --
  type sm4_t is record
    so1 : std_ulogic_vector(7 downto 0);
    so2 : std_ulogic_vector(31 downto 0);
    rnd : std_ulogic_vector(31 downto 0);
  end record;
  signal sm4 : sm4_t;

begin

  -- Instruction Decode ---------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  cmd(cmd_sha256_c) <= '1' when EN_ZKNH and (ctrl_i.ir_opcode(5) = '0') and (ctrl_i.ir_funct12(11 downto 2) = "0001000000") and
                                (ctrl_i.ir_funct3 = "001") else '0';

  cmd(cmd_sha512_c) <= '1' when EN_ZKNH and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct12(11 downto 8) = "0101") and
                                (ctrl_i.ir_funct12(7 downto 6) /= "10") and (ctrl_i.ir_funct3 = "000") else '0';

  cmd(cmd_aesenc_c) <= '1' when EN_ZKNE and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct3 = "000") and
                                (ctrl_i.ir_funct12(9 downto 7) = "100") and (ctrl_i.ir_funct12(5) = '1') else '0';

  cmd(cmd_aesdec_c) <= '1' when EN_ZKND and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct3 = "000") and
                                (ctrl_i.ir_funct12(9 downto 7) = "101") and (ctrl_i.ir_funct12(5) = '1') else '0';

  cmd(cmd_sm3_c)    <= '1' when EN_ZKSH and (ctrl_i.ir_opcode(5) = '0') and (ctrl_i.ir_funct3 = "001") and
                                (ctrl_i.ir_funct12(11 downto 1) = "00010000100") else '0';

  cmd(cmd_sm4_c)    <= '1' when EN_ZKSED and (ctrl_i.ir_opcode(5) = '1') and (ctrl_i.ir_funct3 = "000") and
                                (ctrl_i.ir_funct12(9 downto 7) = "110") and (ctrl_i.ir_funct12(5) = '0') else '0';

  -- valid instruction? --
  cmd_valid <= '1' when (ctrl_i.alu_cp_alu = '1') and (or_reduce_f(cmd) = '1') else '0';


  -- Controller -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  control: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      rs1     <= (others => '0');
      rs2     <= (others => '0');
      funct3  <= (others => '0');
      funct12 <= (others => '0');
      done    <= '0';
      state   <= S_IDLE;
    elsif rising_edge(clk_i) then
      -- operand gating / buffer --
      if (cmd_valid = '1') then
        rs1     <= rs1_i;
        rs2     <= rs2_i;
        funct3  <= ctrl_i.ir_funct3;
        funct12 <= ctrl_i.ir_funct12;
      end if;
      -- arbiter state machine --
      done <= '0'; -- default
      case state is
        -- wait for operation trigger --
        when S_IDLE =>
          if (cmd_valid = '1') then -- trigger new operation
            if (cmd(cmd_aesenc_c) = '1') or (cmd(cmd_aesdec_c) = '1') or (cmd(cmd_sm3_c) = '1') or (cmd(cmd_sm4_c) = '1') then
              state <= S_BUSY;
            else
              done  <= '1';
              state <= S_IDLE;
            end if;
          end if;
        -- delay cycle --
        when S_BUSY =>
          state <= S_DONE;
        -- S_DONE: final step & enable output for one cycle --
        when others =>
          done  <= '1';
          state <= S_IDLE;
      end case;
    end if;
  end process control;

  -- processing done (high one cycle before actual data output) --
  valid_o <= done;


  -- Output Select --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  result: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      res_o <= (others => '0');
    elsif rising_edge(clk_i) then
      res_o <= (others => '0'); -- default
      if (done = '1') then
        if (out_sel = "101") or (out_sel = "110") then
          res_o <= blk_res;
        else
          res_o <= hash_res;
        end if;
      end if;
    end if;
  end process result;

  -- function unit select --
  out_sel <= funct12(9 downto 8) & funct12(5);


  -- Hash Functions -------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  hash_res <= sm3_res when (EN_ZKSH and (ctrl_i.ir_opcode(5) = '0') and (funct12(3) = '1')) else sha_res;

  -- ShangMi Hash --
  sm3_enabled:
  if EN_ZKSH generate
    sm3_res <= (rs1 xor rol_f(rs1, 9) xor rol_f(rs1, 17)) when (funct12(0) = '0') else (rs1 xor rol_f(rs1, 15) xor rol_f(rs1, 23));
  end generate;

  sm3_disabled:
  if not EN_ZKSH generate
    sm3_res <= (others => '0');
  end generate;

  -- NIST SHA --
  sha_enabled:
  if EN_ZKNH generate
    sha_core: process(funct12, rs1, rs2)
    begin
      if (funct12(10) = '0') then -- sha256
        case funct12(1 downto 0) is
          when "00"   => sha_res <= ror_f(rs1,  2) xor ror_f(rs1, 13) xor ror_f(rs1, 22); -- sha256sum0
          when "01"   => sha_res <= ror_f(rs1,  6) xor ror_f(rs1, 11) xor ror_f(rs1, 25); -- sha256sum1
          when "10"   => sha_res <= ror_f(rs1,  7) xor ror_f(rs1, 18) xor lsr_f(rs1,  3); -- sha256sig0
          when others => sha_res <= ror_f(rs1, 17) xor ror_f(rs1, 19) xor lsr_f(rs1, 10); -- sha256sig1
        end case;
      else -- sha512
        case funct12(7 downto 5) is
          when "000"  => sha_res <= lsl_f(rs1, 25) xor lsl_f(rs1, 30) xor lsr_f(rs1, 28) xor lsr_f(rs2,  7) xor lsr_f(rs2,  2) xor lsl_f(rs2,  4); -- sha512sum0r
          when "001"  => sha_res <= lsl_f(rs1, 23) xor lsr_f(rs1, 14) xor lsr_f(rs1, 18) xor lsr_f(rs2,  9) xor lsl_f(rs2, 18) xor lsl_f(rs2, 14); -- sha512sum1r
          when "010"  => sha_res <= lsr_f(rs1,  1) xor lsr_f(rs1,  7) xor lsr_f(rs1,  8) xor lsl_f(rs2, 31) xor lsl_f(rs2, 25) xor lsl_f(rs2, 24); -- sha512sig0l
          when "011"  => sha_res <= lsl_f(rs1,  3) xor lsr_f(rs1,  6) xor lsr_f(rs1, 19) xor lsr_f(rs2, 29) xor lsl_f(rs2, 26) xor lsl_f(rs2, 13); -- sha512sig1l
          when "110"  => sha_res <= lsr_f(rs1,  1) xor lsr_f(rs1,  7) xor lsr_f(rs1,  8) xor lsl_f(rs2, 31) xor lsl_f(rs2, 24); -- sha512sig0h
          when others => sha_res <= lsl_f(rs1,  3) xor lsr_f(rs1,  6) xor lsr_f(rs1, 19) xor lsr_f(rs2, 29) xor lsl_f(rs2, 13); -- sha512sig1h
        end case;
      end if;
    end process sha_core;
  end generate;

  sha_disabled:
  if not EN_ZKNH generate
    sha_res <= (others => '0');
  end generate;


  -- Block Cyphers (AES/SM4) Helper Logic ---------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  block_cyphers_enabled:
  if EN_ZKNE or EN_ZKND or EN_ZKSED generate

    -- select byte from rs2 via bs --
    with funct12(11 downto 10) select rs2_sel <=
      rs2(07 downto 00) when "00",
      rs2(15 downto 08) when "01",
      rs2(23 downto 16) when "10",
      rs2(31 downto 24) when others;

    -- rotate input select --
    rol_in <= aes.mix2 when (not EN_ZKSED) else
              sm4.rnd  when (not EN_ZKNE) and (not EN_ZKND) else
              aes.mix2 when (funct12(8) = '0') else sm4.rnd;

    -- rotate left by multiples of 8 via bs --
    with funct12(11 downto 10) select rol_res <=
      rol_in(31 downto 0)                        when "00",
      rol_in(23 downto 0) & rol_in(31 downto 24) when "01",
      rol_in(15 downto 0) & rol_in(31 downto 16) when "10",
      rol_in(07 downto 0) & rol_in(31 downto 08) when others;

    -- block cypher result --
    blk_res <= rs1 xor rol_res;

  end generate;

  block_cyphers_disabled:
  if not (EN_ZKNE or EN_ZKND or EN_ZKSED) generate
    rs2_sel <= (others => '0');
    rol_in  <= (others => '0');
    rol_res <= (others => '0');
    blk_res <= (others => '0');
  end generate;


  -- NIST AES Encryption/Decryption ---------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  aes_enabled:
  if EN_ZKNE or EN_ZKND generate

    -- operation select --
    aes.dec <= '1' when (not EN_ZKNE) else '0' when (not EN_ZKND) else funct12(7); -- 0 = encrypt, 1 = decrypt

    -- s-box look-up --
    aes_sbox_lookup: process(clk_i)
    begin
      if rising_edge(clk_i) then -- ROM access; try to infer memory primitives
        aes.so <= aes_sbox_c(to_integer(unsigned(aes.dec & rs2_sel))); -- aes.dec = 0 -> fwd-s-box, aes.dec = 1 -> inv-s-box
      end if;
    end process aes_sbox_lookup;

    -- mix columns --
    aes_mix_columns: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        aes.mix1 <= (others => '0');
      elsif rising_edge(clk_i) then
        if (aes.dec = '1') then -- decrypt
          aes.mix1(31 downto 24) <= gfmul_f(aes.so, x"b");
          aes.mix1(23 downto 16) <= gfmul_f(aes.so, x"d");
          aes.mix1(15 downto 08) <= gfmul_f(aes.so, x"9");
          aes.mix1(07 downto 00) <= gfmul_f(aes.so, x"e");
        else -- encrypt
          aes.mix1(31 downto 24) <= gfmul_f(aes.so, x"3");
          aes.mix1(23 downto 16) <= aes.so;
          aes.mix1(15 downto 08) <= aes.so;
          aes.mix1(07 downto 00) <= gfmul_f(aes.so, x"2");
        end if;
      end if;
    end process aes_mix_columns;

    -- final / middle round --
    aes.mix2 <= aes.mix1 when (funct12(6) = '1') else x"000000" & aes.so;

  end generate;

  aes_disabled:
  if (not EN_ZKNE) and (not EN_ZKND) generate
    aes.dec  <= '0';
    aes.so   <= (others => '0');
    aes.mix1 <= (others => '0');
    aes.mix2 <= (others => '0');
  end generate;


  -- ShangMi Encryption/Decryption ----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  sm4_enabled:
  if EN_ZKSED generate

    -- s-box look-up --
    sm4_sbox_lookup: process(clk_i)
    begin
      if rising_edge(clk_i) then -- ROM access; try to infer memory primitives
        sm4.so1 <= sm4_sbox_c(to_integer(unsigned(rs2_sel)));
      end if;
    end process sm4_sbox_lookup;

    -- zero-extend --
    sm4.so2 <= x"000000" & sm4.so1;

    -- round update: encrypt/decrypt or key schedule --
    sm4_round: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        sm4.rnd <= (others => '0');
      elsif rising_edge(clk_i) then
        if (funct12(6) = '0') then -- encrypt/decrypt
          sm4.rnd <= sm4.so2 xor lsl_f(sm4.so2, 8) xor lsl_f(sm4.so2, 2) xor lsl_f(sm4.so2, 18) xor
                                 lsl_f((sm4.so2 and x"0000003F"), 26) xor lsl_f((sm4.so2 and x"000000C0"), 10);
        else -- key schedule
          sm4.rnd <= sm4.so2 xor lsl_f((sm4.so2 and x"00000007"), 29) xor lsl_f((sm4.so2 and x"000000FE"),  7) xor
                                 lsl_f((sm4.so2 and x"00000001"), 23) xor lsl_f((sm4.so2 and x"000000F8"), 13);
        end if;
      end if;
    end process sm4_round;

  end generate;

  sm4_disabled:
  if not EN_ZKSED generate
    sm4.so1 <= (others => '0');
    sm4.so2 <= (others => '0');
    sm4.rnd <= (others => '0');
  end generate;


end neorv32_cpu_cp_crypto_rtl;
