# Getting Started with EmuLiteX

This guide is written for someone joining the project with no prior context. It covers every script in the repo, what each one actually does internally, and the exact commands to reproduce common workflows.

## What This Project Is

EmuLiteX wraps LiteX (an FPGA SoC builder) with setup and run scripts so you don't have to remember the underlying `litex_sim` / `litex_boards` commands by hand. There are four top-level scripts:

| Script | Purpose |
|---|---|
| `sim_setup.sh` | Install everything, then run a LiteX **simulation** (Verilator, no real board) |
| `fpga_setup.sh` | Install everything, then build a bitstream and flash it to a **real Digilent Arty board** |
| `vexriscv_smp_linux_sim_setup.sh` | Download Linux boot images and run a full **Linux boot in simulation** |
| `vexriscv_smp_linux_fpga_setup.sh` | Download Linux boot images and run a full **Linux boot on real hardware** |

The first two scripts (sim_setup.sh and fpga_setup.sh) handle all dependency installation and setup. If you plan to use the Linux scripts (vexriscv_smp_linux_sim_setup.sh or vexriscv_smp_linux_fpga_setup.sh) for the first time, you must run one of the first two scripts first to set up the shared venv/ environment. All scripts reuse this same Python virtual environment on subsequent runs.

---

## Prerequisites

- **Ubuntu/Debian only** — scripts check for `apt-get` and won't run on other distributions. May work on other Debian-based distros (Linux Mint, Pop!_OS) but only officially tested on Ubuntu/Debian.
- **Digilent Arty A7 board** (for FPGA scripts) — connect the single USB cable (provides both JTAG and UART interfaces).
- **Sufficient disk space** — a few GB minimum for LiteX, Verilator, CPU cores, and generated builds.
- **Internet connection** — required for downloading dependencies and Linux images.
- **15-30 minutes build time** — first run compiles Verilator/OpenOCD from source; FPGA Linux builds take extra time.

---

## 1. First Run — Simulation Only

```bash
mkdir Litex_Work
cd Litex_Work
git clone https://github.com/SilverLining-EDA/EmuLiteX.git
cd EmuLiteX
./sim_setup.sh
```

**What this actually does, in order:**
1. Installs system packages: Python, build tools, the RISC-V GCC toolchain, Verilator (built from source — the Ubuntu repo version is too old), GTKWave, and required libraries.
2. Creates a Python virtual environment at `venv/` and activates it.
3. Runs `litex_setup.py --init --install --config=standard` — this is what actually downloads LiteX itself and every CPU core repo (`pythondata-cpu-*`) into `Litex_Work/`, as siblings of `EmuLiteX/`.
4. Runs a VexRiscv simulation (`litex_sim --cpu-type=vexriscv`), inside a fresh, timestamped folder under `../sim_projects/`.

You'll see the BIOS boot in your terminal, ending in a `litex>`-style prompt — except by default it's the LiteX BIOS prompt, not a demo app. Press Ctrl+C to exit.

**Every later run reuses the same `venv/` and doesn't repeat the install steps** unless you pass `--update`.

---

## 2. Everyday Simulation Commands

Once the first run has completed, you almost never need the full install flow again — use `--sim-only` to skip straight to running:

```bash
./sim_setup.sh --sim-only
```

### Change the CPU

```bash
./sim_setup.sh --sim-only --cpu=cva6
./sim_setup.sh --sim-only --cpu=serv
./sim_setup.sh --sim-only --cpu=rocket --variant=full
```

`--variant` only matters for CPUs that define multiple variants (e.g. Rocket's `full`/`linux`/`medium`/`small`). Leave it out for CPUs like VexRiscv/CVA6 that use `standard`.

### Add SDRAM, Ethernet, or any other litex_sim flag

Anything `litex_sim --help` supports can be passed through `--extra-args`:

```bash
./sim_setup.sh --sim-only --extra-args="--with-sdram"
./sim_setup.sh --sim-only --extra-args="--with-sdram --with-etherbone"
```

### Build and boot the bare-metal demo app

```bash
./sim_setup.sh --sim-only --demo
./sim_setup.sh --sim-only --demo --cpu=cva6
```

**What `--demo` actually does**, step by step:
1. Builds a throwaway, header-only SoC (`--no-compile-gateware`) just to generate the software headers (`csr.h`, `mem.h`) the demo needs to compile against — no Verilator run happens for this step.
2. Compiles `litex_bare_metal_demo` (the source lives in `litex/soc/software/demo/`) against those generated headers, producing `demo.bin`.
3. Copies the generated `demo/` folder into this run's own project directory, and deletes it back out of `litex/soc/software/demo/` so the shared LiteX source tree stays clean between runs.
4. Runs the *real* simulation (gateware compiled this time), with `--ram-init=demo.bin` so the compiled demo is what boots automatically — you'll land at a `litex-demo-app>` prompt with `donut` and `helloc` commands.

**Known limitation:** Ibex does not support the CSR/Zicsr instructions the demo app needs, and will fail with an illegal-instruction trap. `--demo --cpu=ibex` is automatically detected and skipped, falling back to a normal (non-demo) run.

### Update everything

```bash
./sim_setup.sh --update
```

Re-runs `litex_setup.py --update --install`, pulling the latest LiteX/CPU-core code, then runs a plain sanity-check simulation.

---

## 3. Simulating a Full Linux Boot (VexRiscv-SMP)

This is a separate script because it needs extra assets (a pre-built Linux kernel image, device tree, root filesystem) that aren't part of LiteX itself.

```bash
./vexriscv_smp_linux_sim_setup.sh
```

**What it does:**
1. Downloads a pre-built Linux image bundle (kernel `Image`, `opensbi.bin`, `rv32.dtb`, `rootfs.cpio`) from the `linux-on-litex-vexriscv` project, if not already present in `../linux_images/vexriscv_smp/linux_image/`.
2. **Writes its own `boot_ram0.json`** manifest alongside the downloaded files — this is deliberate and important (see the warning below).
3. Copies the whole `linux_image/` folder into a fresh, timestamped project directory under `../sim_projects/`.
4. Runs `litex_sim --cpu-type=vexriscv_smp --cpu-variant=linux --with-sdram --sdram-module=MT48LC16M16 --sdram-init <path-to-boot_ram0.json>`.

**⚠️ Why this script writes `boot_ram0.json` itself, and why that matters:** the boot manifest's JSON key order determines the CPU's initial jump address — specifically, whichever key appears **last** in the file is what the BIOS jumps to after its serial-boot timeout. A manifest ending in `rootfs.cpio` (a filesystem archive, not code) causes the CPU to silently execute garbage forever with no error message — it looks identical to a hang. The `boot_ram0.json` this script generates deliberately ends with `opensbi.bin`, the real firmware entry point. **If you ever hand-edit or replace this file, keep `opensbi.bin` (or your correct entry point) as the last key.**

### Add tracing for waveform analysis

```bash
./vexriscv_smp_linux_sim_setup.sh --extra-args="--trace --trace-fst --sim-debug"
```

Produces `sim.fst`/`sim.gtkw` in the run's `build/sim/gateware/` folder, viewable with `gtkwave`.

### Be patient

A full Linux boot under cycle-accurate Verilator simulation is genuinely slow — tens of minutes to hours of wall-clock time depending on your machine, even though the simulated clock is only 1MHz. **Do not assume it has hung and Ctrl+C early** — checking for real kernel log lines (`[    0.000000] Linux version ...`) appearing in the terminal is the only reliable sign it's working; a lack of output for a long time is normal, not a fault.

---

## 4. Running on Real FPGA Hardware (Digilent Arty)

```bash
./fpga_setup.sh
```

**What it does, full flow:**
1. Installs FPGA-specific dependencies: OpenOCD (built from source at v0.12.0 — needed for JTAG programming), `picocom` (serial terminal), plus the same base toolchain as the sim script.
2. Sets up/reuses `venv/` and installs LiteX the same way as `sim_setup.sh`.
3. Builds a real bitstream via `litex_boards.targets.digilent_arty --build`, inside a fresh timestamped folder under `../fpga_projects/`.
4. Flashes it via OpenOCD (`--load`).
5. Opens a `picocom` serial terminal to watch the board boot.

**Exit `picocom` with Ctrl+A then Ctrl+X** — this is not the same key combination as the simulator.

### Change CPU or board settings

```bash
./fpga_setup.sh --cpu=cva6
./fpga_setup.sh --cpu=ibex
./fpga_setup.sh --board-variant=a7-35
./fpga_setup.sh --extra-args="--sys-clk-freq=100e6"
```

**Note on CVA6 specifically:** the script automatically adds `--sys-clk-freq=50e6` whenever `--cpu=cva6` is used and no clock frequency was explicitly given, because CVA6 fails timing (reported as WNS −25ns) at the board's default 100MHz. You don't need to add this yourself — it's handled for you — but if you explicitly pass a different `--sys-clk-freq`, that overrides this default.

### Skip the full install (fast path once already set up)

```bash
./fpga_setup.sh --fpga-only --extra-args="--sys-clk-freq=100e6"
```

Skips the dependency/venv/litex_setup steps entirely — goes straight to build → flash → terminal.

### Flash an already-built bitstream without rebuilding

```bash
./fpga_setup.sh --flash-only --cpu=cva6
```

Searches `../fpga_projects/` for the most recently built bitstream matching that CPU, flashes it, and opens the terminal — no rebuild.

### Custom serial port or baud rate

```bash
./fpga_setup.sh --flash-only --cpu=vexriscv --port=/dev/ttyUSB0 --baudrate=921600
```

Defaults are `/dev/ttyUSB1` and `115200`. If the port isn't found, the script lists whatever `/dev/ttyUSB*` devices actually exist so you can correct it.

### Demo app on real hardware

```bash
./fpga_setup.sh --demo
./fpga_setup.sh --flash-only --cpu=vexriscv --demo
```

Same demo-build mechanism as the simulator, but built against the FPGA build's generated headers (`build/<board>/`) instead of a sim build, and loaded over serial via `litex_term --kernel=demo.bin` instead of embedded at boot — this is because on real hardware, the bitstream (and its embedded BIOS) is already flashed; the demo is uploaded afterward, live, over the same UART you're using for the terminal. Same Ibex limitation applies (CSR/Zicsr unsupported → demo build is skipped automatically).

---

## 5. Running Linux on Real FPGA Hardware

```bash
./vexriscv_smp_linux_fpga_setup.sh
```

Same Linux-image download/manifest logic as the simulation version (§3), but building a real bitstream (`--build --load`) and then loading the Linux images live over serial with `litex_term --images boot.json` (note: this script's live-load path uses `boot.json`, not `boot_ram0.json` — the two manifests order their keys for the two different boot mechanisms, and this is correct as written for the FPGA flow).

**A full build here takes 15–30 minutes** — this is real Vivado/toolchain synthesis, not simulation. The script warns about this before starting.

### Re-flash without rebuilding

```bash
./vexriscv_smp_linux_fpga_setup.sh --flash-only
```

---

## 6. Where Things End Up

| What | Where |
|---|---|
| Simulation runs | `../sim_projects/<cpu>_<timestamp>/` |
| Linux simulation runs | `../sim_projects/linux_vexriscv_smp_<timestamp>/` |
| FPGA bitstreams | `../fpga_projects/<board>_<cpu>_<timestamp>/` |
| Linux FPGA bitstreams | `../fpga_projects/linux_vexriscv_smp_<timestamp>/` |
| Demo binary (any flow) | `<project_dir>/demo/demo.bin` |
| Waveforms (`--trace`) | `<project_dir>/build/sim/gateware/sim.vcd` (or `.fst`) |
| Downloaded Linux images (shared, reused across runs) | `../linux_images/vexriscv_smp/linux_image/` |

Every run gets its own timestamped folder — nothing is overwritten between runs, but disk usage grows over time; periodically clean out old folders under `sim_projects/`/`fpga_projects/` if space becomes an issue.

---

## All Options Reference

### `sim_setup.sh`

| Flag | Description |
|---|---|
| `--config=<name>` | Install config: `minimal`, `standard`, `full` (default: `standard`) |
| `--cpu=<name>` | CPU type (default: `vexriscv`) |
| `--variant=<name>` | CPU variant, e.g. for Rocket (default: `standard`) |
| `--extra-args="..."` | Extra flags passed straight through to `litex_sim` |
| `--demo` | Build and boot the bare-metal demo app instead of the plain BIOS |
| `--sim-only` | Skip install steps, only run simulation |
| `--update` | Force-update all repositories and reinstall |
| `--help`, `-h` | Show help |

### `fpga_setup.sh`

| Flag | Description |
|---|---|
| `--board=<name>` | FPGA board (default: `digilent_arty`) |
| `--board-variant=<name>` | Board variant: `a7-100`, `a7-35`, `s7-50` (default: `a7-100`) |
| `--cpu=<name>` | CPU type (default: `vexriscv`) |
| `--cpu-variant=<name>` | CPU variant (default: `standard`) |
| `--port=<dev>` | Serial device (default: `/dev/ttyUSB1`) |
| `--baudrate=<n>` | Baud rate (default: `115200`) |
| `--fpga-only` | Skip dependency checks — build, flash, open terminal |
| `--flash-only` | Skip build — flash the most recent matching bitstream, open terminal |
| `--demo` | Build the bare-metal demo and load it over serial |
| `--extra-args="..."` | Extra flags passed to the board build command |
| `--help`, `-h` | Show help |

### `vexriscv_smp_linux_sim_setup.sh`

| Flag | Description |
|---|---|
| `--extra-args="..."` | Extra flags passed to `litex_sim` (e.g. `--trace`) |
| `--help`, `-h` | Show help |

### `vexriscv_smp_linux_fpga_setup.sh`

| Flag | Description |
|---|---|
| `--board=<name>` | FPGA board (default: `digilent_arty`) |
| `--board-variant=<name>` | Board variant (default: `a7-100`) |
| `--flash-only` | Skip build — flash the most recent Linux bitstream, load Linux |
| `--extra-args="..."` | Extra flags passed to the board build command |
| `--help`, `-h` | Show help |

For the full, authoritative list of everything `litex_sim` itself supports (bus width, CSR layout, BIOS options, Verilator tracing flags, etc.), run:

```bash
source venv/bin/activate
litex_sim --help
```

## 7. Debugging FPGA Projects with GDB

The `debug.sh` script provides a simple menu-driven interface for debugging running FPGA projects with GDB and OpenOCD.

### Prerequisite — Build and Flash With Debug Features Enabled

**Terminal 1:**

```bash
./fpga_setup.sh --cpu=vexriscv_smp --build --load --demo --extra-args="--with-privileged-debug --hardware-breakpoints=4"
```

When flashing completes, the project folder is printed — this path is needed for `debug.sh`:

```
✓ FPGA loaded successfully
📁 Project Folder:
/home/ravi-server/work/Litex_work/fpga_projects/digilent_arty_vexriscv_smp_*
```


Leave this terminal running — it doubles as the serial/UART output. If it gets closed, `debug.sh` can reopen it (see the full example below).

---

### The Debug Menu

**Running `./debug.sh` with no arguments auto-detects the latest project and shows:**
-------------------------------------
```
FPGA Debug Menu
📁 Project: /home/ravi-server/work/Litex_work/fpga_projects/digilent_arty_vexriscv_smp_*
📦 Demo: Available
Start OpenOCD
GDB - Demo
GDB - BIOS
Load Demo (litex_term --kernel)
Open Serial Terminal (BIOS only)
Exit
Choice [1-6]:
```

| Option | What it does |
|---|---|
| **1) Start OpenOCD** | Starts the JTAG server, waits for GDB on port `3333` |
| **2) GDB - Demo** | Attaches GDB with `demo/demo.elf` symbols |
| **3) GDB - BIOS** | Attaches GDB with `bios.elf` symbols |
| **4) Load Demo** | Uploads and boots `demo.bin` over serial via `litex_term --kernel` — this is what actually gets the demo app running on the board so there's something for GDB to attach to |
| **5) Open Serial Terminal** | Plain `litex_term` session showing BIOS/UART output, no kernel upload |
| **6) Exit** | Quit the menu |

---

### Common GDB Commands

| Command | Description |
|---|---|
| `break <function>` | Set breakpoint at function (e.g., `break main`) |
| `break *<address>` | Set breakpoint at address (e.g., `break *0x4000064c`) |
| `hbreak <function>` | Set a **hardware** breakpoint |
| `info breakpoints` | List all breakpoints |
| `continue` or `c` | Run until breakpoint |
| `step` or `s` | Step one C line (enters functions) |
| `next` or `n` | Step one C line (skips functions) |
| `stepi` | Step one assembly instruction |
| `info registers` | Show CPU registers |
| `info locals` | Show local variables |
| `print <var>` | Print variable value |
| `x/<n>x <addr>` | Examine memory (e.g., `x/10x 0x40000000`) |
| `disassemble` | Show assembly code |
| `where` or `bt` | Show stack backtrace |
| `quit` or `q` | Exit GDB |

**Note on breakpoints:** always use `hbreak`, never plain `break`, when debugging the BIOS (option 3). The BIOS executes from ROM, and a software `break` works by writing a trap instruction directly into memory at that address — which doesn't work when the target address is read-only. `hbreak` uses the debug module's hardware trigger unit instead, so it works correctly regardless of whether the target is ROM or RAM.

**Do not use `stepi` / `step` / `continue` when debugging the BIOS.** Because BIOS code lives in ROM, single-stepping and resuming through it can behave unreliably, unlike RAM-resident code (e.g. the demo app) where stepping is fully supported. To inspect BIOS behavior, set an `hbreak` at the point of interest and use `info registers` / `info locals` / `print` / `x` once halted there, rather than stepping through it instruction-by-instruction.

---

### Full Worked Example — Breaking Into a Running Donut Demo

This walks through the complete three-terminal flow: loading the demo, attaching GDB, setting a breakpoint, starting the animation, breaking into it with Ctrl+C, inspecting state, and resuming — repeatable as many times as needed.

**Order matters here:** connecting OpenOCD/GDB and issuing `continue` can halt/reset the target, so the `donut` command should only be started *after* GDB is attached and has already issued `continue` — starting it earlier means GDB attaching will interrupt it, requiring a retype anyway.

**Terminal 1 — Load the demo (if `litex-demo-app>` terminal closed otherwise use that)**

```bash
./debug.sh
```
========================================

```
FPGA Debug Menu
📁 Project: /home/ravi-server/work/Litex_work/fpga_projects/digilent_arty_vexriscv_smp_*
📦 Demo: Available
Start OpenOCD
GDB - Demo
GDB - BIOS
Load Demo (litex_term --kernel)
Open Serial Terminal (BIOS only)
Exit
Choice [1-6]:4
``` 
```
Loading Demo...
Demo: /home/.../digilent_arty_vexriscv_smp_*/demo/demo.bin
Press Ctrl+A then Ctrl+X to exit
(BIOS banner, SDRAM init, memtest, etc.)
--============== Liftoff! ==============--
LiteX minimal demo app built
Available commands:
help - Show this command
reboot - Reboot CPU
led - Led demo
donut - Spinning Donut demo
helloc - Hello C
litex-demo-app>
```

**Terminal 2 — OpenOCD**

```bash
./debug.sh
```

Select **1**:
```
Choice [1-6]: 1
Starting OpenOCD...
Command: openocd -d2 -f ../litex-boards/litex_boards/prog/
openocd_xc7_ft2232.cfg -f riscv_jtag_tunneled.cfg
Info : Listening on port 3333 for gdb connections
```
Leave this running — it's the JTAG server for the whole session.

**Terminal 3 — GDB**

```bash
./debug.sh
```
Select **2** (Demo):
```
Choice [1-6]: 2
```
```
Debugging Demo...
Command: gdb-multiarch -q demo/demo.elf -ex "target extended-remote localhost:3333"
Reading symbols from demo/demo.elf...
Remote debugging using localhost:3333
0x00000000 in ?? ()
(gdb)
```
Set a breakpoint in the donut renderer and continue:
```
(gdb) break donut
Breakpoint 1 at 0x400002a0: file donut.c, line 26.
(gdb) c
Continuing.
Disabling abstract command writes to CSRs.
```
**Now — back in Terminal 1 — start the animation:**
```
litex-demo-app> donut
```

The animation starts spinning continuously.

**Back in Terminal 3 (GDB), Ctrl+C pauses it at any time:**
```
(gdb)
^C
Program received signal SIGINT, Interrupt.
uart_write (c=32 ' ', c@entry=10 '\n') at /home/ravi-server/work/Litex_work/litex/litex/soc/software/libbase/uart.c:99
99 while(tx_produce_next == tx_consume);
(gdb)
```

The animation freezes instantly in Terminal 1 the moment Ctrl+C is pressed. From here, state can be inspected as usual:
```
(gdb) info registers
(gdb) bt
(gdb) print some_variable
```

To resume the spinning donut, `continue`:
```
(gdb) c
Continuing.
```

**Ctrl+C → inspect → `c` can be repeated as many times as needed, at any point** — a handy way to sample CPU state mid-animation without needing to hit a specific breakpoint each time.


### Using Custom Project Paths

```bash
# Use a specific project
./debug.sh ../fpga_projects/digilent_arty_vexriscv_smp_30-07-12-23

# Use the default project (auto-detects latest)
./debug.sh

# Prefer project with demo folder
./debug.sh --demo

# Use any path (relative or absolute)
./debug.sh /full/path/to/project
```