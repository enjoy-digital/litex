-- ================================================================================ --
-- NEORV32 SoC - Execution Tracer                                                   --
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

entity neorv32_tracer is
  generic (
    TRACE_DEPTH   : natural range 1 to 2**15; -- trace buffer depth (has to be a power of two)
    DUAL_CORE_EN  : boolean;                  -- trace the dual-core configuration
    SIM_LOG_EN    : boolean;                  -- enable simulation trace logging
    SIM_LOG_FILE0 : string := "";             -- trace log file CPU 0
    SIM_LOG_FILE1 : string := ""              -- trace log file CPU 1
  );
  port (
    clk_i     : in  std_ulogic;   -- global clock line
    rstn_i    : in  std_ulogic;   -- global reset line, low-active, async
    trace0_i  : in  trace_port_t; -- CPU 0 trace port
    trace1_i  : in  trace_port_t; -- CPU 1 trace port
    bus_req_i : in  bus_req_t;    -- bus request
    bus_rsp_o : out bus_rsp_t;    -- bus response
    irq_o     : out std_ulogic    -- tracing-done interrupt
  );
end neorv32_tracer;

architecture neorv32_tracer_rtl of neorv32_tracer is

  -- control register bits --
  constant ctrl_enable_c  : natural :=  0; -- r/w: module enable; reset module if 0
  constant ctrl_hsel_c    : natural :=  1; -- r/w: selected hart for tracing
  constant ctrl_start_c   : natural :=  2; -- r/w: start tracing; flag always reads as zero
  constant ctrl_stop_c    : natural :=  3; -- r/w: stop tracing; flag always reads as zero
  constant ctrl_run_c     : natural :=  4; -- r/-: tracing is running when set
  constant ctrl_avail_c   : natural :=  5; -- r/-: trace data available
  constant ctrl_irq_clr_c : natural :=  6; -- r/w: clear pending interrupt by writing one
  constant data_tbm_lsb_c : natural :=  7; -- r/-: log2(RX FIFO size) LSB
  constant data_tbm_msb_c : natural := 10; -- r/-: log2(RX FIFO size) MSB

  -- helpers --
  constant log2_fifo_size_c : natural := index_size_f(TRACE_DEPTH);

  -- control registers --
  signal ctrl_en, ctrl_hsel, ctrl_start, ctrl_stop, ctrl_iclr : std_ulogic;
  signal stop_addr : std_ulogic_vector(30 downto 0);

  -- trace arbiter --
  type arbiter_t is record
    run   : std_ulogic; -- tracing in progress
    valid : std_ulogic_vector(1 downto 0); -- valid-sample shift register
    first : std_ulogic; -- first trace entry
    delta : std_ulogic; -- control flow transfer detected
    src   : std_ulogic_vector(31 downto 0); -- source address
    dst   : std_ulogic_vector(31 downto 0); -- destination address
    push  : std_ulogic; -- push to trace buffer
    astop : std_ulogic; -- auto-stop tracing
  end record;
  signal arbiter : arbiter_t;

  -- trace buffer interface --
  type fifo_t is record
    we,    re    : std_ulogic; -- write/read enable
    wdata, rdata : std_ulogic_vector(63 downto 0); -- write/read data
    avail, free  : std_ulogic; -- FIFO status
    clear        : std_ulogic; -- sync clear
  end record;
  signal fifo : fifo_t;

  -- misc --
  signal over_check : std_ulogic; -- FIFO overflow checker
  signal over_trash : std_ulogic; -- discard data from trace buffer
  signal trace_src  : trace_port_t; -- trace input stream

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o  <= rsp_terminate_c;
      ctrl_en    <= '0';
      ctrl_hsel  <= '0';
      ctrl_start <= '0';
      ctrl_stop  <= '0';
      ctrl_iclr  <= '0';
      stop_addr  <= (others => '0');
    elsif rising_edge(clk_i) then
      -- bus handshake --
      bus_rsp_o.ack <= bus_req_i.stb;
      bus_rsp_o.err <= '0';
      -- write access --
      ctrl_start <= '0';
      ctrl_stop  <= '0';
      ctrl_iclr  <= '0';
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '1') then
        if (bus_req_i.addr(3 downto 2) = "00") then -- control register
          ctrl_en    <= bus_req_i.data(ctrl_enable_c);
          ctrl_hsel  <= bus_req_i.data(ctrl_hsel_c) and bool_to_ulogic_f(DUAL_CORE_EN);
          ctrl_start <= bus_req_i.data(ctrl_start_c);
          ctrl_stop  <= bus_req_i.data(ctrl_stop_c);
          ctrl_iclr  <= bus_req_i.data(ctrl_irq_clr_c);
        end if;
        if (bus_req_i.addr(3 downto 2) = "01") then -- stop-address register
          stop_addr <= bus_req_i.data(31 downto 1);
        end if;
      end if;
      -- read access --
      bus_rsp_o.data <= (others => '0');
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '0') then
        case bus_req_i.addr(3 downto 2) is
          when "00" => -- control register
            bus_rsp_o.data(ctrl_enable_c) <= ctrl_en;
            bus_rsp_o.data(ctrl_hsel_c)   <= ctrl_hsel and bool_to_ulogic_f(DUAL_CORE_EN);
            bus_rsp_o.data(ctrl_run_c)    <= arbiter.run;
            bus_rsp_o.data(ctrl_avail_c)  <= fifo.avail;
            bus_rsp_o.data(data_tbm_msb_c downto data_tbm_lsb_c) <= std_ulogic_vector(to_unsigned(log2_fifo_size_c, 4));
          when "01" => -- stop-address register
            bus_rsp_o.data <= stop_addr & '0';
          when "10" => -- trace data: source
            bus_rsp_o.data <= fifo.rdata(31 downto 0);
          when others => -- trace data: destination
            bus_rsp_o.data <= fifo.rdata(63 downto 32);
        end case;
      end if;
    end if;
  end process bus_access;

  -- trace source select (CPU0 or CPU1) --
  trace_src <= trace0_i when (ctrl_hsel = '0') or (DUAL_CORE_EN = false) else trace1_i;


  -- Trace Control Arbiter ------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trace_arbiter: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      arbiter.run   <= '0';
      arbiter.valid <= (others => '0');
      arbiter.first <= '0';
      arbiter.delta <= '0';
      arbiter.src   <= (others => '0');
      arbiter.dst   <= (others => '0');
    elsif rising_edge(clk_i) then
      if (arbiter.run = '0') then -- tracing disabled
        arbiter.valid <= (others => '0'); -- no valid data sampled yet
        arbiter.first <= '1'; -- this will be the first trace packet
        arbiter.delta <= '0';
        if (ctrl_en = '1') and (ctrl_start = '1') then
          arbiter.run <= '1';
        end if;
      else -- tracing in progress
        arbiter.valid(0) <= '0'; -- default
        if (ctrl_en = '0') or (ctrl_stop = '1') or (arbiter.astop = '1') then -- tracing still running
          arbiter.run <= '0';
        elsif (trace_src.valid = '1') and (trace_src.debug = '0') then -- valid trace packet and not in debug-mode
          arbiter.valid(0) <= '1';
          arbiter.dst      <= trace_src.pc_rdata(31 downto 1) & trace_src.intr;
        end if;
        -- sample shift register --
        if (arbiter.valid(0) = '1') then
          arbiter.valid(1) <= '1';
          arbiter.src      <= arbiter.dst(31 downto 1) & arbiter.first;
        end if;
        arbiter.delta <= trace_src.delta;
        -- clear first-packet flag on first push
        if (arbiter.push = '1') then
          arbiter.first <= '0';
        end if;
      end if;
    end if;
  end process trace_arbiter;

  -- push to trace buffer --
  arbiter.push <= '1' when (arbiter.valid = "11") and (arbiter.delta = '1') else '0';

  -- automatic stop if reaching stop address --
  arbiter.astop <= '1' when (arbiter.dst(31 downto 1) = stop_addr) and (arbiter.valid(0) = '1') else '0';


  -- Interrupt Generator --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  irq_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_o <= '0';
    elsif rising_edge(clk_i) then
      if (ctrl_en = '0') then
        irq_o <= '0';
      elsif (arbiter.astop = '1') then -- trigger interrupt when reaching auto-stop-address
        irq_o <= '1';
      elsif (ctrl_iclr = '1') then
        irq_o <= '0';
      end if;
    end if;
  end process irq_generator;


  -- Trace Buffer (implemented as FIFO) -----------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trace_buffer_inst: entity neorv32.neorv32_prim_fifo
  generic map (
    AWIDTH  => log2_fifo_size_c,
    DWIDTH  => 2*32,
    OUTGATE => false
  )
  port map (
    -- global control --
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    clear_i => fifo.clear,
    -- write port --
    wdata_i => fifo.wdata,
    we_i    => fifo.we,
    free_o  => fifo.free,
    -- read port --
    re_i    => fifo.re,
    rdata_o => fifo.rdata,
    avail_o => fifo.avail
  );

  -- FIFO access --
  fifo.clear <= not ctrl_en;
  fifo.we    <= arbiter.push;
  fifo.wdata <= arbiter.dst & arbiter.src;
  fifo.re    <= '1' when (over_trash = '1') or
                         ((bus_req_i.stb = '1') and (bus_req_i.rw = '0') and (bus_req_i.addr(3 downto 2) = "11")) else '0';

  -- discard oldest entry if overflowing --
  discard: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      over_check <= '0';
      over_trash <= '0';
    elsif rising_edge(clk_i) then
      if (over_check = '0') or (ctrl_en = '0') or (arbiter.run = '0') then
        over_check <= not fifo.free;
        over_trash <= '0';
      else
        over_check <= '0';
        over_trash <= '1';
      end if;
    end if;
  end process discard;


  -- Simulation Trace Logging ---------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------

  -- CPU 0 --
  sim_trace0_enabled:
  if is_simulation_c and SIM_LOG_EN generate
    assert false report "[NEORV32] CPU 0 trace logging enabled -> " & SIM_LOG_FILE0 severity note;
    neorv32_cpu_trace_simlog0_inst: entity neorv32.neorv32_cpu_trace_simlog
    generic map (
      LOG_FILE => SIM_LOG_FILE0
    )
    port map (
      clk_i   => clk_i,
      rstn_i  => rstn_i,
      trace_i => trace0_i
    );
  end generate;

  -- CPU 1 --
  sim_trace1_enabled:
  if is_simulation_c and SIM_LOG_EN and DUAL_CORE_EN generate
    assert false report "[NEORV32] CPU 1 trace logging enabled -> " & SIM_LOG_FILE1 severity note;
    neorv32_cpu_trace_simlog1_inst: entity neorv32.neorv32_cpu_trace_simlog
    generic map (
      LOG_FILE => SIM_LOG_FILE1
    )
    port map (
      clk_i   => clk_i,
      rstn_i  => rstn_i,
      trace_i => trace1_i
    );
  end generate;

end neorv32_tracer_rtl;
