#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import tempfile
import unittest

from litex.build.report import parse_vivado_timing, parse_vivado_utilization
from litex.build.report import parse_gowin_timing, parse_gowin_utilization
from litex.build.report import parse_quartus_timing, parse_quartus_utilization
from litex.build.report import parse_efinity_timing, parse_efinity_utilization
from litex.build.report import parse_nextpnr_log, parse_build_log_errors, parse_build_reports

# Report excerpts ----------------------------------------------------------------------------------

VIVADO_TIMING = """\
------------------------------------------------------------------------------------------------
| Design Timing Summary
| ---------------------
------------------------------------------------------------------------------------------------

    WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints      WHS(ns)      THS(ns)  THS Failing Endpoints  THS Total Endpoints     WPWS(ns)     TPWS(ns)  TPWS Failing Endpoints  TPWS Total Endpoints
    -------      -------  ---------------------  -------------------      -------      -------  ---------------------  -------------------     --------     --------  ----------------------  --------------------
     -5.916     -856.390                    184                21903        0.007        0.000                      0                21900        1.100        0.000                       0                  8035


Timing constraints are not met.


------------------------------------------------------------------------------------------------
| Intra Clock Table
| -----------------
------------------------------------------------------------------------------------------------

Clock                         WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints      WHS(ns)      THS(ns)  THS Failing Endpoints  THS Total Endpoints     WPWS(ns)     TPWS(ns)  TPWS Failing Endpoints  TPWS Total Endpoints
-----                         -------      -------  ---------------------  -------------------      -------      -------  ---------------------  -------------------     --------     --------  ----------------------  --------------------
clk200_p                        4.083        0.000                      0                   14        0.209        0.000                      0                   14        1.100        0.000                       0                    19
  sys_clk                      -5.916     -856.390                    184                 3695        0.087        0.000                      0                 3695        2.796        0.000                       0                  1433
  pll_fb                                                                                                                                                                    8.751        0.000                       0                     2


Max Delay Paths
--------------------------------------------------------------------------------------
Slack (VIOLATED) :        -5.916ns  (required time - arrival time)
  Source:                 multireg_regs1_reg[1]/C
                            (rising edge-triggered cell FDRE clocked by sys_clk  {rise@0.000ns fall@3.846ns period=7.692ns})
  Destination:            storage_dat1_reg[38]/D
                            (rising edge-triggered cell FDRE clocked by sys_clk  {rise@0.000ns fall@3.846ns period=7.692ns})
  Path Group:             sys_clk
  Path Type:              Setup (Max at Slow Process Corner)
  Requirement:            7.692ns  (sys_clk rise@7.692ns - sys_clk rise@0.000ns)
  Data Path Delay:        13.333ns  (logic 0.816ns (6.120%)  route 12.517ns (93.880%))
  Logic Levels:           4  (LUT3=1 LUT6=2 RAMD32=1)

    Location             Delay type                Incr(ns)  Path(ns)    Netlist Resource(s)
"""

VIVADO_UTILIZATION = """\
+----------------------------+------+-------+------------+-----------+-------+
|          Site Type         | Used | Fixed | Prohibited | Available | Util% |
+----------------------------+------+-------+------------+-----------+-------+
| Slice LUTs                 | 6261 |     0 |        800 |    133800 |  4.68 |
|   LUT as Distributed RAM   |  582 |     0 |            |           |       |
| Slice Registers            | 6848 |     0 |       1600 |    267600 |  2.56 |
+----------------------------+------+-------+------------+-----------+-------+
"""

GOWIN_TIMING = """\
\t2.3 Max Frequency Summary
\t2.4 Total Negative Slack Summary
2.3 Max Frequency Summary
  NO.      Clock Name        Constraint    Actual Fmax    Level   Entity
 ===== =================== ============== ============== ======= ========
  1     tx_clk              125.000(MHz)   163.639(MHz)   9       TOP
  2     sys_clk             62.504(MHz)    58.377(MHz)    9       TOP

2.4 Total Negative Slack Summary
     Clock Name       Analysis Type   EndPoints TNS   Number of EndPoints
 =================== =============== =============== =====================
  tx_clk              setup           0.000           0
  sys_clk             setup           -12.500         7

Path Summary:
Slack             : -1.250
Data Arrival Time : 17.638
Data Required Time: 16.388
From              : core_a_s0
To                : core_b_s0
Launch Clk        : sys_clk:[R]
Latch Clk         : sys_clk:[R]

"""

GOWIN_UTILIZATION = """\
3. Resource Usage Summary

  --------------------------------------------------------------------------------
  Resources                   | Usage                               | Utilization
  --------------------------------------------------------------------------------
  Logic                       | 13759/15120                         |  91%
    --LUT,ALU,ROM16           | 12103(10925 LUT, 1178 ALU, 0 ROM16) | -
  Register                    | 7737/15276                          |  51%
  BSRAM                       | 35/35                               |  100%
  ================================================================================

5. Clock Resource Usage Summary
  ------------------------------------------
  Clock Resource| Usage         | Utilization
  ------------------------------------------
  PRIMARY       | 5/8           | 63%
  ------------------------------------------
"""

NEXTPNR_LOG = """\
Info: Device utilisation:
Info: 	          TRELLIS_IO:     125/    197    63%
Info: 	              DP16KD:      19/     56    33%

Info: Max frequency for clock '$glbnet$sys_clk': 102.77 MHz (PASS at 99.01 MHz)
Info: Max frequency for clock '$glbnet$eth_clk': 112.00 MHz (FAIL at 125.00 MHz)
ERROR: Max frequency for clock '$glbnet$eth_clk' failed.
"""

QUARTUS_STA_SUMMARY = """\
------------------------------------------------------------
Timing Analyzer Summary
------------------------------------------------------------

Type  : Slow 1100mV 85C Model Setup 'sys_clk'
Slack : -0.412
TNS   : -3.250

Type  : Fast 1100mV 0C Model Setup 'sys_clk'
Slack : 1.900
TNS   : 0.000

Type  : Slow 1100mV 85C Model Hold 'sys_clk'
Slack : 0.301
TNS   : 0.000

Type  : Slow 1100mV 85C Model Minimum Pulse Width 'clk50'
Slack : 6.525
TNS   : 0.000
"""

QUARTUS_FIT_SUMMARY = """\
Fitter Status : Successful - Mon Oct 23 15:15:20 2023
Family : Cyclone V
Device : 5CEBA4F23C8
Logic utilization (in ALMs) : 1,541 / 18,480 ( 8 % )
Total registers : 2733
Total RAM Blocks : 84 / 308 ( 27 % )
Total DSP Blocks : 0 / 66 ( 0 % )
"""

EFINITY_TIMING = """\
---------- 1. Clock Frequency Summary (begin) ----------

User target constrained clocks
          Clock Name           Period (ns)  Frequency (MHz)    Waveform                Targets
sys_clk                            5.000        200.000     {0.000 2.500}  {sys}

Maximum possible analyzed clocks frequency
 Clock Name  Period (ns)  Frequency (MHz)     Edge
  sys_clk       5.589        178.923         (R-R)

---------- Clock Frequency Summary (end) ---------------

---------- 2. Clock Relationship Summary (begin) ----------

Setup (Max) Clock Relationship
  Launch Clock    Capture Clock   Constraint (ns)     Slack (ns)          Edge
    sys_clk          sys_clk           5.000            -0.589           (R-R)

Hold (Min) Clock Relationship
  Launch Clock    Capture Clock   Constraint (ns)     Slack (ns)          Edge
    sys_clk          sys_clk           0.000            0.022            (R-R)

NOTE: Values are in nanoseconds.

---------- Clock Relationship Summary (end) ---------------

---------- 3. Path Details for Max Critical Paths (begin) ----------

++++ Path 1 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

Path Begin    : storage_19__D$12|RCLK
Path End      : core/error_code[3]~FF|CE
Launch Clock  : sys_clk (RISE)
Capture Clock : sys_clk (RISE)
Slack         : -0.589 (required time - arrival time)
Delay         : 3.998

Logic Level             : 10

---------- Path Details for Max Critical Paths (end) ---------------
"""

EFINITY_TIMING_OLD = """\
---------- 2. Clock Relationship Summary (begin) ----------

Launch Clock    Capture Clock    Constraint (ns)   Slack (ns)    Edge
pll0_clkout1     pll0_clkout1          5.000         1.090     (R-R)

NOTE: Values are in nanoseconds.

---------- Clock Relationship Summary (end) ---------------
"""

EFINITY_PLACE = """\
---------- Resource Summary (begin) ----------
Inputs: 84 / 1703 (4.93%)
XLRs: 54398 / 60800 (89.47%)
\tXLRs needed for Logic: 25123 / 60800 (41.32%)
Memory Blocks: 200 / 256 (78.12%)
---------- Resource Summary (end) ----------
"""

# Test Report --------------------------------------------------------------------------------------

class TestReport(unittest.TestCase):
    def test_vivado(self):
        t = parse_vivado_timing(VIVADO_TIMING)
        self.assertEqual(t["wns"], -5.916)
        self.assertEqual(t["tns_failing_endpoints"], 184)
        self.assertFalse(t["met"])
        self.assertEqual([c["clock"] for c in t["clocks"]], ["clk200_p", "sys_clk"])
        self.assertEqual(t["failing_paths"][0]["path_group"], "sys_clk")
        self.assertTrue(t["failing_paths"][0]["logic_levels"].startswith("4"))
        u = parse_vivado_utilization(VIVADO_UTILIZATION)
        self.assertEqual([(r["resource"], r["used"]) for r in u], [("Slice LUTs", 6261), ("Slice Registers", 6848)])

    def test_gowin(self):
        t = parse_gowin_timing(GOWIN_TIMING)
        self.assertEqual([c["clock"] for c in t["clocks"]], ["tx_clk", "sys_clk"])
        self.assertFalse(t["met"])
        self.assertEqual(t["tns"], -12.5)
        self.assertEqual(t["wns"], -1.25)
        self.assertEqual(t["clocks"][1]["failing_endpoints"], 7)
        u = parse_gowin_utilization(GOWIN_UTILIZATION)
        self.assertEqual([r["resource"] for r in u], ["Logic", "Register", "BSRAM"])

    def test_quartus(self):
        t = parse_quartus_timing(QUARTUS_STA_SUMMARY)
        self.assertEqual(t["wns"], -0.412) # Worst corner.
        self.assertEqual(t["whs"], 0.301)
        self.assertFalse(t["met"])
        self.assertEqual(t["clocks"], [{"clock": "sys_clk", "setup_slack": -0.412, "setup_tns": -3.25,
            "hold_slack": 0.301, "hold_tns": 0.0}])
        u, status = parse_quartus_utilization(QUARTUS_FIT_SUMMARY)
        self.assertTrue(status.startswith("Successful"))
        self.assertEqual([(r["resource"], r["used"], r["available"]) for r in u], [
            ("Logic utilization (in ALMs)", 1541, 18480), ("Total RAM Blocks", 84, 308), ("Total DSP Blocks", 0, 66)])

    def test_efinity(self):
        t = parse_efinity_timing(EFINITY_TIMING)
        self.assertEqual(t["clocks"], [{"clock": "sys_clk", "fmax_mhz": 178.923, "constraint_mhz": 200.0, "met": False}])
        self.assertEqual((t["wns"], t["whs"], t["met"]), (-0.589, 0.022, False))
        self.assertEqual(t["failing_paths"][0]["destination"], "core/error_code[3]~FF|CE")
        self.assertEqual(t["failing_paths"][0]["logic_levels"], "10")
        t = parse_efinity_timing(EFINITY_TIMING_OLD)
        self.assertEqual((t["wns"], t["met"]), (1.09, True))
        u = parse_efinity_utilization(EFINITY_PLACE)
        self.assertEqual([r["resource"] for r in u], ["Inputs", "XLRs", "Memory Blocks"])

    def test_nextpnr(self):
        t, u = parse_nextpnr_log(NEXTPNR_LOG)
        self.assertFalse(t["met"])
        self.assertEqual(t["clocks"][0]["fmax_mhz"], 102.77)
        self.assertEqual([r["resource"] for r in u], ["TRELLIS_IO", "DP16KD"])
        self.assertEqual(len(parse_build_log_errors(NEXTPNR_LOG)), 1)

    def test_build_dir_quartus_efinity(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "gateware", "outflow"))
            for name, content in [("top.sta.summary", QUARTUS_STA_SUMMARY), ("top.fit.summary", QUARTUS_FIT_SUMMARY)]:
                with open(os.path.join(d, "gateware", name), "w") as f:
                    f.write(content)
            r = parse_build_reports(d)
            self.assertEqual(r["toolchain"], "quartus")
            self.assertTrue(r["fitter_status"].startswith("Successful"))
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "gateware", "outflow"))
            for name, content in [("top.timing.rpt", EFINITY_TIMING), ("top.place.rpt", EFINITY_PLACE)]:
                with open(os.path.join(d, "gateware", "outflow", name), "w") as f:
                    f.write(content)
            r = parse_build_reports(d)
            self.assertEqual(r["toolchain"], "efinity")
            self.assertEqual(r["timing"]["wns"], -0.589)
            self.assertEqual(len(r["utilization"]), 3)

    def test_build_dir(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "gateware"))
            with open(os.path.join(d, "gateware", "top_timing.rpt"), "w") as f:
                f.write(VIVADO_TIMING)
            with open(os.path.join(d, "gateware", "top_utilization_place.rpt"), "w") as f:
                f.write(VIVADO_UTILIZATION)
            with open(os.path.join(d, "litex.log"), "w") as f:
                f.write("INFO:SoC:...\nERROR: [Place 30-640] Place Check failed.\n")
            r = parse_build_reports(d)
            self.assertEqual(r["toolchain"], "vivado")
            self.assertEqual(r["timing"]["wns"], -5.916)
            self.assertEqual(len(r["utilization"]), 2)
            self.assertEqual(r["errors"], ["ERROR: [Place 30-640] Place Check failed."])

if __name__ == "__main__":
    unittest.main()
