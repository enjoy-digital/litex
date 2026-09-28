# LiteX Architecture and Portability

LiteX projects should keep protocol behavior separate from device primitives and
board policy. A design is portable when a new device or board can be supported
without copying its protocol implementation or changing existing public ports.
This document complements [coding_style.md](coding_style.md), which covers how
to write the code within each layer.

## Put Each Decision in Its Owning Layer

| Layer | Owns | Does not own |
| --- | --- | --- |
| Protocol core | Framing, encoding, state machines, and stream behavior | Vendor primitives, board pins, and reference-clock selection |
| Device adapter | Primitive configuration, gearbox cadence, reset sequence, clock domains, and polarity | Packet or protocol policy |
| Integration wrapper | Stable stream/control/CSR interface and the connections between core and adapter | A second copy of the core or device implementation |
| Platform and target | Pins, reference clocks, available channels, and timing constraints | Protocol logic or a private copy of a reusable adapter |

Share a block at the lowest layer where its behavior is truly the same. Use an
existing LiteX or companion-project block before adding a local copy. In the
Ethernet stack, LiteEth owns the Ethernet PCS and PHY integration, while
LiteICLink supplies reusable transceiver PLL, DRP, and initialization helpers.
The surrounding LiteX target selects the pads, clock source, and transceiver
channel. Keep dependencies in that direction so a generic link block does not
need to import an Ethernet protocol block.

Sharing a transceiver primitive requires matching its data mode and control
contract, not just its device family. For example, an 8b/10b SerDes with a
20/40-bit interface is not a drop-in replacement for a 64b/66b Ethernet PMA
with a 64-bit block, two sync-header bits, bitslip, and gearbox enable. Reuse
its PLL, DRP, or reset helpers where their timing contract matches; retain a
small protocol-specific PMA adapter for the mode-specific primitive ports.

## Define the Boundary Before Adding a Device

Write down the wrapper's public contract before implementing a new variant:

* Data width and direction of each stream or block interface. State whether
  `valid`/`ready` can stall inside a frame.
* Clock domains, their expected frequencies, and who creates each clock and
  reset. Name every clock-domain crossing and use the existing CDC helpers.
* Reset and lock ordering, including any cross-domain requests and pulse
  widths. Keep vendor-specific sequencing in the device adapter.
* Optional capabilities such as loopback, PRBS, polarity, diagnostics, and
  timing constraints. Make unsupported combinations explicit.
* Rate and reference-clock combinations checked in simulation and on hardware.
  Keep measured or wizard-derived settings beside the adapter that uses them.

Use the same contract for every implementation of a protocol. A 7-series and
an UltraScale+ Ethernet PMA can expose the same block/header/bitslip interface
even when their gearboxes advance at different rates. The wrapper connects the
PCS enable to the PMA's block cadence; the PCS need not know the device family.

## Choose Reuse Carefully

Prefer parameters or a small shared helper when variants have identical signal
meaning and timing. Keep separate implementations when a primitive changes
gearbox width, reset ordering, clock topology, or calibration behavior. Avoid
large inheritance trees whose overrides silently change hardware timing. Keep
vendor `Instance` parameters visible and group rate-dependent values so a
reviewer can compare them against the relevant device documentation or a
generated configuration.

Preserve public class names, constructor arguments, CSR layouts, and clock
domain names when refactoring an existing wrapper. If a new shared module
changes a boundary, provide compatibility aliases or a migration path rather
than changing every board target at once.

## Validate a New Port or Refactor

1. Run protocol simulation with the device adapter replaced by a model. Cover
   packet boundaries, backpressure, reset, and error paths.
2. Elaborate every supported device/rate combination. Check primitive names,
   clock domains, connected ports, and rate-dependent parameters in the
   generated design. A Python import alone does not establish that a wrapper
   can be instantiated.
3. Compare generated primitive parameters and timing constraints before and
   after a refactor. Keep any intentional changes small and explained.
4. Run the existing project test suite and at least one representative target
   build when the toolchain is available. Record untested boards and rates in
   the pull request.
5. Confirm link-up, traffic, reset recovery, and diagnostics on hardware before
   claiming a new transceiver configuration is validated there. Simulation and
   elaboration cannot establish analog behavior or timing closure.

For an Ethernet port, the usual sequence is: reuse the protocol PCS, select a
PMA that satisfies its interface, reuse applicable LiteICLink clock/reset/DRP
helpers, connect them in a PHY wrapper, and put board-specific pad and clock
selection in the target. Add another PMA only when the existing one cannot
express the device's gearbox or reset behavior.

Byte-oriented stream interfaces should use the payload mask convention described in
[stream_byte_enables.md](stream_byte_enables.md). Keep any legacy encoding adapters
at integration boundaries so reusable datapaths use a single representation.
