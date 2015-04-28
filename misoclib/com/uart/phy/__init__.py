def UARTPHY(pads, *args, **kwargs):
    # Autodetect PHY
    if hasattr(pads, "source_stb"):
        from misoclib.com.uart.phy.sim import UARTPHYSim
        return UARTPHYSim(pads, *args, **kwargs)
    else:
        from misoclib.com.uart.phy.serial import UARTPHYSerial
        return UARTPHYSerial(pads, *args, **kwargs)
