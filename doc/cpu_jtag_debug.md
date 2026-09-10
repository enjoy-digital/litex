# CPU debugging through the FPGA JTAG port

`--with-cpu-jtag-debug` connects an enabled CPU JTAG instruction interface to
a Xilinx USER chain. It allows OpenOCD/GDB to use the FPGA's existing JTAG cable
without routing a separate CPU TAP to external pins.

This option connects the transport; the CPU's own options select its debug
implementation. For VexRiscv-SMP's official RISC-V debug module on Arty:

```sh
python3 -m litex_boards.targets.digilent_arty \
    --cpu-type=vexriscv_smp --cpu-count=1 \
    --with-privileged-debug --hardware-breakpoints=2 \
    --with-cpu-jtag-debug --build --load
```

Without `--with-cpu-jtag-debug`, no CPU USER-chain connection is added, even
when the CPU's debug module is enabled. Do not combine it with an external
CPU TAP (`--jtag-tap` on VexRiscv-SMP). Custom targets can instead call
`soc.add_cpu_jtag_debug(chain=4, clk_freq=10e6, clock_domain="sys")` after adding
the CPU. The CPU must expose the `jtag_clk`, `jtag_tdi`, `jtag_tdo`,
`jtag_enable`, `jtag_capture`, `jtag_shift`, `jtag_update` and `jtag_reset`
instruction signals, with clock-domain crossing implemented in its debug
transport. This interface is also used by NaxRiscv and VexiiRiscv when their
JTAG instruction option is enabled.

## Chain allocation and timing

- `--cpu-jtag-debug-chain=N` selects USER1 through USER4; the default is USER4.
- `--cpu-jtag-debug-clk-freq=10e6` specifies the maximum TCK frequency for
  timing analysis. It does not program the cable speed. Configure OpenOCD
  at or below this frequency and rebuild if increasing the limit.
- JTAGBone and JTAG UART normally use USER1, so they can coexist with CPU
  debug on USER4. The same chain cannot be assigned to two users. Pass the
  platform to any custom `XilinxJTAG` instance so it participates in the
  allocation checks; raw vendor `Instance` objects are not tracked.

The JTAG stream PHY qualifies shared BSCAN capture/shift signals with the
USER-chain select signal, so CPU-debug scans do not enter JTAGBone or JTAG UART.

The helper constrains TCK and declares it asynchronous to the CPU's system
clock. It uses a kept alias of `ClockSignal(clock_domain)` and does not require
a particular target CRG hierarchy. It adds no synchronizers: these must
already be part of the CPU debug transport.

## Supported hardware

The helper uses `BSCANE2` or `BSCAN_SPARTAN6` according to the device. The
original [hardware validation](https://github.com/litex-hub/linux-on-litex-vexriscv/pull/458)
was on an Arty A7-35T using VexRiscv-SMP.
Other supported Xilinx device families still need their board-specific
OpenOCD TAP configuration and hardware qualification.

Zynq and Zynq UltraScale+ devices are currently rejected because their BSCAN
TDI has a one-cycle delay which this CPU transport connection does not
compensate for. Other FPGA vendors are not yet supported by this helper.

## OpenOCD and GDB on Arty

Use a RISC-V capable OpenOCD with `riscv use_bscan_tunnel` support and the
`riscv_jtag_tunneled.tcl` configuration from the
[LiteX JTAG debugging guide](https://github.com/enjoy-digital/litex/wiki/JTAG-GDB-Debugging-with-VexRiscv-SMP-NaxRiscv-VexiiRiscv-CPUs).
With that guide's `digilent_arty.cfg` and a one-hart CPU:

```sh
openocd -f digilent_arty.cfg -c 'set TAP_NAME xc7.tap' \
    -f riscv_jtag_tunneled.tcl
riscv64-unknown-elf-gdb build/digilent_arty/software/bios/bios.elf \
    -ex 'target extended-remote localhost:3333'
```

The tunnel configuration must select the FPGA TAP, enable
`riscv use_bscan_tunnel 6 1`, and match the built hart count (`RISCV_COUNT` in
the guide's script). USER4 is IR `0x23` on Arty's six-bit TAP. Other devices
can have different IR widths/encodings, and changing the USER chain requires
changing the OpenOCD tunnel IR as well (`riscv set_bscan_tunnel_ir` on versions
that provide it).

JTAGBone and OpenOCD can use the same cable in turn. Chain separation does
not make simultaneous access by two independent cable drivers safe; release
the cable before switching clients.
