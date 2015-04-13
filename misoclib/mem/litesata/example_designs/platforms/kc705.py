from mibuild.generic_platform import *
from mibuild.platforms import kc705

_sata_io = [
    ("sata", 0,
        Subsignal("refclk_p", Pins("HPC:GBTCLK0_M2C_P")),
        Subsignal("refclk_n", Pins("HPC:GBTCLK0_M2C_N")),
        Subsignal("txp", Pins("HPC:DP0_C2M_P")),
        Subsignal("txn", Pins("HPC:DP0_C2M_N")),
        Subsignal("rxp", Pins("HPC:DP0_M2C_P")),
        Subsignal("rxn", Pins("HPC:DP0_M2C_N")),
    )
]

class Platform(kc705.Platform):
    def __init__(self, *args, **kwargs):
        kc705.Platform.__init__(self, *args, **kwargs)
        self.add_extension(_sata_io)

    def do_finalize(self, fragment):
            try:
                self.add_period_constraint(self.lookup_request("clk156").p, 6.4)
            except ConstraintError:
                pass
            try:
                self.add_period_constraint(self.lookup_request("clk200").p, 5.0)
            except ConstraintError:
                pass
            self.add_platform_command("""
create_clock -name sys_clk -period 6 [get_nets sys_clk]
create_clock -name sata_rx_clk -period 3.33 [get_nets sata_rx_clk]
create_clock -name sata_tx_clk -period 3.33 [get_nets sata_tx_clk]

set_false_path -from [get_clocks sys_clk] -to [get_clocks sata_rx_clk]
set_false_path -from [get_clocks sys_clk] -to [get_clocks sata_tx_clk]
set_false_path -from [get_clocks sata_rx_clk] -to [get_clocks sys_clk]
set_false_path -from [get_clocks sata_tx_clk] -to [get_clocks sys_clk]

set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 2.5 [current_design]
""")
