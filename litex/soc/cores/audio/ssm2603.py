#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import Cat, If, Mux, Signal
from migen.genlib.cdc import MultiReg

from litex.gen import LiteXModule
from litex.soc.cores.bitbang import I2CMaster

from litex.soc.cores.audio.pcm import PCM
from litex.soc.interconnect.csr import CSRStatus, CSRStorage


# Normal mode, symmetric ADC/DAC rates with MCLK = 256 × sample rate.
# See the SSM2603 datasheet, Table 30.
_SAMPLE_RATE_SETTINGS = {44_100: 0x020, 48_000: 0x000}

_WORD_LENGTH_SETTINGS = {16: 0, 20: 1, 24: 2, 32: 3}


def _sample_rate_setting(sample_rate):
    if sample_rate not in _SAMPLE_RATE_SETTINGS:
        raise ValueError("SSM2603 sample_rate must be 44100 or 48000 Hz.")
    return _SAMPLE_RATE_SETTINGS[sample_rate]


def _word_length_setting(sample_width):
    if not isinstance(sample_width, int) or sample_width not in _WORD_LENGTH_SETTINGS:
        raise ValueError("SSM2603 sample_width must be 16, 20, 24 or 32 bits.")
    return _WORD_LENGTH_SETTINGS[sample_width]


class SSM2603(LiteXModule):
    """BIOS initialization for an SSM2603 clock peripheral.

    The design supplies MCLK, bit clock, and separate ADC and DAC frame clocks.
    This configuration uses left-justified samples at 256 MCLK cycles
    per frame, with stereo line input and DAC playback enabled.

    Parameters
    ----------
    soc : SoCCore
        SoC that provides the I2C master and receives the BIOS configuration.
    i2c_name : str
        Name of the SoC's bit-banged I2CMaster attribute.
    address : int
        Seven-bit I2C address, 0x1a (default) or 0x1b.
    output_gain : int
        Initial seven-bit output gain register value. Defaults to 0x75.
    vmid_delay_us : int
        Bias settling time in microseconds. Defaults to 75,000.
    sample_rate : int
        Sample rate in Hz, 48,000 (default) or 44,100.
    sample_width : int
        Serial bits per sample, 16 (default), 20, 24 or 32.
    """

    def __init__(self, soc, i2c_name, address=0x1a, output_gain=0x75, vmid_delay_us=75_000, *, sample_rate=48_000, sample_width=16):
        if address not in (0x1a, 0x1b):
            raise ValueError("SSM2603 address must be 0x1a or 0x1b.")
        if not 0 <= output_gain <= 0x7f:
            raise ValueError("SSM2603 output gain must be a 7-bit register value.")
        if vmid_delay_us < 0:
            raise ValueError("SSM2603 VMID delay must be non-negative.")

        if not isinstance(getattr(soc, i2c_name, None), I2CMaster):
            raise ValueError("SSM2603 requires a named SoC I2CMaster.")

        rate_setting = _sample_rate_setting(sample_rate)
        word_length = _word_length_setting(sample_width)
        soc.add_config("SSM2603_I2C_BUS", i2c_name)
        soc.add_config("SSM2603_I2C_ADDRESS", address)
        soc.add_config("SSM2603_OUTPUT_GAIN", output_gain)
        soc.add_config("SSM2603_VMID_DELAY_US", vmid_delay_us)
        soc.add_config("SSM2603_INTERFACE", (word_length << 2) | 1)
        soc.add_config("SSM2603_SAMPLING", rate_setting)


class SSM2603PCM(PCM):
    """Stereo playback and stereo line-in capture.

    Pass the same sample rate and width to the codec control core. Supply MCLK and an
    `audio` clock domain at `sample_rate * 256`.
    Use the CSR name `audio` and set `AUDIO_PCM_RATE` to `sample_rate` to
    enable BIOS tone playback.

    Parameters
    ----------
    pads : Record
        Codec pins with xck, bclk, daclrck, adclrck, dacdat and adcdat fields.
    master_clk : Signal
        Master clock sent to the codec on xck, at 256 times the sample rate.
    sample_rate : int
        Sample rate in Hz, 48,000 (default) or 44,100.
    sample_width : int
        Serial bits per sample, 16 (default), 20, 24 or 32. In 32-bit mode,
        the codec's 24-bit ADC fills the low eight bits with zeros.
    playback_bus : wishbone.Interface or None
        Optional DMA read port. Use 32 bits at 16-bit PCM, otherwise 64 bits.
    capture_bus : wishbone.Interface or None
        Optional DMA write port, separate from the playback port and of the
        same required width.
    """

    def __init__(self, pads, master_clk, *, sample_rate=48_000, sample_width=16,
        playback_bus=None, capture_bus=None):
        _sample_rate_setting(sample_rate)
        _word_length_setting(sample_width)
        super().__init__(sample_width=sample_width, playback_bus=playback_bus, capture_bus=capture_bus)
        # Use power-of-two slots for an exact BCLK divider from 256 × fs.
        slot_width = 16 if sample_width == 16 else 32
        padding = slot_width - sample_width
        self.sample_rate = int(sample_rate)
        self.master_clk_freq = 256 * self.sample_rate
        # The self-test uses an even number of frames per square-wave period.
        half_period = round(self.sample_rate / 2000)
        period = 2 * half_period
        half_bclk = 256 // (4 * slot_width)
        divider = Signal(max=half_bclk)
        bclk = Signal()
        left_slot = Signal()
        slot_bit = Signal(max=slot_width)
        bit_tick = divider == half_bclk - 1
        falling = bit_tick & bclk
        end_slot = slot_bit == slot_width - 1
        next_frame = falling & end_slot & ~left_slot
        self.sync.audio += [
            If(bit_tick,
                divider.eq(0),
                bclk.eq(~bclk),
            ).Else(divider.eq(divider + 1)),
            If(falling,
                If(end_slot, left_slot.eq(~left_slot)),
                slot_bit.eq(slot_bit + 1),
            ),
        ]
        self.comb += [
            pads.xck.eq(master_clk),
            pads.bclk.eq(bclk),
            pads.daclrck.eq(left_slot),
            pads.adclrck.eq(left_slot),
        ]

        self.tone = CSRStorage(description="Play a square wave near 1 kHz for an output test.")

        tone = Signal()
        test = Signal()
        self.specials += MultiReg(self.tone.storage, tone, odomain="audio")
        counter = Signal(max=period)
        right = Signal(sample_width)
        tx_shift = Signal(slot_width)
        test_sample = Signal(sample_width)
        frame = Signal(2 * sample_width)
        self.comb += [
            test_sample.eq(Mux(counter < half_period,
                4096 << (sample_width - 16), 0xf000 << (sample_width - 16))),
            frame.eq(Mux(tone | test, Cat(test_sample, test_sample), self.playback.sample)),
            self.playback.ready.eq(next_frame & ~(tone | test)),
            pads.dacdat.eq(tx_shift[-1]),
        ]
        self.sync.audio += If(falling,
            If(end_slot,
                If(left_slot,
                    tx_shift.eq(right << padding),
                ).Else(
                    tx_shift.eq(frame[:sample_width] << padding),
                    right.eq(frame[sample_width:]),
                    If(counter == period - 1, counter.eq(0)).Else(counter.eq(counter + 1)),
                ),
            ).Else(tx_shift.eq(tx_shift << 1)),
        )
        activity = Signal(2)
        self.sync.audio += If(next_frame,
            If(frame[sample_width - 1] | frame[-1], activity[1].eq(1)),
            If((~frame[sample_width - 1] & (frame[:sample_width] != 0)) |
               (~frame[-1] & (frame[sample_width:] != 0)), activity[0].eq(1)),
        )
        self.activity = CSRStatus(2, description="PCM activity: positive and negative samples serialized.")
        self.specials += MultiReg(activity, self.activity.status)

        # Sample ADC data one MCLK cycle after the rising BCLK edge.
        sample_bit = Signal()
        self.sync.audio += sample_bit.eq(bit_tick & ~bclk)
        rx_shift = Signal(sample_width)
        left = Signal(sample_width)
        have_left = Signal()
        word = Cat(pads.adcdat, rx_shift[:-1])
        end_sample = sample_bit & (slot_bit == sample_width - 1)
        right_done = end_sample & ~left_slot
        self.sync.audio += [
            If(sample_bit, rx_shift.eq(word)),
            If(end_sample & left_slot, left.eq(word), have_left.eq(1)),
        ]
        self.comb += [
            self.record.valid.eq(have_left & right_done),
            self.record.sample.eq(Cat(left, word)),
        ]

        self.loopback = CSRStorage(description="Enable the test tone and check the external analog loopback.")
        self.loopback_result = CSRStatus(3, description="Bit 0 done, bit 1 left passed, bit 2 right passed.")
        done = Signal()
        count = Signal(11)
        passed = Signal(2)
        self.specials += [
            MultiReg(self.loopback.storage, test, odomain="audio"),
            MultiReg(Cat(done, passed), self.loopback_result.status),
        ]
        # Ignore the first 1024 frames while the analog path settles.
        # In the next 1024, a full period repeats its sign, and
        # a half-period reverses it. Require measurable amplitude.
        self.sync.audio += If(~test,
            count.eq(0), done.eq(0), passed.eq(0),
        ).Elif(right_done & have_left & ~done,
            count.eq(count + 1),
            If(count == 2047, done.eq(1)),
        )
        for lane, sample_in in enumerate((left, word)):
            history = Signal(period)
            matches = Signal(11)
            threshold = 16 << (sample_width - 16)
            strong = (sample_in > threshold) & (sample_in < (1 << sample_width) - threshold)
            sign = sample_in[-1]
            match = strong & (sign == history[period - 1]) & (sign != history[half_period - 1])
            self.sync.audio += If(~test,
                history.eq(0), matches.eq(0),
            ).Elif(right_done & have_left & ~done,
                history.eq(Cat(sign, history[:-1])),
                If(count[10] & match, matches.eq(matches + 1)),
                If(count == 2047, passed[lane].eq(matches >= 900)),
            )
