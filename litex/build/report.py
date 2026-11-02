#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Build report parsing: timing and utilization summaries from the toolchain reports of a build.

parse_build_reports(output_dir) looks for the reports a LiteX build leaves in <output_dir> and
<output_dir>/gateware and returns a dictionary that serializes to JSON:
- Vivado    : <name>_timing.rpt (report_timing_summary) and <name>_utilization_place.rpt.
- Gowin     : impl/pnr/project.tr and impl/pnr/project.rpt.txt.
- Quartus   : <name>.sta.summary and <name>.fit.summary.
- Efinity   : outflow/<name>.timing.rpt and outflow/<name>.place.rpt.
- nextpnr   : the Fmax and utilization lines of the build log (<output_dir>/litex.log).
and the errors found in the build log. Missing reports are simply not reported.
"""

import os
import re
import glob

# Helpers ------------------------------------------------------------------------------------------

def _read(filename):
    with open(filename, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def _float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None

def _section(report, title):
    # Numbered section heading at the start of a line ("2.3 Max Frequency Summary"); the table of
    # contents lists the same titles indented, the last heading is the section itself.
    matches = list(re.finditer(rf"^[\d.]+\s+{re.escape(title)}\s*$", report, re.M))
    return "" if not matches else report[matches[-1].start():]

def _int(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return None

# Vivado -------------------------------------------------------------------------------------------

_VIVADO_SUMMARY_KEYS = [
    "wns", "tns", "tns_failing_endpoints", "tns_total_endpoints",
    "whs", "ths", "ths_failing_endpoints", "ths_total_endpoints",
]

def parse_vivado_timing(report, max_paths=10):
    """Parse a Vivado report_timing_summary report (text)."""
    timing = {}

    # Design Timing Summary: first numeric line after the header.
    m = re.search(r"Design Timing Summary.*?\n\s*-+\s+-+.*?\n(.*?)\n", report, re.S)
    if m:
        values = m.group(1).split()
        for key, value in zip(_VIVADO_SUMMARY_KEYS, values):
            timing[key] = _int(value) if "endpoints" in key else _float(value)
    if "All user specified timing constraints are met" in report:
        timing["met"] = True
    elif "Timing constraints are not met" in report:
        timing["met"] = False

    # Intra Clock Table: per clock WNS/TNS/WHS.
    clocks = []
    m = re.search(r"Intra Clock Table.*?\n\s*-+\s+-+.*?\n(.*?)\n\s*\n", report, re.S)
    if m:
        for line in m.group(1).splitlines():
            fields = line.split()
            if len(fields) >= 9 and _float(fields[1]) is not None:
                clocks.append({
                    "clock"            : fields[0],
                    "wns"              : _float(fields[1]),
                    "tns"              : _float(fields[2]),
                    "failing_endpoints": _int(fields[3]),
                    "whs"              : _float(fields[5]),
                })
    timing["clocks"] = clocks

    # Failing paths (setup/hold violations).
    paths = []
    for m in re.finditer(r"Slack \(VIOLATED\)\s*:\s*(-?[\d.]+)ns.*?\n(.*?)(?=\n\s*\n\s*Location|\n\s*\n\s*Delay Type)", report, re.S):
        block = m.group(2)
        path  = {"slack": _float(m.group(1))}
        for key, label in [("source", "Source"), ("destination", "Destination"),
            ("path_group", "Path Group"), ("path_type", "Path Type"), ("requirement", "Requirement"),
            ("data_path_delay", "Data Path Delay"), ("logic_levels", "Logic Levels")]:
            n = re.search(rf"^\s*{label}:\s*(.*)$", block, re.M)
            if n:
                path[key] = n.group(1).strip()
        paths.append(path)
        if len(paths) >= max_paths:
            break
    timing["failing_paths"] = paths
    return timing

def parse_vivado_utilization(report):
    """Parse a Vivado report_utilization report (text): one entry per table row with numbers."""
    utilization = []
    for line in report.splitlines():
        fields = [f.strip() for f in line.strip().strip("|").split("|")]
        if len(fields) == 6 and _float(fields[1]) is not None and _float(fields[5]) is not None:
            utilization.append({
                "resource"  : fields[0],
                "used"      : _float(fields[1]),
                "available" : _float(fields[4]),
                "percent"   : _float(fields[5]),
            })
        elif len(fields) == 5 and _float(fields[1]) is not None and _float(fields[4]) is not None:
            utilization.append({
                "resource"  : fields[0],
                "used"      : _float(fields[1]),
                "available" : _float(fields[3]),
                "percent"   : _float(fields[4]),
            })
    return utilization

# Gowin --------------------------------------------------------------------------------------------

def parse_gowin_timing(report, max_paths=10):
    """Parse a Gowin timing report (project.tr)."""
    timing = {"clocks": [], "worst_paths": []}
    m = re.search(r"=+.*?\n(.*?)\n\s*\n", _section(report, "Max Frequency Summary"), re.S)
    if m:
        for line in m.group(1).splitlines():
            n = re.match(r"\s*\d+\s+(\S+)\s+([\d.]+)\(MHz\)\s+([\d.]+)\(MHz\)\s+(\d+)", line)
            if n:
                timing["clocks"].append({
                    "clock"         : n.group(1),
                    "constraint_mhz": _float(n.group(2)),
                    "fmax_mhz"      : _float(n.group(3)),
                    "logic_levels"  : _int(n.group(4)),
                    "met"           : _float(n.group(3)) >= _float(n.group(2)),
                })
    tns = {}
    m = re.search(r"=+.*?\n(.*?)\n\s*\n", _section(report, "Total Negative Slack Summary"), re.S)
    if m:
        for line in m.group(1).splitlines():
            fields = line.split()
            if len(fields) == 4 and _float(fields[2]) is not None:
                tns[(fields[0], fields[1])] = (_float(fields[2]), _int(fields[3]))
    for clock in timing["clocks"]:
        clock["tns"], clock["failing_endpoints"] = tns.get((clock["clock"], "setup"), (None, None))
    timing["tns"] = sum(v[0] for (c, t), v in tns.items() if t == "setup")
    for m in re.finditer(r"Path Summary:\s*\nSlack\s*:\s*(-?[\d.]+)(.*?)\n\s*\n", report, re.S):
        path = {"slack": _float(m.group(1))}
        for key, label in [("from", "From"), ("to", "To"), ("launch_clock", "Launch Clk"),
            ("latch_clock", "Latch Clk")]:
            n = re.search(rf"^{label}\s*:\s*(.*)$", m.group(2), re.M)
            if n:
                path[key] = n.group(1).strip()
        timing["worst_paths"].append(path)
        if len(timing["worst_paths"]) >= max_paths:
            break
    slacks = [p["slack"] for p in timing["worst_paths"]]
    timing["wns"] = min(slacks) if slacks else None
    timing["met"] = all(c["met"] for c in timing["clocks"]) and (timing["tns"] == 0)
    return timing

def parse_gowin_utilization(report):
    """Parse the Resource Usage Summary of a Gowin report (project.rpt.txt)."""
    utilization = []
    m = re.search(r"-{10,}\n.*?-{10,}\n(.*?)\n\s*-{10,}", _section(report, "Resource Usage Summary"), re.S)
    if m:
        for line in m.group(1).splitlines():
            fields = [f.strip() for f in line.split("|")]
            n = re.match(r"(\d+)/(\d+)", fields[1]) if len(fields) == 3 else None
            if n:
                utilization.append({
                    "resource"  : fields[0].lstrip("-"),
                    "used"      : _float(n.group(1)),
                    "available" : _float(n.group(2)),
                    "percent"   : _float(fields[2].rstrip("%")),
                })
    return utilization

# Quartus ------------------------------------------------------------------------------------------

def parse_quartus_timing(summary):
    """Parse a Quartus Timing Analyzer summary (<name>.sta.summary): worst slack/TNS per clock."""
    clocks = {}
    worst  = {"setup": [], "hold": [], "pulse": []}
    for m in re.finditer(r"Type\s*:\s*(.*?)\s+'([^']+)'\s*\nSlack\s*:\s*(-?[\d.]+)\s*\nTNS\s*:\s*(-?[\d.]+)", summary):
        kind  = m.group(1)
        clock = m.group(2)
        slack = _float(m.group(3))
        tns   = _float(m.group(4))
        if "Setup" in kind:
            key = "setup"
        elif "Hold" in kind:
            key = "hold"
        elif "Pulse Width" in kind:
            key = "pulse"
        else:
            continue
        worst[key].append(slack)
        if key == "pulse":
            continue
        c = clocks.setdefault(clock, {"clock": clock})
        # Worst case over the timing models (slow/fast corners).
        if c.get(f"{key}_slack") is None or slack < c[f"{key}_slack"]:
            c[f"{key}_slack"] = slack
        if c.get(f"{key}_tns") is None or tns < c[f"{key}_tns"]:
            c[f"{key}_tns"] = tns
    timing = {"clocks": list(clocks.values())}
    timing["wns"] = min(worst["setup"]) if worst["setup"] else None
    timing["whs"] = min(worst["hold"])  if worst["hold"]  else None
    timing["tns"] = sum(c.get("setup_tns", 0) for c in clocks.values()) if clocks else None
    slacks = worst["setup"] + worst["hold"] + worst["pulse"]
    if slacks:
        timing["met"] = min(slacks) >= 0
    return timing

def parse_quartus_utilization(summary):
    """Parse a Quartus Fitter summary (<name>.fit.summary)."""
    utilization = []
    status      = None
    for line in summary.splitlines():
        key, _, value = line.partition(" : ")
        if key.strip() == "Fitter Status":
            status = value.strip()
            continue
        m = re.match(r"([\d,]+)\s*/\s*([\d,]+)\s*\(\s*([<\d.]+)\s*%\s*\)", value.strip())
        if m:
            utilization.append({
                "resource"  : key.strip(),
                "used"      : _float(m.group(1).replace(",", "")),
                "available" : _float(m.group(2).replace(",", "")),
                "percent"   : _float(m.group(3).lstrip("<")),
            })
    return utilization, status

# Efinity ------------------------------------------------------------------------------------------

def _efinity_section(report, title):
    m = re.search(rf"-+ (?:\d+\. )?{re.escape(title)} \(begin\) -+\n(.*?)\n-+ (?:\d+\. )?{re.escape(title)} \(end\)", report, re.S)
    return "" if m is None else m.group(1)

def parse_efinity_timing(report, max_paths=10):
    """Parse an Efinity timing report (outflow/<name>.timing.rpt)."""
    timing = {"clocks": [], "failing_paths": []}
    freq   = _efinity_section(report, "Clock Frequency Summary")
    targets, fmax = {}, {}
    block = re.search(r"User target constrained clocks\s*\n.*?\n(.*?)(?:\n\s*\n|\Z)", freq, re.S)
    for line in (block.group(1).splitlines() if block else []):
        fields = line.split()
        if len(fields) >= 3 and _float(fields[2]) is not None:
            targets[fields[0]] = _float(fields[2])
    block = re.search(r"Maximum possible analyzed clocks frequency\s*\n.*?\n(.*?)(?:\n\s*\n|\Z)", freq, re.S)
    for line in (block.group(1).splitlines() if block else []):
        fields = line.split()
        if len(fields) >= 3 and _float(fields[2]) is not None:
            fmax[fields[0]] = _float(fields[2])
    for clock, f in fmax.items():
        timing["clocks"].append({
            "clock"         : clock,
            "fmax_mhz"      : f,
            "constraint_mhz": targets.get(clock),
            "met"           : None if clock not in targets else f >= targets[clock],
        })

    # Clock relationships: worst setup/hold slack.
    relations = _efinity_section(report, "Clock Relationship Summary")
    for key, title in [("wns", "Setup"), ("whs", "Hold")]:
        block = re.search(rf"{title} \((Max|Min)\) Clock Relationship\s*\n.*?\n(.*?)\n\s*\n", relations, re.S)
        slacks = []
        for line in (block.group(2).splitlines() if block else []):
            fields = line.split()
            if len(fields) >= 4 and _float(fields[3]) is not None:
                slacks.append(_float(fields[3]))
        timing[key] = min(slacks) if slacks else None
    if "Clock Relationship" not in relations:
        # Older Efinity versions: one table without Setup/Hold titles (setup slacks).
        slacks = []
        for line in relations.splitlines():
            fields = line.split()
            if len(fields) >= 4 and _float(fields[2]) is not None and _float(fields[3]) is not None:
                slacks.append(_float(fields[3]))
        timing["wns"] = min(slacks) if slacks else None
    if timing["wns"] is not None or timing["whs"] is not None:
        timing["met"] = all(v is None or v >= 0 for v in [timing["wns"], timing["whs"]])

    # Failing setup paths.
    paths = _efinity_section(report, "Path Details for Max Critical Paths")
    for m in re.finditer(r"Path Begin\s*:\s*(\S+).*?Path End\s*:\s*(\S+).*?Launch Clock\s*:\s*([^\n]+?)\s*\n.*?Capture Clock\s*:\s*([^\n]+?)\s*\n.*?Slack\s*:\s*(-?[\d.]+).*?Logic Level\s*:\s*(\d+)", paths, re.S):
        slack = _float(m.group(5))
        if slack is None or slack >= 0:
            continue
        timing["failing_paths"].append({
            "slack"        : slack,
            "source"       : m.group(1),
            "destination"  : m.group(2),
            "launch_clock" : m.group(3),
            "capture_clock": m.group(4),
            "logic_levels" : m.group(6),
        })
        if len(timing["failing_paths"]) >= max_paths:
            break
    return timing

def parse_efinity_utilization(report):
    """Parse the Resource Summary of an Efinity place report (outflow/<name>.place.rpt)."""
    utilization = []
    m = re.search(r"Resource Summary \(begin\) -+\n(.*?)\n-+ Resource Summary \(end\)", report, re.S)
    for line in (m.group(1).splitlines() if m else []):
        if line.startswith((" ", "\t")):
            continue # Detail lines.
        n = re.match(r"(.+?):\s*(\d+)\s*/\s*(\d+)\s*\(([\d.]+)%\)", line)
        if n:
            utilization.append({
                "resource"  : n.group(1).strip(),
                "used"      : _float(n.group(2)),
                "available" : _float(n.group(3)),
                "percent"   : _float(n.group(4)),
            })
    return utilization

# nextpnr ------------------------------------------------------------------------------------------

def parse_nextpnr_log(log):
    """Parse the Fmax and Device utilisation lines that nextpnr prints (last run in the log)."""
    clocks = {}
    for m in re.finditer(r"Max frequency for clock\s+'([^']+)':\s*([\d.]+) MHz \((PASS|FAIL) at ([\d.]+) MHz\)", log):
        clocks[m.group(1)] = {
            "clock"         : m.group(1),
            "fmax_mhz"      : _float(m.group(2)),
            "constraint_mhz": _float(m.group(4)),
            "met"           : m.group(3) == "PASS",
        }
    utilization = []
    blocks = log.split("Device utilisation:")
    if len(blocks) > 1:
        for line in blocks[-1].splitlines()[1:]:
            m = re.match(r"Info:\s+(\S+):\s+(\d+)/\s*(\d+)\s+(\d+)%", line)
            if not m:
                break
            utilization.append({
                "resource"  : m.group(1),
                "used"      : _float(m.group(2)),
                "available" : _float(m.group(3)),
                "percent"   : _float(m.group(4)),
            })
    timing = {"clocks": list(clocks.values())}
    if clocks:
        timing["met"] = all(c["met"] for c in clocks.values())
    return timing, utilization

# Build log ----------------------------------------------------------------------------------------

def parse_build_log_errors(log, max_errors=20):
    """Return the error lines of a build log (toolchain ERROR/Error/fatal lines, Python exceptions)."""
    errors = []
    for line in log.splitlines():
        if re.search(r"^(ERROR|Error|FATAL|Fatal|CRITICAL WARNING)\b|\bERROR:|^\w*Error: |Traceback", line):
            errors.append(line.strip())
            if len(errors) >= max_errors:
                break
    return errors

# Build reports ------------------------------------------------------------------------------------

def parse_build_reports(output_dir, max_paths=10):
    """Return the timing/utilization summaries and errors of the build in output_dir."""
    gateware_dir = os.path.join(output_dir, "gateware")
    r = {"output_dir": output_dir}

    # Vivado.
    timing_rpts = sorted(glob.glob(os.path.join(gateware_dir, "*_timing.rpt")))
    if timing_rpts:
        r["toolchain"] = "vivado"
        r["timing"]    = parse_vivado_timing(_read(timing_rpts[0]), max_paths)
        util_rpts = sorted(glob.glob(os.path.join(gateware_dir, "*_utilization_place.rpt")))
        if util_rpts:
            r["utilization"] = parse_vivado_utilization(_read(util_rpts[0]))

    # Gowin.
    gowin_tr  = os.path.join(gateware_dir, "impl", "pnr", "project.tr")
    gowin_rpt = os.path.join(gateware_dir, "impl", "pnr", "project.rpt.txt")
    if os.path.exists(gowin_tr):
        r["toolchain"] = "gowin"
        r["timing"]    = parse_gowin_timing(_read(gowin_tr), max_paths)
    if os.path.exists(gowin_rpt):
        r["utilization"] = parse_gowin_utilization(_read(gowin_rpt))

    # Quartus.
    sta_summaries = sorted(glob.glob(os.path.join(gateware_dir, "*.sta.summary")))
    fit_summaries = sorted(glob.glob(os.path.join(gateware_dir, "*.fit.summary")))
    if sta_summaries:
        r["toolchain"] = "quartus"
        r["timing"]    = parse_quartus_timing(_read(sta_summaries[0]))
    if fit_summaries:
        r["utilization"], r["fitter_status"] = parse_quartus_utilization(_read(fit_summaries[0]))

    # Efinity.
    efinity_timing = sorted(glob.glob(os.path.join(gateware_dir, "outflow", "*.timing.rpt")))
    efinity_place  = sorted(glob.glob(os.path.join(gateware_dir, "outflow", "*.place.rpt")))
    if efinity_timing:
        r["toolchain"] = "efinity"
        r["timing"]    = parse_efinity_timing(_read(efinity_timing[0]), max_paths)
    if efinity_place:
        r["utilization"] = parse_efinity_utilization(_read(efinity_place[0]))

    # Build log (nextpnr results and errors).
    log_file = os.path.join(output_dir, "litex.log")
    if os.path.exists(log_file):
        log = _read(log_file)
        r["log"] = log_file
        if "timing" not in r and "Max frequency for clock" in log:
            r["toolchain"] = "nextpnr"
            r["timing"], r["utilization"] = parse_nextpnr_log(log)
        r["errors"] = parse_build_log_errors(log)
    return r
