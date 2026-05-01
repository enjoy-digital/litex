#!/usr/bin/env python3

# Git repositories ---------------------------------------------------------------------------------

# Get SHA1: git rev-parse --short=7 HEAD

class GitRepo:
    def __init__(self, url, clone="regular", develop=True, editable=True, sha1=None, branch="master",
        tag=None):
        assert clone in ["regular", "recursive"]
        self.url      = url
        self.clone    = clone
        self.develop  = develop
        self.editable = editable
        self.sha1     = sha1
        self.branch   = branch
        self.tag      = tag


git_repos = {
    # HDL.
    # ----
    "migen": GitRepo(
        url      = "https://git.m-labs.hk/M-Labs/",
        clone    = "recursive",
        editable = False,
        sha1     = 0x4c2ae8dfeea37f235b52acb8166f12acaaae4f7c,
    ),

    # LiteX SoC builder.
    # ------------------
    "pythondata-software-picolibc":    GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-software-compiler_rt": GitRepo(url="https://github.com/litex-hub/"),
    "litex":                           GitRepo(url="https://github.com/enjoy-digital/", tag=True),

    # LiteX Cores Ecosystem.
    # ----------------------
    "liteiclink":   GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "liteeth":      GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litedram":     GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litepcie":     GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litesata":     GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litesdcard":   GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litescope":    GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litejesd204b": GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litespi":      GitRepo(url="https://github.com/litex-hub/",     tag=True),
    "litei2c":      GitRepo(url="https://github.com/litex-hub/",     tag=True, branch="main"),

    # LiteX Boards.
    # -------------
    "litex-boards": GitRepo(url="https://github.com/litex-hub/", clone="regular", tag=True),

    # LiteX pythondata.
    # -----------------
    # Generic.
    "pythondata-misc-tapcfg":      GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-misc-usb_ohci":    GitRepo(url="https://github.com/litex-hub/", clone="recursive"),

    # LM32 CPU(s).
    "pythondata-cpu-lm32":         GitRepo(url="https://github.com/litex-hub/"),

    # OpenRISC CPU(s).
    "pythondata-cpu-mor1kx":       GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-marocchino":   GitRepo(url="https://github.com/litex-hub/"),

    # OpenPower CPU(s).
    "pythondata-cpu-microwatt":    GitRepo(url="https://github.com/litex-hub/", sha1=0xc69953aff92),

    # RISC-V CPU(s).
    "pythondata-cpu-blackparrot":  GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-coreblocks":   GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-cv32e40p":     GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-cv32e41p":     GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-cva5":         GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-cva6":         GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-ibex":         GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-minerva":      GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-naxriscv":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-openc906":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-picorv32":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-rocket":       GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-sentinel":     GitRepo(url="https://github.com/litex-hub/", branch="main"),
    "pythondata-cpu-serv":         GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-vexiiriscv":   GitRepo(url="https://github.com/litex-hub/", branch="main"),
    "pythondata-cpu-vexriscv":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-vexriscv-smp": GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
}

# Installs -----------------------------------------------------------------------------------------

# Minimal: Only Migen + LiteX.
minimal_repos = ["migen", "litex"]

# Standard: Migen + LiteX + Cores + Software + Popular CPUs (LM32, Mor1kx, SERV, VexRiscv).
standard_repos = list(git_repos.keys())
standard_repos.remove("pythondata-cpu-blackparrot")
standard_repos.remove("pythondata-cpu-coreblocks")
standard_repos.remove("pythondata-cpu-cv32e40p")
standard_repos.remove("pythondata-cpu-cv32e41p")
standard_repos.remove("pythondata-cpu-cva5")
standard_repos.remove("pythondata-cpu-cva6")
standard_repos.remove("pythondata-cpu-ibex")
standard_repos.remove("pythondata-cpu-openc906")
standard_repos.remove("pythondata-cpu-marocchino")
standard_repos.remove("pythondata-cpu-microwatt")
standard_repos.remove("pythondata-cpu-picorv32")
standard_repos.remove("pythondata-cpu-rocket")

# Full: Migen + LiteX + Cores + Software + All CPUs.
full_repos = list(git_repos.keys())

# Installs:
install_configs = {
    "minimal"  : minimal_repos,
    "standard" : standard_repos,
    "full"     : full_repos,
}
