import sys
import time

# Helpers ------------------------------------------------------------------------------------------

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

# Compat -------------------------------------------------------------------------------------------

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

def add_compat(location):
    # Integration.
    if location == "litex.soc.integration":
        class compat_soc_sdram:
            noticed = False
            def __getattr__(self, name):
                if not self.noticed:
                    compat_notice("SoCSDRAM", date="2020-03-24", info="Switch to SoCCore/add_sdram/soc_core_args instead.")
                    self.noticed = True
                from litex.compat import soc_sdram
                return getattr(soc_sdram, name)
        sys.modules["litex.soc.integration.soc_sdram"] = compat_soc_sdram()
    # Interconnect.
    if location == "litex.soc.interconnect":
        class compat_stream_sim:
            noticed = False
            def __getattr__(self, name):
                if not self.noticed:
                    compat_notice("stream_sim", date="2020-03-24", info="Code will not be replaced, copy it in your project to continue using it.")
                    self.noticed = True
                from litex.compat import stream_sim
                return getattr(stream_sim, name)
        sys.modules["litex.soc.interconnect.stream_sim"] = compat_stream_sim()

    # Cores.
    if location == "litex.soc.cores":
        class compat_up5kspram:
            noticed = False
            def __getattr__(self, name):
                if not self.noticed:
                    compat_notice("litex.soc.cores.up5kspram", date="2020-03-24", info="Switch to litex.soc.cores.ram.")
                    self.noticed = True
                from litex.soc.cores import ram
                return getattr(ram, name)
        from litex.soc.cores import ram
        sys.modules["litex.soc.cores.up5kspram"] = compat_up5kspram()
