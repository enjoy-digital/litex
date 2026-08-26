-- ================================================================================ --
-- NEORV32 CPU - Compressed Instructions Decoder (RISC-V 'C' ISA Extension)         --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2024 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_cpu_decompressor is
  port (
    instr_i : in  std_ulogic_vector(15 downto 0); -- compressed instruction
    instr_o : out std_ulogic_vector(31 downto 0)  -- decompressed instruction
  );
end neorv32_cpu_decompressor;

architecture neorv32_cpu_decompressor_rtl of neorv32_cpu_decompressor is

  -- compressed instruction layout --
  constant ci_opcode_lsb_c : natural :=  0;
  constant ci_opcode_msb_c : natural :=  1;
  constant ci_rd_3_lsb_c   : natural :=  2;
  constant ci_rd_3_msb_c   : natural :=  4;
  constant ci_rd_5_lsb_c   : natural :=  7;
  constant ci_rd_5_msb_c   : natural := 11;
  constant ci_rs1_3_lsb_c  : natural :=  7;
  constant ci_rs1_3_msb_c  : natural :=  9;
  constant ci_rs1_5_lsb_c  : natural :=  7;
  constant ci_rs1_5_msb_c  : natural := 11;
  constant ci_rs2_3_lsb_c  : natural :=  2;
  constant ci_rs2_3_msb_c  : natural :=  4;
  constant ci_rs2_5_lsb_c  : natural :=  2;
  constant ci_rs2_5_msb_c  : natural :=  6;
  constant ci_funct3_lsb_c : natural := 13;
  constant ci_funct3_msb_c : natural := 15;

  -- intermediates --
  signal illegal : std_ulogic;
  signal decoded : std_ulogic_vector(31 downto 0);

begin

  -- Compressed Instruction Decoder ---------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  decompressor: process(instr_i)
    variable imm20_v : std_ulogic_vector(20 downto 0);
    variable imm12_v : std_ulogic_vector(12 downto 0);
  begin
    -- large sign-extended immediates --
    imm20_v := replicate_f(instr_i(12),10) & instr_i(8) & instr_i(10 downto 9) & instr_i(6) & instr_i(7) & instr_i(2) & instr_i(11) & instr_i(5 downto 3) & '0';
    imm12_v := replicate_f(instr_i(12),5) & instr_i(6 downto 5) & instr_i(2) & instr_i(11 downto 10) & instr_i(4 downto 3) & '0';

    -- defaults --
    illegal <= '0';
    decoded <= x"00000003"; -- empty rv32 instruction

    -- decoder --
    case instr_i(ci_opcode_msb_c downto ci_opcode_lsb_c) is

      when "00" => -- C0: register-based loads and stores
        case instr_i(ci_funct3_msb_c downto ci_funct3_lsb_c) is

          when "000" => -- canonical illegal instruction, C.ADDI4SPN
          -- --------------------------------------------------------------------------------------
            decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_alui_c;
            decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= "00010"; -- stack pointer
            decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= "01" & instr_i(ci_rd_3_msb_c downto ci_rd_3_lsb_c);
            decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_sadd_c;
            decoded(instr_imm12_msb_c downto instr_imm12_lsb_c)   <= "00" & instr_i(10 downto 7) & instr_i(12 downto 11) & instr_i(5) & instr_i(6) & "00";
            if (instr_i(12 downto 5) = "00000000") then -- canonical illegal C instruction or C.ADDI4SPN with nzuimm = 0
              illegal <= '1';
            end if;

          when "010" => -- C.LW
          -- --------------------------------------------------------------------------------------
            decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_load_c;
            decoded(instr_imm12_msb_c downto instr_imm12_lsb_c)   <= "00000" & instr_i(5) & instr_i(12 downto 10) & instr_i(6) & "00";
            decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_lw_c;
            decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= "01" & instr_i(ci_rs1_3_msb_c downto ci_rs1_3_lsb_c); -- x8 - x15
            decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= "01" & instr_i(ci_rd_3_msb_c downto ci_rd_3_lsb_c);   -- x8 - x15

          when "110" => -- C.SW
          -- --------------------------------------------------------------------------------------
            decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_store_c;
            decoded(instr_funct7_msb_c downto instr_funct7_lsb_c) <= "00000" & instr_i(5) & instr_i(12); -- immediate
            decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= instr_i(11 downto 10) & instr_i(6) & "00"; -- immediate
            decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_sw_c;
            decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= "01" & instr_i(ci_rs1_3_msb_c downto ci_rs1_3_lsb_c); -- x8 - x15
            decoded(instr_rs2_msb_c downto instr_rs2_lsb_c)       <= "01" & instr_i(ci_rs2_3_msb_c downto ci_rs2_3_lsb_c); -- x8 - x15

          when others => -- "011": C.FLW, "111": C.FSW, "001": C.FLS / C.LQ, "100": reserved, "101": C.FSD / C.SQ
          -- --------------------------------------------------------------------------------------
            illegal <= '1';

        end case;

      when "01" => -- C1: control transfer instructions, integer constant-generation instructions

        case instr_i(ci_funct3_msb_c downto ci_funct3_lsb_c) is

          when "101" | "001" => -- C.J, C.JAL
          -- --------------------------------------------------------------------------------------
            if (instr_i(ci_funct3_msb_c) = '1') then -- C.J
              decoded(instr_rd_msb_c downto instr_rd_lsb_c) <= "00000"; -- discard return address
            else -- C.JAL
              decoded(instr_rd_msb_c downto instr_rd_lsb_c) <= "00001"; -- x1 = lr (link register)
            end if;
            decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_jal_c;
            decoded(instr_imm20_msb_c downto instr_imm20_lsb_c)   <= imm20_v(20) & imm20_v(10 downto 1) & imm20_v(11) & imm20_v(19 downto 12);

          when "110" | "111" => -- C.BEQ, C.BNEZ
          -- --------------------------------------------------------------------------------------
            if (instr_i(ci_funct3_lsb_c) = '0') then -- C.BEQ
              decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_beq_c;
            else -- C.BNEZ
              decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_bne_c;
            end if;
            decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_branch_c;
            decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= "01" & instr_i(ci_rs1_3_msb_c downto ci_rs1_3_lsb_c);
            decoded(instr_rs2_msb_c downto instr_rs2_lsb_c)       <= "00000"; -- x0
            decoded(instr_funct7_msb_c downto instr_funct7_lsb_c) <= imm12_v(12) & imm12_v(10 downto 5); -- immediate
            decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= imm12_v(4 downto 1) & imm12_v(11); -- immediate

          when "010" => -- C.LI
          -- --------------------------------------------------------------------------------------
            decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_alui_c;
            decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_sadd_c;
            decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= "00000"; -- x0
            decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= instr_i(ci_rd_5_msb_c downto ci_rd_5_lsb_c);
            decoded(instr_imm12_msb_c downto instr_imm12_lsb_c)   <= replicate_f(instr_i(12),6) & instr_i(12) & instr_i(6 downto 2);

          when "011" => -- C.LUI / C.ADDI16SP
          -- --------------------------------------------------------------------------------------
            if (instr_i(ci_rd_5_msb_c downto ci_rd_5_lsb_c) = "00010") then -- C.ADDI16SP
              decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_alui_c;
              decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_sadd_c;
              decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= instr_i(ci_rd_5_msb_c downto ci_rd_5_lsb_c);
              decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= "00010"; -- stack pointer
              decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= "00010"; -- stack pointer
              decoded(instr_imm12_msb_c downto instr_imm12_lsb_c)   <= replicate_f(instr_i(12),3) & instr_i(4 downto 3) & instr_i(5) & instr_i(2) & instr_i(6) & "0000";
            else -- C.LUI
              decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_lui_c;
              decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= instr_i(ci_rd_5_msb_c downto ci_rd_5_lsb_c);
              decoded(instr_imm20_msb_c downto instr_imm20_lsb_c)   <= replicate_f(instr_i(12),15) & instr_i(6 downto 2);
            end if;
            if (instr_i(6 downto 2) = "00000") and (instr_i(12) = '0') then -- reserved if nzimm = 0
              illegal <= '1';
            end if;

          when "000" => -- C.NOP (rd=0) / C.ADDI
          -- --------------------------------------------------------------------------------------
            decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_alui_c;
            decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_sadd_c;
            decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= instr_i(ci_rs1_5_msb_c downto ci_rs1_5_lsb_c);
            decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= instr_i(ci_rd_5_msb_c downto ci_rd_5_lsb_c);
            decoded(instr_imm12_msb_c downto instr_imm12_lsb_c)   <= replicate_f(instr_i(12),7) & instr_i(6 downto 2);

          when others => -- 100: C.SRLI, C.SRAI, C.ANDI, C.SUB, C.XOR, C.OR, C.AND, reserved
          -- --------------------------------------------------------------------------------------
            decoded(instr_rd_msb_c downto instr_rd_lsb_c)   <= "01" & instr_i(ci_rs1_3_msb_c downto ci_rs1_3_lsb_c);
            decoded(instr_rs1_msb_c downto instr_rs1_lsb_c) <= "01" & instr_i(ci_rs1_3_msb_c downto ci_rs1_3_lsb_c);
            decoded(instr_rs2_msb_c downto instr_rs2_lsb_c) <= "01" & instr_i(ci_rs2_3_msb_c downto ci_rs2_3_lsb_c);
            case instr_i(11 downto 10) is
              when "00" | "01" => -- C.SRLI, C.SRAI
                if (instr_i(10) = '0') then -- C.SRLI
                  decoded(instr_funct7_msb_c downto instr_funct7_lsb_c) <= "0000000";
                else -- C.SRAI
                  decoded(instr_funct7_msb_c downto instr_funct7_lsb_c) <= "0100000";
                end if;
                decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_alui_c;
                decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_sr_c;
                decoded(instr_rs2_msb_c downto instr_rs2_lsb_c)       <= instr_i(6 downto 2); -- immediate
                if (instr_i(12) = '1') then -- nzuimm[5] = 1 -> RV32 custom / illegal
                  illegal <= '1';
                end if;
              when "10" => -- C.ANDI
                decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_alui_c;
                decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_and_c;
                decoded(instr_imm12_msb_c downto instr_imm12_lsb_c)   <= replicate_f(instr_i(12),7) & instr_i(6 downto 2);
              when others => -- "11" = register-register operation
                decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_alu_c;
                case instr_i(6 downto 5) is
                  when "00" => -- C.SUB
                    decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_sadd_c;
                    decoded(instr_funct7_msb_c downto instr_funct7_lsb_c) <= "0100000";
                  when "01" => -- C.XOR
                    decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_xor_c;
                    decoded(instr_funct7_msb_c downto instr_funct7_lsb_c) <= "0000000";
                  when "10" => -- C.OR
                    decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_or_c;
                    decoded(instr_funct7_msb_c downto instr_funct7_lsb_c) <= "0000000";
                  when others => -- C.AND
                    decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_and_c;
                    decoded(instr_funct7_msb_c downto instr_funct7_lsb_c) <= "0000000";
                end case;
                if (instr_i(12) = '1') then -- reserved
                  illegal <= '1';
                end if;
            end case;

        end case;

      when others => -- C2: stack-pointer-based loads and stores, control transfer instructions (or c3 which is not rvc)
        case instr_i(ci_funct3_msb_c downto ci_funct3_lsb_c) is

          when "000" => -- C.SLLI
          -- --------------------------------------------------------------------------------------
            decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_alui_c;
            decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= instr_i(ci_rs1_5_msb_c downto ci_rs1_5_lsb_c);
            decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= instr_i(ci_rs1_5_msb_c downto ci_rs1_5_lsb_c);
            decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_sll_c;
            decoded(instr_funct7_msb_c downto instr_funct7_lsb_c) <= "0000000";
            decoded(instr_rs2_msb_c downto instr_rs2_lsb_c)       <= instr_i(6 downto 2); -- immediate
            if (instr_i(12) = '1') then -- nzuimm[5] = 1 -> RV32 custom
              illegal <= '1';
            end if;

          when "010" | "011" => -- C.LWSP / C.FLWSP
          -- --------------------------------------------------------------------------------------
            decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_load_c;
            decoded(instr_imm12_msb_c downto instr_imm12_lsb_c)   <= "0000" & instr_i(3 downto 2) & instr_i(12) & instr_i(6 downto 4) & "00";
            decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_lw_c;
            decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= "00010"; -- x2 = sp (stack pointer)
            decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= instr_i(ci_rd_5_msb_c downto ci_rd_5_lsb_c);
            if (instr_i(ci_funct3_lsb_c) = '1') or -- C.FLWSP -> illegal
               (instr_i(ci_rd_5_msb_c downto ci_rd_5_lsb_c) = "00000") then -- rd = 0 -> reserved
              illegal <= '1';
            end if;

          when "110" | "111" => -- C.SWSP / C.FSWSP
          -- --------------------------------------------------------------------------------------
            decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_store_c;
            decoded(instr_funct7_msb_c downto instr_funct7_lsb_c) <= "0000" & instr_i(8 downto 7) & instr_i(12); -- immediate
            decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= instr_i(11 downto 9) & "00"; -- immediate
            decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= funct3_sw_c;
            decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= "00010"; -- x2 = sp (stack pointer)
            decoded(instr_rs2_msb_c downto instr_rs2_lsb_c)       <= instr_i(ci_rs2_5_msb_c downto ci_rs2_5_lsb_c);
            if (instr_i(ci_funct3_lsb_c) = '1') then -- C.FSWSP -> illegal
              illegal <= '1';
            end if;

          when "100" => -- "100": C.JR, C.JALR, C.MV, C.EBREAK, C.ADD
          -- --------------------------------------------------------------------------------------
            if (instr_i(12) = '0') then -- C.JR, C.MV
              if (instr_i(6 downto 2) = "00000") then -- C.JR
                decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_jalr_c;
                decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= instr_i(ci_rs1_5_msb_c downto ci_rs1_5_lsb_c);
                decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= "00000"; -- discard return address
                if (instr_i(ci_rs1_5_msb_c downto ci_rs1_5_lsb_c) = "00000") or -- rs1 = 0 -> reserved
                   (instr_i(ci_rs2_5_msb_c downto ci_rs2_5_lsb_c) /= "00000") then -- rs2 != 0 -> illegal
                  illegal <= '1';
                end if;
              else -- C.MV
                decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_alu_c;
                decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= "000";
                decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= instr_i(ci_rd_5_msb_c downto ci_rd_5_lsb_c);
                decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= "00000"; -- x0
                decoded(instr_rs2_msb_c downto instr_rs2_lsb_c)       <= instr_i(ci_rs2_5_msb_c downto ci_rs2_5_lsb_c);
                if (instr_i(ci_rs2_5_msb_c downto ci_rs2_5_lsb_c) = "00000") then -- rs2 = 0 -> reserved
                  illegal <= '1';
                end if;
              end if;
            else -- C.EBREAK, C.JALR, C.ADD
              if (instr_i(6 downto 2) = "00000") then -- C.EBREAK, C.JALR
                if (instr_i(11 downto 7) = "00000") then -- C.EBREAK
                  decoded(instr_opcode_msb_c downto instr_opcode_lsb_c)   <= opcode_system_c;
                  decoded(instr_funct12_msb_c downto instr_funct12_lsb_c) <= funct12_ebreak_c;
                else -- C.JALR
                  decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_jalr_c;
                  decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= instr_i(ci_rs1_5_msb_c downto ci_rs1_5_lsb_c);
                  decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= "00001"; -- x1 = lr (link register)
                end if;
              else -- C.ADD
                decoded(instr_opcode_msb_c downto instr_opcode_lsb_c) <= opcode_alu_c;
                decoded(instr_funct3_msb_c downto instr_funct3_lsb_c) <= "000";
                decoded(instr_rd_msb_c downto instr_rd_lsb_c)         <= instr_i(ci_rd_5_msb_c downto ci_rd_5_lsb_c);
                decoded(instr_rs1_msb_c downto instr_rs1_lsb_c)       <= instr_i(ci_rd_5_msb_c downto ci_rd_5_lsb_c);
                decoded(instr_rs2_msb_c downto instr_rs2_lsb_c)       <= instr_i(ci_rs2_5_msb_c downto ci_rs2_5_lsb_c);
              end if;
            end if;

          when others => -- "001"/"101": C.FLDSP / C.LQSP, C.FSDSP / C.SQSP -> illegal
          -- --------------------------------------------------------------------------------------
            illegal <= '1';

        end case;

    end case;
  end process decompressor;

  -- output illegal instruction in its pre-decoded 32-bit form --
  instr_o(31 downto 2) <= decoded(31 downto 2);
  instr_o(1) <= decoded(1) when (illegal = '0') else '0'; -- force OPCODE[1] to zero if illegal
  instr_o(0) <= decoded(0);


end neorv32_cpu_decompressor_rtl;
