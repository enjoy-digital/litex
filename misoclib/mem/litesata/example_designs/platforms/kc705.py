from mibuild.generic_platform import *
from mibuild.platforms import kc705

_sata_io = [
    ("sata_clocks", 0,
        Subsignal("refclk_p", Pins("HPC:GBTCLK0_M2C_P")),
        Subsignal("refclk_n", Pins("HPC:GBTCLK0_M2C_N"))
    ),
    ("sata", 0,
        Subsignal("txp", Pins("HPC:DP0_C2M_P")),
        Subsignal("txn", Pins("HPC:DP0_C2M_N")),
        Subsignal("rxp", Pins("HPC:DP0_M2C_P")),
        Subsignal("rxn", Pins("HPC:DP0_M2C_N"))
    ),
    ("sata", 1,
        Subsignal("txp", Pins("HPC:DP1_C2M_P")),
        Subsignal("txn", Pins("HPC:DP1_C2M_N")),
        Subsignal("rxp", Pins("HPC:DP1_M2C_P")),
        Subsignal("rxn", Pins("HPC:DP1_M2C_N"))
    ),
    ("sata", 2,
        Subsignal("txp", Pins("HPC:DP2_C2M_P")),
        Subsignal("txn", Pins("HPC:DP2_C2M_N")),
        Subsignal("rxp", Pins("HPC:DP2_M2C_P")),
        Subsignal("rxn", Pins("HPC:DP2_M2C_N"))
    ),
    ("sata", 3,
        Subsignal("txp", Pins("HPC:DP3_C2M_P")),
        Subsignal("txn", Pins("HPC:DP3_C2M_N")),
        Subsignal("rxp", Pins("HPC:DP3_M2C_P")),
        Subsignal("rxn", Pins("HPC:DP3_M2C_N"))
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
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 2.5 [current_design]
""")
