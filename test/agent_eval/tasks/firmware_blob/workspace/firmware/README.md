# Sampler firmware v2.3 (prebuilt)

Delivered as a binary only (`sampler.bin`, linked at 0x40000000, booted by the BIOS from main
RAM); the sources are not available and the firmware cannot be rebuilt.

The firmware converts the 4 channels of the ADC (`adc` CSRs) in turn and prints one line per pass
on the console:

    pass <n>: ch0=0x... ch1=0x... ch2=0x... ch3=0x... channel check: OK|FAIL

`channel check` fails when two channels return the same value (stuck multiplexer).
