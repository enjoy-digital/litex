A starting point for the `doc/debugging-guide.md` of a board or product repository: the build
and load commands, the way in, the registers and probes that already exist, and the failures
already understood, in one page. Copy the block below, fill it as you debug, and the next person
(or agent) starts from your findings instead of rediscovering them.

## Use it

```sh
mkdir -p doc && $EDITOR doc/debugging-guide.md     # paste the template, replace the <...> fields
```

Mention it from the repository's `README.md` and `AGENTS.md` ("debugging: doc/debugging-guide.md"),
so that an agent reads it before touching the hardware. Keep it short and current: a section with
nothing to say yet is deleted, not left empty.

## The template

~~~markdown
# <Project> debugging guide

<What the design is, which board(s), which LiteX/core versions it was last checked with.>

## Build and load

```sh
python3 -m <target> <options> --build --output-dir=build/<name>    # toolchain <name and version>
python3 -m <target> <options> --load  --output-dir=build/<name>    # volatile; flash only when asked
```

Expected timing: <clock>: WNS <value> ns (<toolchain>). Known critical paths: <...>.

## Connect

```sh
litex_server <--uart --uart-port=... | --jtag | --udp --udp-ip=... | --pcie> --bind-port=<port>
litex_cli --csr-csv=build/<name>/csr.csv --port=<port> --ident --json
litex_mcp --csr-csv=build/<name>/csr.csv --port=<port>               # same link, for agents
```

Expected identifier: `<ident string>`. Adapters on this setup: <which port is which>.

## Known-good state

| Register | Expected | Meaning |
| --- | --- | --- |
| `ctrl_scratch` | `0x12345678` | the bus and the CSR map work |
| `<core>_<status>` | `<value>` | <what it says when the design is healthy> |

## Instrumentation

| Register / probe | How to enable | Answers |
| --- | --- | --- |
| `<core>_<counter>` | always built | <how often X happens> |
| LiteScope `<group>` | `--with-<feature>-probe` | <which handshake or sequence> |

Scripts: `<path/to/script.py>`: <what it prints>.

## Simulation and tests

```sh
python3 -m pytest test/                       # <what is covered>
<simulation command>                          # <what it exercises>
```

## Known failures

| Symptom | Cause | Check |
| --- | --- | --- |
| <what you observe> | <root cause found> | <register, capture or command that proves it> |

## Log

- <YYYY-MM-DD>: <finding, with the build, the transport and the evidence>.
~~~

## Fill it in

- **Build and load**: the exact commands that produced the bitstream on the bench, with the
  toolchain version; the timing summary comes from the build report (`litex_build_report` or
  `litex.build.report`).
- **Connect**: what `--ident` must print, so that a server answering on the wrong port is
  spotted at once.
- **Known-good state** and **Instrumentation**: the registers and probes of the
  [debug method](Debug-A-SoC-On-Hardware.md#registers-before-traces), kept in the tree, with the
  switch that enables each.
- **Known failures**: one row per bug understood, with the evidence; the same symptom usually
  comes back.
- **Log**: dated, newest last; move a finding up into a table once it is confirmed.

## Next

- [Debug a SoC on hardware](Debug-A-SoC-On-Hardware.md): the method this guide records the results of.
- [Look inside with LiteScope](Use-LiteScope-To-Debug-A-SoC.md): adding the probes listed in the guide.
- [LiteX for AI agents](LiteX-for-AI-Agents.md#drive-a-soc-through-mcp): the same loop through `litex_mcp`.
