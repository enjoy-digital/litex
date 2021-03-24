import sys
import time

def colorer(s, color="bright"): # FIXME: Move colorer to litex.common?
    header  = {
        "bright": "\x1b[1m",
        "green":  "\x1b[32m",
        "cyan":   "\x1b[36m",
        "red":    "\x1b[31m",
        "yellow": "\x1b[33m",
        "underline": "\x1b[4m"}[color]
    trailer = "\x1b[0m"
    return header + str(s) + trailer

def compat_notice(name, date, info=""):
    print("Compat: {name} is {deprecated} since {date} and will soon no longer work, please {update}. {info}".format(
        name       = colorer(name),
        deprecated = colorer("deprecated", color="red"),
        date       = colorer(date),
        update     = colorer("update", color="red"),
        info       = info,
    ), end="")
    # Annoy user to force update :)
    for i in range(10):
        time.sleep(0.2)
        print(".", end="")
        sys.stdout.flush()
    print("thanks :)")
    time.sleep(1)

def add_compat(location):
    if location == "litex.soc.integration":
        #compat_notice("SoCSDRAM", date="2020-03-24", info="Switch to SoCCore/add_sdram/soc_core_args instead.")
        from litex.compat import soc_sdram
        sys.modules["litex.soc.integration.soc_sdram"] = soc_sdram
    elif location == "litex.soc.cores":
        compat_notice("litex.soc.cores.up5kspram", date="2020-03-24", info="Switch to litex.soc.cores.ram.")
        from litex.soc.cores import ram
        sys.modules["litex.soc.cores.up5kspram"] = ram
