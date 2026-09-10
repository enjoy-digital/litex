#
# This file is part of LiteX.
#
# Copyright (c) 2022 Icenowy Zheng <icenowy@aosc.io>
# Copyright (c) 2022-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import re

from litex.soc.cores.clock.gowin_gw1n import GW1NPLL

# GoWin / GW2APLL ----------------------------------------------------------------------------------

class GW2APLL(GW1NPLL):
    # GW2A uses rPLL with device- and speed-dependent frequency limits.

    @classmethod
    def get_primitive(cls, devicename):
        # UG286 Table 5-1. GW2AN-9X/18X use the distinct PLLO primitive.
        if cls.get_device_model(devicename) in (
            "GW2A-18", "GW2A-55", "GW2AR-18", "GW2AN-55", "GW2ANR-18",
        ):
            return "rPLL"
        raise ValueError(f"Unsupported rPLL device {devicename}.")

    @classmethod
    def get_freq_ranges(cls, device, devicename=None):
        if devicename is None:
            match = re.match(r"(GW2[A-Z]*)-(?:LV|UV|EV)?([0-9]+X?)", device)
            if match is None:
                raise ValueError(f"Unsupported device {device}.")
            devicename = "-".join(match.groups())
        cls.get_primitive(devicename)
        model = cls.get_device_model(devicename)
        grade = cls.get_speed_grade(device)

        # DS102, DS226, DS976 and DS961 PLL switching characteristics.
        if grade == 7:
            return (400e6, 1000e6), (3e6, 400e6)
        if grade == 8 or (grade == 9 and model in ("GW2A-18", "GW2A-55", "GW2AR-18")):
            return (500e6, 1250e6), (3e6, 500e6)
        if grade is None:
            # Intersection of the documented speed-grade ranges.
            return (500e6, 1000e6), (3e6, 400e6)
        raise ValueError(f"Unsupported speed grade for {devicename}: {device}.")
