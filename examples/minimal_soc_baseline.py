#!/usr/bin/env python3

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from migen import ClockDomain

from litex.build.generic_platform import GenericPlatform, Pins
from litex.build.generic_toolchain import GenericToolchain
from litex.gen import LiteXModule
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc import SoCMini


class ExportOnlyToolchain(GenericToolchain):
    """Generate Verilog without invoking an external FPGA toolchain."""

    def build_io_constraints(self):
        return "", ""

    def build_script(self):
        return None


class BaselinePlatform(GenericPlatform):
    def __init__(self):
        GenericPlatform.__init__(
            self,
            device="baseline",
            io=[("sys_clk", 0, Pins("X"))],
            name="minimal_soc",
        )
        self.toolchain = ExportOnlyToolchain()

    def build(self, fragment, **kwargs):
        return self.toolchain.build(self, fragment, **kwargs)


class CRG(LiteXModule):
    def __init__(self, sys_clk):
        self.cd_sys = ClockDomain("sys")
        self.comb += self.cd_sys.clk.eq(sys_clk)


class MinimalSoC(SoCMini):
    def __init__(self, sys_clk_freq):
        platform = BaselinePlatform()
        SoCMini.__init__(
            self,
            platform=platform,
            clk_freq=sys_clk_freq,
            ident="LiteX HarmonyOS PC baseline",
            ident_version=False,
            with_ctrl=True,
            with_timer=True,
        )
        self.crg = CRG(platform.request("sys_clk"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_clean(output_dir):
    resolved = output_dir.absolute()
    forbidden = {
        Path.cwd().absolute(),
        Path.home().absolute(),
        Path(resolved.anchor),
    }
    if resolved in forbidden:
        raise ValueError(f"Refusing to clean unsafe output directory: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a toolchain-independent LiteX SoC baseline."
    )
    parser.add_argument(
        "--output-dir",
        default="build/minimal-soc",
        help="Directory for generated HDL, CSR maps, headers, and summary.",
    )
    parser.add_argument(
        "--sys-clk-freq",
        default=1_000_000,
        type=int,
        help="System clock frequency used in generated constants.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove the selected output directory before generation.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    if args.sys_clk_freq <= 0:
        raise ValueError("--sys-clk-freq must be positive")
    if args.clean:
        safe_clean(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    soc = MinimalSoC(sys_clk_freq=args.sys_clk_freq)
    builder = Builder(
        soc,
        output_dir=str(output_dir),
        csr_csv=str(output_dir / "csr.csv"),
        csr_json=str(output_dir / "csr.json"),
        compile_software=False,
        compile_gateware=False,
    )
    builder.build(run=False, build_name="minimal_soc")

    required = [
        output_dir / "gateware" / "minimal_soc.v",
        output_dir / "csr.csv",
        output_dir / "csr.json",
        output_dir / "software" / "include" / "generated" / "csr.h",
        output_dir / "software" / "include" / "generated" / "soc.h",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Missing expected build outputs: " + ", ".join(missing))

    artifacts = []
    for path in sorted(p for p in output_dir.rglob("*") if p.is_file()):
        if path.name == "baseline-summary.json":
            continue
        artifacts.append({
            "path": path.relative_to(output_dir).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })

    summary = {
        "build_name": "minimal_soc",
        "sys_clk_freq": args.sys_clk_freq,
        "output_dir": str(output_dir),
        "artifacts": artifacts,
    }
    summary_path = output_dir / "baseline-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Generated {len(artifacts)} artifacts in {output_dir}")
    for artifact in artifacts:
        print(f"  {artifact['path']} ({artifact['bytes']} bytes)")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
