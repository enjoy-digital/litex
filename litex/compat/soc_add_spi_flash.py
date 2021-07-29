####################################################################################################
#       DISCLAIMER: Provides retro-compatibility layer for add_spi_flash with previous LiteX core.
#              Will soon no longer work, please don't use in new designs.
####################################################################################################

from math import ceil

from litex.soc.integration.soc import SoCRegion

def add_spi_flash(soc, name="spiflash", mode="4x", dummy_cycles=None, clk_freq=None):
    # Imports.
    from litex.soc.cores.spi_flash import SpiFlash

    # Checks.
    assert dummy_cycles is not None # FIXME: Get dummy_cycles from SPI Flash
    assert mode in ["1x", "4x"]
    if clk_freq is None: clk_freq = soc.clk_freq/2 # FIXME: Get max clk_freq from SPI Flash

    # Core.
    soc.check_if_exists(name)
    spiflash = SpiFlash(
        pads         = soc.platform.request(name if mode == "1x" else name + mode),
        dummy        = dummy_cycles,
        div          = ceil(soc.clk_freq/clk_freq),
        with_bitbang = True,
        endianness   = soc.cpu.endianness)
    spiflash.add_clk_primitive(soc.platform.device)
    setattr(soc.submodules, name, spiflash)
    spiflash_region = SoCRegion(origin=soc.mem_map.get(name, None), size=0x1000000) # FIXME: Get size from SPI Flash
    soc.bus.add_slave(name=name, slave=spiflash.bus, region=spiflash_region)
