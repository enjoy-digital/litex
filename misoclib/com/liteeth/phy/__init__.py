from misoclib.com.liteeth.common import *


def LiteEthPHY(clock_pads, pads, clk_freq=None, **kwargs):
    # Autodetect PHY
    if hasattr(pads, "source_stb"):
        # This is a simulation PHY
        from misoclib.com.liteeth.phy.sim import LiteEthPHYSim
        return LiteEthPHYSim(pads)
    elif hasattr(clock_pads, "gtx") and flen(pads.tx_data) == 8:
        if hasattr(clock_pads, "tx"):
            # This is a 10/100/1G PHY
            from misoclib.com.liteeth.phy.gmii_mii import LiteEthPHYGMIIMII
            return LiteEthPHYGMIIMII(clock_pads, pads, clk_freq=clk_freq, **kwargs)
        else:
            # This is a pure 1G PHY
            from misoclib.com.liteeth.phy.gmii import LiteEthPHYGMII
            return LiteEthPHYGMII(clock_pads, pads, **kwargs)
    elif hasattr(pads, "rx_ctl"):
        # This is a 10/100/1G RGMII PHY
        raise ValueError("RGMII PHYs are specific to vendors (for now), use direct instantiation")
    elif flen(pads.tx_data) == 4:
        # This is a MII PHY
        from misoclib.com.liteeth.phy.mii import LiteEthPHYMII
        return LiteEthPHYMII(clock_pads, pads, **kwargs)
    else:
        raise ValueError("Unable to autodetect PHY from platform file, use direct instantiation")
