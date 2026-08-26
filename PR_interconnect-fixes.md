# soc/interconnect: Fix protocol/RTL bugs and tighten validation (review fixes)

This PR is the result of a systematic review of `litex/soc/interconnect/` (wishbone, ahb, avalon, axi/, stream, packet, csr) for protocol/RTL bugs and validation gaps, following the same approach as #bios-fixes and #integration-fixes. 11 commits, one fix per commit. **Every RTL fix was confirmed by migen simulation, both for the bug and the fix.**

## Protocol/RTL bugs (all simulation-confirmed)

- **AHB2Wishbone**: SEQUENTIAL burst beats were silently dropped (an INCR/WRAP burst lost every beat after the first, OKAY-ed without generating a Wishbone access); Wishbone errors never reached the AHB master (HRESP only driven while HREADY was low; err-only slaves deadlocked the bridge); oversized transfer sizes were OKAY-ed. Now converts SEQ beats and issues proper two-cycle AHB ERROR responses.
- **wishbone.DownConverter**: ignored `slave.err` entirely - an err-only sub-access hung the master forever and an err+ack completion returned corrupt data as a clean ack. Errors now latch across sub-accesses and terminate the master cycle with `err`.
- **AXIDownConverter**: the narrow burst length `((len+1) << log2(ratio)) - 1` overflows the 8-bit AXI len field for wide bursts longer than 256/ratio beats (a 129-beat 64→32 burst became 2 narrow beats) - long INCR bursts now route through the per-wide-beat slow path with advancing addresses, verified end-to-end through an AXISRAM; the wide R channel id/resp were registered unconditionally, violating AXI stability while the master stalled and losing errors on non-final sub-beats (now captured per wide beat with worst-of resp accumulation); single-beat sub-width transfers returned wrong bytes (narrow side now always runs full-width beats, with data steered through strobes/lanes).
- **AXIDecoder/AXILiteDecoder**: a new command decoding to a *different* slave was presented through the held (old) selection while responses were pending - accepted by the wrong slave with spec-legal pipelined slaves. Commands are now held until responses drain unless they target the already-selected slave.
- **AXI2AXILite**: `r.last` was derived from "all ARs issued", marking the wrong beat with pipelined AXI-Lite slaves (orphaned R beats mis-delivered to the next read); slave error responses were hardcoded to OKAY and B was answered before the per-beat lite responses were collected; the write path could exit before all AW beats were issued. Affects `AXI2Wishbone` and `AXISRAM`, which build on it.
- **Packetizer/Depacketizer/PacketFIFO**: the Packetizer's unaligned path captured its boundary register on invalid cycles - livelocking single-beat packets and corrupting data on protocol-legal bubbles (the fix also clears the kept `last`, which otherwise leaks into the next packet - caught by the 128-bit loopback test); PacketFIFO re-enqueued params every cycle while a packet's last beat was stalled, later replaying endless phantom packets; the Depacketizer merged header-only/truncated packets into the next packet; headers narrower than the datapath now rejected at elaboration.
- **CSRStorage atomic_write with `ordering="little"`**: the commit was hardcoded to word 0 (correct only for big ordering) - the MSB words of a multi-word atomic register were simply lost. Now commits on the last word in address order for both orderings.

## Validation / Python fixes

- **wishbone**: converters never validated the *slave's* addressing (copy-pasted duplicate assert on the master); interconnects accepted mixed word/byte-addressed ports (silent 4x address mis-routing); Cache accepted byte addressing (scrambled tag/line/offset split) and crashed cryptically on `cachesize=0` with width mismatch; SRAM reported `mode="rw"` for memories promoted to read-only.
- **avalon**: `address_width` was silently ignored (dead kwargs branch checking the wrong key, with a latent `NameError`); `like()` dropped `adr_width`.
- **axi misc**: `Wishbone2AXILite` hardcoded `base_address//4` (wrong for 64-bit and byte-addressed Wishbone; propagates to `Wishbone2AXI`); `AXILite2CSR()` defaults raised `NameError` (missing import) with an 8-vs-32-bit width mismatch; write-only/read-only `AXILiteSRAM` accepted commands it could never answer (master deadlock); `connect_axi()` mutated the caller's `omit` set; Remappers silently floored non-power-of-2 sizes (region aliasing).
- **stream/csr**: `Unpack`/`Pack` mutated the caller's `EndpointDescription` in place; EventManager register descriptions leaked the last source's text and a zero-source EventManager crashed; single-word CSRStorage simple CSR naming aligned with CSRStatus (`name` instead of `name0`, generated Verilog naming only); `packet.Arbiter` honored `**kwargs` in only one of its two paths.

## Known limitations (documented, intentionally not changed here)

- `stream.Crossbar` remains a stub (its wiring was added and reverted upstream without stated rationale).
- AXI timeouts only cover command-channel stalls; Packetizer has no `last_be` (padding bytes on the final unaligned beat); PacketFIFO deadlocks by design on packets longer than `payload_depth`; DownConverter WRAP bursts with ratio > 16 remain unsupported.

## Verification

- **292 tests pass** (all 12 interconnect test suites + test_soc; 196-test pre-fix baseline of the same suites used as the regression gate).
- Dedicated simulations for every RTL fix: AHB burst/error scenarios, converter error forwarding, 129-beat AXI burst end-to-end through AXISRAM, decoder cross-slave routing with pipelined slaves, AXI2AXILite last/resp with delayed slaves, packet livelock/bubble/phantom-packet scenarios, atomic_write for both orderings including non-busword-multiple sizes.
- `litex_sim` builds pass for the featured config, serv, and `--bus-standard axi-lite`; end-to-end Verilator run boots the BIOS to the `litex>` prompt.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
