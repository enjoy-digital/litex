# This file is Copyright (c) 2014-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
# License: BSD

import os
from litex.build import tools


def _xdc_separator(msg):
    r =  "#"*80 + "\n"
    r += "# " + msg + "\n"
    r += "#"*80 + "\n"
    return r

def _format_xdc_constraint(c):
    if c[0] == "location":
        return "set_property LOC " + c[1]
    elif c[0] == "iostandard":
        return "set_property IOSTANDARD " + c[1]
    elif c[0] == "drive":
        return "set_property DRIVE " + c[1]
    elif c[0] == "custom":
        return "set_property " + c[1].replace("=", " ")
    elif c[0] == "inverted":
        return None
    else:
        raise ValueError("unknown constraint {}".format(c))

def _format_xdc(signame, *constraints):
    fmt_c = [_format_xdc_constraint(c) for c in constraints]
    r = ""
    for c in fmt_c:
        if c is not None:
            r += c + " [get_ports {" + signame + "}]\n"
    r += "\n"
    return r

def _build_xdc(io, constraints):
    r = _xdc_separator("IO constraints") + "\n"
    for entry in io:
        sig = entry["signal"]
        pins = entry.get("pins", [])
        properties = entry.get("properties", [])
        if len(pins) > 1:
            for i, p in enumerate(pins):
                r += _format_xdc(sig + "[" + str(i) + "]", ("location", p), *properties)
        elif pins:
            r += _format_xdc(sig, ("location", pins[0]), *properties)
        else:
            r += _format_xdc(sig, *properties)
    if constraints:
        r += _xdc_separator("Design constraints")
        r += "\n" + "\n".join(constraints)
    r += "\n"
    return r


class Vivado:
    def __init__(self, edam=None, work_root=None):
        self._edam = edam
        self._work_root = work_root

    def configure(self):
        io = self._edam.get("constraints", {}).get("io", [])
        period_constraints = self._edam.get("constraints", {}).get("period", {})
        false_paths = self._edam.get("constraints", {}).get("false_path", {})
        custom_constraints = self._edam.get("constraints", {}).get("custom", [])

        constraints = custom_constraints[:]

        # Process constraints
        constraints.append("\n" + _xdc_separator("Clock constraints"))
        for clk, period in period_constraints.items():
            constraints.append(
                f"create_clock -name {clk} -period {str(period)} [get_nets {clk}]")
        for from_, to in false_paths:
            constraints.append(
                "set_clock_groups "
                f"-group [get_clocks -include_generated_clocks -of [get_nets {from_}]] "
                f"-group [get_clocks -include_generated_clocks -of [get_nets {to}]] "
                "-asynchronous")

        constraints.append("\n" + _xdc_separator("False path constraints"))
        # The asynchronous input to a MultiReg is a false path
        constraints.append(
            "set_false_path -quiet "
            "-through [get_nets -hierarchical -filter {mr_ff == TRUE}]"
        )
        # The asychronous reset input to the AsyncResetSynchronizer is a false path
        constraints.append(
            "set_false_path -quiet "
            "-to [get_pins -filter {REF_PIN_NAME == PRE} "
                "-of_objects [get_cells -hierarchical -filter {ars_ff1 == TRUE || ars_ff2 == TRUE}]]"
        )
        # clock_period-2ns to resolve metastability on the wire between the AsyncResetSynchronizer FFs
        constraints.append(
            "set_max_delay 2 -quiet "
            "-from [get_pins -filter {REF_PIN_NAME == C} "
                "-of_objects [get_cells -hierarchical -filter {ars_ff1 == TRUE}]] "
            "-to [get_pins -filter {REF_PIN_NAME == D} "
                "-of_objects [get_cells -hierarchical -filter {ars_ff2 == TRUE}]]"
        )

        # Create .xdc
        xdc = os.path.join(self._work_root, self._edam.get("name", "top") + ".xdc")
        self._edam["files"].append({ "name": xdc, "file_type": "xdc" })
        tools.write_to_file(xdc, _build_xdc(io, constraints))
