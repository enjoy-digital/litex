import sys
import time

# Compatibility Layer ------------------------------------------------------------------------------

def compat_notice(name, date, info=""):
    from litex.gen import colorer
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
        pass
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
        pass
