# Experimental USNative BIOS initialization

This adds an explicit BIOS startup path for the XEM8320 x16 native DDR4
integration. It is an initial board-specific calibration driver, not a
portable implementation for every UltraScale board. The coordinated LiteDRAM
feature branch supplies the complete initial PHY/CSR ABI; the litex-boards
feature branch selects it explicitly for Vivado.

## Default operation

A board target opts in with:

```python
self.add_config("SDRAM_USNATIVE_XEM8320")
```

`sdram_init()` then runs native readiness initialization, direct-DFII clock and
lane searches, CPU-based per-DQ read deskew and measured +/-4-tap guards. After
successful calibration, the existing BIOS controller handoff and memory check
run normally. Startup prints the selected profile, success or an error; it does
not print per-tap scans or use DMA. Other PHYs and the existing custom-init hook
keep their existing initialization paths. When both native and custom-init flags
are present, the native driver takes precedence; new targets should use only the
native flag unless they explicitly need another custom hook elsewhere.

Training writes memory and must run from ROM/SRAM before applications use DDR.
The CPU deskew scratch region is 2 MiB at 0x41000000; direct DFII searches also
write training rows. This is not a non-destructive runtime retraining service.
On calibration or final memory-check failure, DDR remains in reset and under
software ownership, and the existing DDRCTRL error/status reporting is updated.

## Optional build features

```python
# Optional detailed scan output and diagnostic snapshot CSRs.
self.add_config("SDRAM_USNATIVE_DEBUG")

# Optional counter/PRBS refinement using the local 256-bit DMA engine.
self.add_config("SDRAM_USNATIVE_DMA_CALIBRATION")
```

These options are independent and disabled by default. DMA refinement requires
a 256-bit DMA CSR interface, per-DQ error mask and its hardware timeout.
It destroys 64 MiB starting at 0x41000000. Software also bounds polling when the
hardware completion response never arrives. A failed/stuck DMA transaction must
be reset/quiesced by the system before another attempt; firmware cannot cancel
an already issued memory operation through this interface.

The optional DMA benchmark command is compiled only when the board target
instantiates its DMA hardware and selects `CONFIG_SDRAM_NATIVE_DMA_TEST`.
Debug hardware is also a separate board-target choice. Required delay
selection, RIU and readiness CSRs are calibration controls, even when verbose
diagnostics are off.

## Supported initial interface

- XEM8320 x16 DDR4, four 32-bit DFI phases, eight-bit serializers, 512 delay taps,
  eight bitslips and registered TX with command latency 5.
- 2400 MT/s: controller 300 MHz, CL17/CWL12, RD2/WR3.
- 2666.667 MT/s: controller 333333333 Hz, CL19/CWL14, RD0/WR1.
- Experimental 2933.333 MT/s: controller 366666666/7 Hz, CL21/CWL16,
  RD2/WR3; requires the overclock configuration.
- Experimental 3200 MT/s: controller 400 MHz, CL24/CWL16, generated RD3/WR3,
  operating RD2/WR3 after BIOS initialization;
  requires the overclock configuration.
- Related sys:RIU clocks 2:1, acknowledged RIU bridge and registered tap-status
  freshness. Physical tap indices and nibble ownership match the existing
  XEM8320 integration; a new board must not simply reuse this flag.
- Generated JEDEC initialization and memory timing settings remain the target's
  responsibility. Unsupported widths, phase/latency profiles, inadequate scratch
  memory and missing required CSR capabilities fail at compile time.

The firmware and PHY share one configuration: direct read/write commands use the
same operating phase as controller traffic. At 3200 MT/s the firmware
selects read phase 2 rather than the generated CSR reset phase 3. The SDRAM frequency API
returns an unsigned frequency so rates above 2147 MT/s display correctly.

## Validation and remaining integration

Eleven host C tests cover profile rejection, overclock opt-in, optional DMA
requirements, phase selection, RIU/tap wait failures, DMA completion bounds,
the debug-disabled deskew seed, init failure ownership, final memory-test
failure and unsigned speed reporting. Run:

```sh
python -m pytest test/software/test_usnative.py test/software/test_litedram_accessors.py
```

The 2400 and 2666.667 BIOS configurations compile and link using the generated
SoC headers. The DMA-enabled 2666.667 configuration also compiles with the
optional `native_dma` command. See the hardware qualification section below for
the narrower set of configurations that have been exercised on hardware.

The current interface still has board-specific tap/nibble indices and bootstrap
settings. A future portable interface should provide these as generated PHY
metadata. Runtime retraining also needs an explicit controller/DMA quiesce
contract. No thermal or runtime background retraining is included.

## Coordinated board options and overclock profiles

The board target's `--with-dma` selects `CONFIG_SDRAM_NATIVE_DMA_TEST`, which
compiles the optional `native_dma` BIOS command. This is explicit destructive
bandwidth/integrity testing after normal calibration, not automatic DMA-based
calibration refinement. The default engine uses a 128/256-bit width-converted
native port. Write and read rates are reported independently, using hardware
cycle counts; percentage efficiency uses the physical x16 DDR peak rather than
DMA port width.

When the target selects `CONFIG_SDRAM_NATIVE_DMA_BANK_GROUP_INTERLEAVING`, the
same command reports `mode=paired-bank-group-interleaved`. This opt-in hardware
uses two 128-bit bank-group streams as one 256-bit benchmark interface and waits
for both write paths to drain before starting reads. A sticky error from either
stream prevents further traffic through the engine. The standard native-port
mode remains the default. Firmware DMA refinement is selected through
`CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION`; the XEM8320 target enables it for native
256-bit DMA performance/example builds, with either converted or paired traffic.

The board's explicit `--usnative-dma-calibration` option selects that firmware
refinement only when USNative, DMA, and a 256-bit
DMA interface are all enabled. It is independent of `--usnative-debug`: debug
controls verbose scan output, while DMA calibration controls the destructive
counter/PRBS refinement itself. CPU-only, native128 DMA and component-PHY builds
retain their existing initialization policy. The refinement uses scratch memory
through `0x44ffffff`, requires the DMA engine's per-DQ
error-mask CSR, and runs during `sdram_init` before the final BIOS memory test.

The optional command also supports component `USPDDRPHY` builds. These select
`CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION` and provide the
`dma_bench_software_ready` CSR. `sdram_init()` clears admission before each
initialization and grants it only after standard leveling and the final
controller-path memory test complete. A failed or interrupted reinitialization
therefore leaves the hardware gate closed. The `sdram_cal` diagnostic revokes
admission because leveling alone does not validate normal controller traffic;
run `sdram_init` before using DMA again. Component-PHY debug uses LiteDRAM's
existing leveling output and commands, not HSSIO bit-slice window reporting.
Targets may map a component-PHY debug option to `CONFIG_SDRAM_PHY_DEBUG` to
include command-delay scans and write-latency calibration samples. It remains
separate from USNative debugging and does not enable DMA.

For `USDDRPHY` and `USPDDRPHY`, repeated initialization wraps each DQS output
delay back to its base before asserting the global PHY reset. The global reset
clears DQ output delay, so this preparation keeps the DQ and software-tracked
DQS offsets coherent when leveling starts again. It does not affect the
USNative initialization path.

The restoration loop is bounded to one complete delay range. A status counter
that does not advance now fails initialization before global reset or JEDEC
commands instead of hanging. The standard leveling wrapper also propagates an
existing write-leveling failure and skips later training, the final memory test,
and DMA admission. Host tests inject both failures and verify those control
paths; normal hardware testing exercised the candidate without injecting a PHY
fault. Write-latency, write DQ-DQS, and read-leveling routines still expose void
or otherwise incomplete stage results, so full per-stage failure propagation is
deferred.

The BIOS DMA completion wait uses LiteX's hardware timer instead of a fixed CPU
poll count. Its deadline covers two complete DMA hardware timeout intervals
plus a settling margin, with the conversion performed from system-clock cycles
using 64-bit arithmetic. This permits large transfers to finish without making
the safety timeout depend on CPU execution speed.

The 2933.333 and 3200 profiles require `CONFIG_SDRAM_USNATIVE_OVERCLOCK` in
addition to the native profile. Their CL/CWL and read-gate delays differ from
the initial 2400/2666.667 profiles. The BIOS identifies overclock operation at
startup. Acceptance of a profile is not timing or hardware qualification.

Debug logs provide direct RX/TX search endpoints and final per-bit RX deskew
windows. Report spans as last-first taps, together with scan step and censored
search boundaries. These measurements do not constitute full eye or thermal scans.

## Hardware qualification status

The 2400 MT/s, debug-disabled XEM8320 build passed three calibration runs—an
FPGA load, a reboot, and an explicit `sdram_init`—and three BIOS memory tests
after making the RX deskew pattern seed unconditional. CPU memory-speed
measurements were 44.6 MiB/s write and 48.7 MiB/s read. These CPU-loop figures
measure the firmware access path, not the sustained bandwidth available through
a native DMA port.

The 2666.667 MT/s debug/DMA256 build also passed calibration and memory tests.
Its 2 MiB CPU test measured 49.3 MiB/s write and 54.6 MiB/s read. Both 64 MiB
counter and PRBS31 DMA tests passed with zero errors and no fault: writes were
2.402195 and 2.400797 GB/s (45.04% and 45.01% of physical peak), and reads were
2.420201 and 2.420200 GB/s (45.37%). This uses the standard controller and a
width-converted port, so the result is not comparable to the older paired-port
engine without accounting for that architecture.

That converted-port result is historical rather than current qualification. A
later 2666.667 MT/s run reported 153 errors with the primary counter pattern,
while its PRBS transfer and CPU guard checks passed. Those passing checks do not
identify the cause of the counter failure or establish that the converted path
is reliable. The converted 2666.667 MT/s configuration therefore remains
unqualified pending hardware reproduction from the current sources.

Final component-`USPDDRPHY` hardware testing covered three configurations. Each
passed three initialization runs, three mandatory controller-path memory tests,
and five DMA tests including a full 1 GiB PRBS write and reread.

| DDR rate | DMA interface | DMA write/read | Physical-peak efficiency |
|---:|---|---:|---:|
| 1000 MT/s | 128-bit standard | 0.905 / 0.918 GB/s | 45.24% / 45.90% |
| 1000 MT/s | 256-bit paired bank groups | 1.797 / 1.815 GB/s | 89.85% / 90.77% |
| 2000 MT/s | 256-bit paired bank groups | 3.569 / 3.584 GB/s | 89.23% / 89.60% |

Both paired configurations passed CPU/DMA interoperability tests. The 1000
MT/s paired build also verified the admission contract: calibration-only and a
subsequent standalone memory test left DMA closed, while full initialization
restored access. The hardware-timer completion deadline passed the 1 GiB tests.
These builds retain the upstream component-PHY RTL and use the BIOS pre-reset
DQS restoration described above.

The 1000 MT/s implementations passed setup, hold, and pulse-width timing. The
2000 MT/s implementation had positive fabric setup and hold slack but a
`-0.600 ns` clock pulse-width slack, so it remains an experimental hardware
result rather than a timing-qualified component-PHY configuration. Its reported
read-leveling windows are standard PHY half-windows, not HSSIO bit-slice eyes.

The packaged 2933.333 and 3200 MT/s configurations have not yet completed
hardware qualification. Both are overclock profiles and must remain explicitly
opt-in.


## 3200 MT/s bootstrap profile

The 3200-only firmware profile selects read phase 2 for both direct-DFII probes
and controller traffic, with initial TX DQ/DM delay 72 and RX delay 48. The
matching XEM8320 target selects DQ EQ_LEVEL3 while leaving DQS at EQ_LEVEL2.
Other speed profiles retain their existing phases, bootstrap delays and receiver
settings. The BIOS banner reports the operating phase rather than its CSR reset.

These seeds are not final calibrated taps: normal CK/RX/TX searches, per-bit
read deskew, guards and the final memory test must still pass. CK failures now
distinguish an insufficient passing window from failed center confirmation.
Verbose per-CK error counts remain controlled by the native debug option.

This is still an explicit experimental overclock. Successful functional tests
do not remove the primitive clock violations or PLL VCO limit warning.


## Full retries and explicit BISC diagnostics

`sdram_init` always runs full native training and the final controller memory
test, including after a failed attempt. The safe `bisc_only` CSR state left by
failure no longer selects the next operation. Existing CSR-based debug scripts
must use `sdram_bisc` to request the internal-delay diagnostic explicitly.
`sdram_bisc` is available only with native debug firmware, holds DDR reset and
software DFI ownership, and leaves DDR/DMA unavailable even on a BISC PASS.
Use `sdram_init` afterward to restore memory operation.

CK errors retain their numeric codes and report distinct initialization,
insufficient-window, center-initialization and center-burst failures. Per-tap
error counts remain debug-only. No passing-window or guard requirement changes.

Matching XEM8320 targets provide software DMA admission for both PHYs. Full
initialization revokes admission and grants it only after the controller memory
test succeeds; builds disabling that test cannot grant DMA admission. Explicit
DMA-assisted native calibration briefly grants access inside the refinement
step and revokes it on return, including failure. PHY readiness, training state,
DFI ownership and sticky hardware faults remain additional hardware gates.
Fatal DMA faults still require FPGA reconfiguration.


### Bounded 3200 TX-window recovery

At 3200 only, an undersized direct TX window can trigger four nearby RX trials
(+4, +8, -4, then -8 taps). Each RX candidate stays at least four taps inside the
previously measured RX window. A candidate is accepted only when two complete
TX scans have an intersection of at least 32 taps and its center confirms.
Delay-programming and center-confirmation failures do not trigger this fallback.
The final direct-burst check, per-bit RX deskew, guards and controller memory
test remain mandatory. Exhaustion fails calibration and leaves DDR/DMA closed.
Other profiles keep the original search behavior. Retry attempts and accepted
windows are reported even with debug disabled; detailed lane summaries are
available with debug enabled. This does not qualify the overclock's static
primitive timing or replace power-cycle/temperature testing.


### Optional DMA guard recovery

The initial DMA eye sweep changes all RX DQs together and reads a previously
written pattern. A disagreement with the later fresh write/read guards can
therefore justify a new measurement; it is not proof that the global sweep
caused a hardware failure.

On guard-window exhaustion or a center failure, refinement remeasures the affected
DQs (including earlier failing guards) one at a time, holding every other DQ at its selected center. Each DQ is
scanned from tap 12 through 68 and back at two-tap spacing, using fresh 64 MiB
counter and PRBS write/read transfers at every point. The accepted window is the
longest contiguous intersection of all four observations, with at least five
samples. All six center/+/-4-tap guards restart after changing a center. No guard
margin is relaxed, no unmeasured taps are accepted, and there is only one such
recovery budget per initialization. A subsequent guard failure retains the
existing bounded two-tap adjustment within the new measured bounds or fails.

For example, a measured 22..34 window permits guarded centers only at 26, 28 or
30. Persistent failure there must fail initialization; moving to 32 is invalid.
DMA engine/poll timeout, inconsistent error count/mask, or delay-programming
failure immediately aborts. Normal final memory testing and software admission
remain mandatory.

The fallback adds exactly 116 DMA transactions per reported failing DQ, at most
1,856 for all sixteen DQs. Including the original sweep, sixteen guard attempts
and final confirmation, an upper bound is 2,014 transactions: 125.875 GiB read
and 122.25 GiB written. This is an opt-in destructive startup diagnostic with a
potentially substantial startup cost, not normal initialization. The host C
regressions exercise repeat-scan intersections, nonoverlap, the original narrow
window, other-DQ center preservation, engine/delay failures, restarted guards,
and exhaustion without a second recovery. Hardware qualification is tracked in
the board validation report; these host tests alone do not resolve the recorded
hardware failures.


Optional DMA calibration accepts both converted256 and paired256 benchmark
interfaces. Firmware selects it through `CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION`.
The XEM8320 target enables this for native 256-bit DMA performance/example builds;
CPU-only and component-PHY builds keep their normal initialization. The explicit
`--usnative-dma-calibration` request also remains available. Firmware requires the
benchmark error-mask CSRs and checks the actual DMA data-width CSR equals 256
before training. This preserves fixed 64 MiB transaction beat-count checks.
The same measured-window and guard rules apply to both paths, using whichever
traffic schedule the selected DMA engine produces. Enabling this option is not
by itself hardware qualification of either interface.


PHY or mode-register mutation invalidates DMA admission. Entering software DFI
control clears the optional software-ready CSR, and returning hardware ownership
does not set it. BIOS read/write-phase commands also invalidate admission before
their direct CSR writes. Delay/bitslip overrides, standalone leveling and mode
register commands enter software control and therefore follow the same rule.
Only a complete successful initialization and final controller-path memory test
re-establish normal admission; internal DMA refinement retains its scoped grant.
Read-only status commands and builds without software DMA admission are unchanged.
