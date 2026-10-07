#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# LiteX @ HarmonyOS PC 移植项目 —— 环境检测脚本（2 号交付物）
#
# 纯 Python 标准库实现，单文件、可直接拷贝到目标机运行，不依赖 LiteX 本身。
# 输出系统 / 架构 / 终端 / Python / pip / Git / 编码 / 路径 / 文件系统能力 /
# 子进程 / 编译器与外部工具 的完整探测报告，用于：
#   1) 鸿蒙 PC 真机环境确认（分工文档 2 号第一周任务）；
#   2) 参考环境与鸿蒙环境结果对比（4 号测试基线输入）；
#   3) 阻塞报告的证据材料（分工文档第六节同步要求）。
#
# 用法：
#   python3 scripts/check_environment.py                     # 快速检测（静态信息 + 本地能力探测）
#   python3 scripts/check_environment.py --full              # 全量检测（+ 网络 / Git 远端 / venv 创建 / 工具版本）
#   python3 scripts/check_environment.py --json report.json  # 同时输出机器可读 JSON
#
# 退出码：
#   0 = 未发现 FAIL 项
#   1 = 存在 FAIL 项（核心必达能力受阻，应按《鸿蒙 PC 环境搭建说明》提交阻塞报告）
#
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import json
import locale
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import urllib.request

# 与上游 setup.py 的 python_requires = "~=3.7" 保持一致。
REQUIRED_PYTHON = (3, 7)

# 网络探测端点：severity 为 required 的端点不通即影响核心安装流程。
NET_ENDPOINTS = [
    ("pypi.org (pip 索引)",            "https://pypi.org/simple/",                        "required"),
    ("files.pythonhosted.org (wheel)", "https://files.pythonhosted.org/",                 "required"),
    ("git.m-labs.hk (Migen 源仓库)",   "https://git.m-labs.hk/",                          "required"),
    ("github.com (LiteX 仓库)",        "https://github.com/",                             "optional"),
    ("raw.githubusercontent.com",      "https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_repos.py", "optional"),
]

# 外部工具探测表：(分类, 可执行文件名, 版本参数, 缺失影响说明)。
TOOLS = [
    ("C/C++ 编译器",           "cc",                    ["--version"], "构建依赖无预编译 wheel 时需要"),
    ("C/C++ 编译器",           "gcc",                   ["--version"], "构建依赖无预编译 wheel 时需要"),
    ("C/C++ 编译器",           "clang",                 ["--version"], "构建依赖无预编译 wheel 时需要"),
    ("构建系统",               "make",                  ["--version"], "扩展验收（litex_sim / 固件）"),
    ("构建系统",               "ninja",                 ["--version"], "扩展验收（litex_sim / 固件）"),
    ("构建系统",               "meson",                 ["--version"], "扩展验收（litex_sim / 固件）"),
    ("构建系统",               "cmake",                 ["--version"], "扩展验收（可选）"),
    ("仿真 / HDL 工具",        "verilator",             ["--version"], "扩展验收（litex_sim）"),
    ("仿真 / HDL 工具",        "iverilog",              ["-V"],        "扩展验收（可选仿真）"),
    ("仿真 / HDL 工具",        "yosys",                 ["--version"], "扩展验收（FPGA 综合，非首期）"),
    ("RISC-V 交叉工具链",      "riscv64-unknown-elf-gcc", ["--version"], "扩展验收（BIOS/固件编译）"),
    ("RISC-V 交叉工具链",      "riscv64-elf-gcc",       ["--version"], "扩展验收（BIOS/固件编译）"),
    ("RISC-V 交叉工具链",      "riscv32-unknown-elf-gcc", ["--version"], "扩展验收（BIOS/固件编译）"),
]

# Python 依赖探测表：(import 名, pip 包名, 用途说明, 是否核心必达)。
PY_DEPS = [
    ("migen",     "migen",      "HDL 生成引擎（litex/gen 全面依赖）",                  True),
    ("packaging", "packaging",  "builder.py 版本比较（litex/soc/integration/builder.py:22）", True),
    ("serial",    "pyserial",   "litex_term / UART 远程（litex/tools/litex_term.py:16）", True),
    ("requests",  "requests",   "远程烧写懒加载（litex/build/generic_programmer.py:52）", True),
    ("setuptools", "setuptools", "安装/构建（litex_setup.py:628）",                     False),
    ("wheel",     "wheel",      "安装/构建（litex_setup.py:630）",                       False),
    ("pexpect",   "pexpect",    "交互式终端自动化（extras: develop）",                   False),
    ("meson",     "meson",      "litex_sim C 仿真构建（扩展验收）",                      False),
]

# POSIX 专属模块探测：影响 litex_term / litex_server 等工具（扩展验收）。
POSIX_MODULES = ["termios", "pty", "select", "fcntl", "signal"]

CORE = "bright"

def tag(status):
    return "[{:<4}]".format(status)

class Report(object):
    def __init__(self, full):
        self.entries  = []
        self.full     = full
        self.started  = time.time()

    def add(self, section, name, status, detail="", required=False):
        self.entries.append({
            "section":  section,
            "name":     name,
            "status":   status,   # OK / WARN / FAIL / SKIP / INFO
            "detail":   str(detail),
            "required": bool(required),
        })

    def sections(self):
        order, seen = [], set()
        for e in self.entries:
            if e["section"] not in seen:
                seen.add(e["section"])
                order.append(e["section"])
        return [(s, [e for e in self.entries if e["section"] == s]) for s in order]

    def blockers(self):
        return [e for e in self.entries if e["status"] == "FAIL"]

    def to_json(self):
        return {
            "tool":        "litex-harmonyos-check_environment",
            "generated":   time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode":        "full" if self.full else "fast",
            "elapsed_s":   round(time.time() - self.started, 2),
            "entries":     self.entries,
            "blockers":    ["/".join([e["section"], e["name"]]) for e in self.blockers()],
        }

def run_cmd(cmd, timeout=15, cwd=None, env=None):
    """执行外部命令，返回 (returncode, 合并输出文本)。returncode 为 None 表示启动失败/超时。"""
    try:
        r = subprocess.run(
            cmd, cwd=cwd, env=env, timeout=timeout,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return r.returncode, r.stdout.decode("utf-8", errors="replace").strip()
    except FileNotFoundError:
        return None, "可执行文件未找到: {}".format(cmd[0])
    except subprocess.TimeoutExpired:
        return None, "超时 ({}s): {}".format(timeout, " ".join(cmd))
    except Exception as e:
        return None, "执行异常: {}".format(e)

# 系统 ---------------------------------------------------------------------------------------------

def probe_system(rep):
    s = "系统"
    rep.add(s, "platform.system",    "INFO", platform.system())
    rep.add(s, "platform.release",   "INFO", platform.release())
    rep.add(s, "platform.version",   "INFO", platform.version())
    rep.add(s, "platform.machine",   "INFO", platform.machine())
    rep.add(s, "platform.processor", "INFO", platform.processor() or "N/A")
    rep.add(s, "sys.platform",       "INFO", sys.platform)
    tokens = ("openharmony", "harmonyos", "hongmeng", "ohos")
    os_release_txt = ""
    if os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release", "r", encoding="utf-8", errors="replace") as f:
                os_release_txt = f.read()
            rep.add(s, "/etc/os-release", "INFO", os_release_txt.replace("\n", " | ").strip())
        except OSError as e:
            rep.add(s, "/etc/os-release", "INFO", "读取失败: {}".format(e))
    else:
        rep.add(s, "/etc/os-release", "INFO", "不存在（非标准 Linux/OpenHarmony 布局）")
    if os.path.exists("/proc/version"):
        try:
            with open("/proc/version", "r", encoding="utf-8", errors="replace") as f:
                rep.add(s, "/proc/version", "INFO", f.read().strip())
        except OSError:
            pass
    hay = (os_release_txt + " " + platform.system() + " " + platform.release()).lower()
    hit = [t for t in tokens if t in hay]
    if hit:
        rep.add(s, "鸿蒙特征识别", "OK", "命中关键字: {}".format(", ".join(hit)))
    elif os.name == "posix":
        rep.add(s, "鸿蒙特征识别", "WARN",
                "未命中 OpenHarmony/HarmonyOS 关键字；若当前确为鸿蒙 PC，"
                "请将上方原始值发回群里确认检测规则（勿改用虚拟机/容器验证）")
    else:
        rep.add(s, "鸿蒙特征识别", "INFO", "当前为非 POSIX 平台（参考环境预期结果）")
    rep.add(s, "SHELL 环境变量",   "INFO", os.environ.get("SHELL", "未设置"))
    rep.add(s, "TERM 环境变量",    "INFO", os.environ.get("TERM", "未设置"))
    rep.add(s, "TERM_PROGRAM",     "INFO", os.environ.get("TERM_PROGRAM", "未设置"))
    rep.add(s, "终端 isatty(stdin/stdout)", "INFO",
            "stdin={} stdout={}".format(
                sys.stdin.isatty()  if hasattr(sys.stdin,  "isatty") else False,
                sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False))
    try:
        ts = os.get_terminal_size()
        rep.add(s, "终端尺寸", "INFO", "{}x{}".format(ts.columns, ts.lines))
    except OSError:
        rep.add(s, "终端尺寸", "INFO", "无法获取（非交互终端）")

# Python / pip / venv --------------------------------------------------------------------------------

def probe_python(rep):
    s = "Python"
    vi = sys.version_info
    status = "OK" if (vi.major, vi.minor) >= REQUIRED_PYTHON else "FAIL"
    rep.add(s, "解释器版本 (需 >=3.7)", status,
            "{} ({})".format(platform.python_version(), platform.python_implementation()),
            required=True)
    rep.add(s, "sys.executable",  "INFO", sys.executable or "N/A")
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    rep.add(s, "是否虚拟环境",     "INFO", "是 ({})".format(sys.prefix) if in_venv else "否（系统环境）")
    marker = os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED")
    if os.path.exists(marker):
        rep.add(s, "PEP 668 外部管理标记", "WARN",
                "存在 {}：系统 pip 受保护，必须使用 venv（litex_setup.py 会直接拒绝安装）".format(marker))
    else:
        rep.add(s, "PEP 668 外部管理标记", "INFO", "无（可直接 pip，仍建议使用 venv）")
    rc, out = run_cmd([sys.executable, "-m", "pip", "--version"], timeout=30)
    if rc == 0 and out:
        rep.add(s, "pip 可用性", "OK", out, required=True)
    else:
        rep.add(s, "pip 可用性", "FAIL", "python -m pip --version 失败: {}".format(out), required=True)
    try:
        import venv  # noqa: F401
        rep.add(s, "venv 模块可导入", "OK", "已内置")
    except ImportError as e:
        rep.add(s, "venv 模块可导入", "FAIL", str(e))
    rep.add(s, "site-packages 路径", "INFO", sysconfig.get_path("purelib"))
    rep.add(s, "可执行脚本目录",     "INFO", sysconfig.get_path("scripts"))

def probe_venv_creation(rep):
    """--full 模式：真实创建一个 venv 并运行其中的解释器与 pip。"""
    s = "venv 实测"
    d = tempfile.mkdtemp(prefix="litex-env-check-")
    venv_dir = os.path.join(d, "venvtest")
    try:
        t0 = time.time()
        rc, out = run_cmd([sys.executable, "-m", "venv", venv_dir], timeout=180)
        if rc != 0:
            rep.add(s, "python -m venv 创建", "FAIL",
                    "退出码 {}，输出: {}".format(rc, out[-2000:]))
            return
        rep.add(s, "python -m venv 创建", "OK", "耗时 {:.1f}s".format(time.time() - t0))
        vpy = (os.path.join(venv_dir, "bin", "python") if os.name != "nt"
               else os.path.join(venv_dir, "Scripts", "python.exe"))
        if not os.path.exists(vpy):
            rep.add(s, "venv 内解释器", "FAIL", "未找到 {}".format(vpy))
            return
        rc, out = run_cmd([vpy, "-c", "import sys; print(sys.version)"], timeout=30)
        rep.add(s, "venv 内解释器", "OK" if rc == 0 else "FAIL", out or "退出码 {}".format(rc))
        rc, out = run_cmd([vpy, "-m", "pip", "--version"], timeout=60)
        rep.add(s, "venv 内 pip (ensurepip)", "OK" if rc == 0 else "FAIL", out or "退出码 {}".format(rc))
    finally:
        shutil.rmtree(d, ignore_errors=True)

# 编码 -----------------------------------------------------------------------------------------------

def probe_encoding(rep):
    s = "编码与字符集"
    rep.add(s, "文件系统编码", "INFO", sys.getfilesystemencoding())
    rep.add(s, "区域首选编码", "INFO", locale.getpreferredencoding(False))
    rep.add(s, "stdout 编码",  "INFO", getattr(sys.stdout, "encoding", "N/A"))
    probe_str = "鸿蒙 LiteX 移植环境检测 — 中文与→特殊符号←"
    try:
        probe_str.encode(getattr(sys.stdout, "encoding", None) or "ascii")
        rep.add(s, "控制台中文输出", "OK", "stdout 编码可表示中文与全角符号（未直接打印，避免污染报告）")
    except UnicodeEncodeError as e:
        rep.add(s, "控制台中文输出", "WARN", "UnicodeEncodeError: {}（LiteX 日志含中文时可能乱码）".format(e))
    try:
        d = tempfile.mkdtemp(prefix="litex-enc-")
        p = os.path.join(d, "中文测试文件.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("ok")
        with open(p, "r", encoding="utf-8") as f:
            ok = f.read() == "ok"
        rep.add(s, "UTF-8 文件名读写", "OK" if ok else "FAIL", "创建/读取中文名文件{}".format("成功" if ok else "失败"))
    except Exception as e:
        rep.add(s, "UTF-8 文件名读写", "FAIL", str(e))
    finally:
        shutil.rmtree(d, ignore_errors=True)

# 文件系统能力 -----------------------------------------------------------------------------------------

def probe_filesystem(rep):
    s = "文件系统能力"
    rep.add(s, "路径分隔符", "INFO", "os.sep={!r} os.pathsep={!r}".format(os.sep, os.pathsep))
    rep.add(s, "临时目录",   "INFO", tempfile.gettempdir())
    rep.add(s, "HOME",       "INFO", os.path.expanduser("~"))
    d = tempfile.mkdtemp(prefix="litex-fs-")
    try:
        # 基础写入。
        try:
            p = os.path.join(d, "t.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("x")
            with open(p, "r", encoding="utf-8") as f:
                assert f.read() == "x"
            rep.add(s, "临时目录写入", "OK", tempfile.gettempdir(), required=True)
        except Exception as e:
            rep.add(s, "临时目录写入", "FAIL", str(e), required=True)
        # 大小写敏感性。
        try:
            with open(os.path.join(d, "LitexCase.TXT"), "w") as f:
                f.write("x")
            case_sensitive = not os.path.exists(os.path.join(d, "litexcase.txt"))
            rep.add(s, "文件名大小写", "INFO",
                    "敏感（类 Unix 行为，LiteX 上游按此设计）" if case_sensitive else "不敏感（Windows 行为）")
        except Exception as e:
            rep.add(s, "文件名大小写", "WARN", str(e))
        # 符号链接（libxil 等使用 os.symlink；安装主流程不依赖）。
        try:
            t = os.path.join(d, "target.txt")
            l = os.path.join(d, "link.txt")
            with open(t, "w") as f:
                f.write("x")
            os.symlink(t, l)
            ok = os.path.exists(l)
            rep.add(s, "符号链接", "OK" if ok else "FAIL",
                    "可用" if ok else "创建后无法解析")
        except AttributeError:
            rep.add(s, "符号链接", "INFO", "当前 Python 无 os.symlink")
        except OSError as e:
            rep.add(s, "符号链接", "WARN",
                    "不可用: {}（影响 libxil/Xilinx 流程，不阻塞核心验收）".format(e))
        # 硬链接。
        try:
            os.link(os.path.join(d, "target.txt"), os.path.join(d, "hard.txt"))
            rep.add(s, "硬链接", "OK", "可用")
        except (AttributeError, OSError) as e:
            rep.add(s, "硬链接", "INFO", "不可用: {}".format(e))
        # 可执行位（venv/bin 激活、console scripts 运行的前提）。
        if os.name != "nt":
            try:
                sp = os.path.join(d, "lxexec.sh")
                with open(sp, "w", encoding="utf-8") as f:
                    f.write("#!/bin/sh\necho LXEXEC-OK\n")
                os.chmod(sp, 0o755)
                rc, out = run_cmd([sp], timeout=15)
                if rc == 0 and "LXEXEC-OK" in out:
                    rep.add(s, "可执行位 (chmod +x 后可直接运行)", "OK", out, required=True)
                else:
                    rep.add(s, "可执行位 (chmod +x 后可直接运行)", "FAIL",
                            "退出码 {}，输出: {}".format(rc, out))
            except Exception as e:
                rep.add(s, "可执行位 (chmod +x 后可直接运行)", "FAIL", str(e), required=True)
        else:
            rep.add(s, "可执行位", "INFO", "Windows 无此概念（参考环境预期）")
        # 255 字节文件名（POSIX 单组件上限；LiteX 生成文件名普遍 40~80 字符）。
        name255 = "a" * 251 + ".txt"          # 恰好 255 字节 ASCII
        name120 = "a" * 116 + ".txt"          # 保守长度对照组
        try:
            with open(os.path.join(d, name255), "w") as f:
                f.write("x")
            rep.add(s, "255 字节文件名", "OK", "255 字节 ASCII 组件名可创建")
        except OSError as e255:
            try:
                with open(os.path.join(d, name120), "w") as f:
                    f.write("x")
                rep.add(s, "255 字节文件名", "WARN",
                        "255 字节失败而 120 字节成功（{}）——若为 Windows 参考环境，"
                        "通常是 MAX_PATH 总长限制而非文件系统组件限制；真机上需记录实际组件上限".format(e255))
            except OSError as e120:
                rep.add(s, "255 字节文件名", "FAIL", "120 字节亦失败: {}".format(e120))
        # 深层长路径（LiteX build/<config> 目录层级较多时使用）。
        try:
            deep = os.path.join(d, *["lvl{}".format(i) for i in range(8)])
            os.makedirs(deep)
            long_name = "litex_build_" + "x" * 180 + ".v"
            with open(os.path.join(deep, long_name), "w") as f:
                f.write("x")
            rep.add(s, "长路径（嵌套 8 层 + 180 字符文件名）", "OK", "总长 {} 字符".format(
                len(os.path.join(deep, long_name))))
        except OSError as e:
            rep.add(s, "长路径（嵌套 8 层 + 180 字符文件名）", "WARN",
                    "失败: {}（Windows 参考环境受 MAX_PATH 260 限制；真机记录实际总长上限即可）".format(e))
        # HOME 可写（--user 安装与 pip 缓存需要）。
        try:
            hp = os.path.join(os.path.expanduser("~"), ".litex-env-check-tmp")
            with open(hp, "w") as f:
                f.write("x")
            os.remove(hp)
            rep.add(s, "HOME 目录可写", "OK", os.path.expanduser("~"))
        except OSError as e:
            rep.add(s, "HOME 目录可写", "WARN", "{}（影响 --user 安装与 pip 缓存）".format(e))
    finally:
        shutil.rmtree(d, ignore_errors=True)

# 子进程 -----------------------------------------------------------------------------------------------

def probe_subprocess(rep):
    s = "子进程能力"
    rc, out = run_cmd([sys.executable, "-c", "print('LXSUB-OK')"], timeout=30)
    if rc == 0 and "LXSUB-OK" in out:
        rep.add(s, "基本子进程 (python -c)", "OK", out, required=True)
    else:
        rep.add(s, "基本子进程 (python -c)", "FAIL", "退出码 {}，输出: {}".format(rc, out), required=True)
    env = os.environ.copy()
    env["LITEX_CHECK_VAR"] = "1"
    rc, out = run_cmd([sys.executable, "-c", "import os; print(os.environ['LITEX_CHECK_VAR'])"], env=env)
    rep.add(s, "环境变量继承", "OK" if rc == 0 and out == "1" else "FAIL", out or "退出码 {}".format(rc))
    rc, out = run_cmd([sys.executable, "-c", "import os; print(os.getcwd())"], cwd=tempfile.gettempdir())
    rep.add(s, "工作目录指定 (cwd 参数)", "OK" if rc == 0 else "FAIL", out or "退出码 {}".format(rc))
    sh = shutil.which("sh")
    if sh:
        rc, out = run_cmd([sh, "-c", "echo LXSH-OK"], timeout=15)
        rep.add(s, "shell 子进程 (sh -c)", "OK" if rc == 0 and "LXSH-OK" in out else "FAIL",
                out or "退出码 {}".format(rc))
    else:
        rep.add(s, "shell 子进程 (sh -c)", "INFO", "未找到 sh（Windows 参考环境预期；构建工具调用主要走 argv 形式）")

# Git --------------------------------------------------------------------------------------------------

def probe_git(rep):
    s = "Git"
    git = shutil.which("git")
    if git is None:
        rep.add(s, "git 可执行文件", "FAIL",
                "PATH 中未找到 git（litex_setup.py --init 与手动安装 Migen 均依赖，核心必达）", required=True)
        return
    rc, out = run_cmd(["git", "--version"], timeout=15)
    if rc != 0:
        rep.add(s, "git 可执行文件", "FAIL", out or "退出码 {}".format(rc), required=True)
        return
    rep.add(s, "git 可执行文件", "OK", "{} ({})".format(out, git), required=True)
    if not rep.full:
        rep.add(s, "git 远端连通性", "SKIP", "--full 模式检测")
        return
    # M-Labs 是手动最小安装的必达网络目标（Migen 只此一家）；GitHub 影响
    # litex_setup.py --init 完整流程，手动模式下 LiteX 仓库已在本地，故降级为 WARN。
    for url, desc, required, fail_status in [
        ("https://git.m-labs.hk/M-Labs/migen.git", "M-Labs 连通 (git ls-remote)", True,  "FAIL"),
        ("https://github.com/enjoy-digital/litex.git", "GitHub 连通 (git ls-remote)", False, "WARN"),
    ]:
        rc, out = run_cmd(["git", "ls-remote", "--heads", url], timeout=30)
        detail = out.splitlines()[0] if rc == 0 and out else "退出码 {}，输出: {}".format(rc, out[-500:])
        rep.add(s, desc, "OK" if rc == 0 else fail_status, detail, required=required)

# 网络 --------------------------------------------------------------------------------------------------

def probe_network(rep):
    s = "网络连通性"
    if not rep.full:
        rep.add(s, "HTTP(S) 访问", "SKIP", "--full 模式检测", required=True)
        return
    # 判定原则：DNS/TLS/HTTP 任一层拿到响应即"可达"（HTTP 4xx/5xx 说明服务端有响应，
    # 例如 files.pythonhosted.org 根路径返回 404 属正常）；仅连接失败/超时记 FAIL。
    import urllib.error
    for desc, url, severity in NET_ENDPOINTS:
        req = urllib.request.Request(url, headers={"User-Agent": "litex-env-check/1.0"})
        try:
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=15) as r:
                status = getattr(r, "status", None) or r.getcode()
            detail = "HTTP {}，耗时 {:.1f}s".format(status, time.time() - t0)
            rep.add(s, desc, "OK", detail, required=(severity == "required"))
        except urllib.error.HTTPError as e:
            rep.add(s, desc, "OK",
                    "HTTP {}（服务端可达；该路径无内容，不影响连通判定）".format(e.code),
                    required=(severity == "required"))
        except Exception as e:
            rep.add(s, desc, "FAIL" if severity == "required" else "WARN", str(e),
                    required=(severity == "required"))

# 外部工具 -----------------------------------------------------------------------------------------------

def probe_tools(rep):
    s = "外部工具"
    for category, exe, version_args, impact in TOOLS:
        path = shutil.which(exe)
        if path is None:
            rep.add(s, "{}/{}".format(category, exe), "SKIP", "未安装（{}）".format(impact))
            continue
        if not rep.full:
            rep.add(s, "{}/{}".format(category, exe), "INFO", path)
            continue
        rc, out = run_cmd([exe] + version_args, timeout=15)
        first = out.splitlines()[0] if (rc == 0 and out) else "退出码 {}".format(rc)
        rep.add(s, "{}/{}".format(category, exe), "OK" if rc == 0 else "WARN",
                "{} | {}".format(path, first))

# Python 依赖 --------------------------------------------------------------------------------------------

def _module_version(mod_name, dist_name):
    try:
        import importlib.metadata as md
        return md.version(dist_name)
    except Exception:
        pass
    try:
        mod = __import__(mod_name)
        return getattr(mod, "__version__", "已导入（无版本属性）")
    except Exception:
        return None

def probe_pydeps(rep):
    s = "Python 依赖"
    for mod_name, dist_name, purpose, core_required in PY_DEPS:
        ver = _module_version(mod_name, dist_name)
        if ver is not None:
            rep.add(s, dist_name, "OK", "{} —— {}".format(ver, purpose))
        else:
            label = "核心必达" if core_required else "构建/扩展"
            rep.add(s, dist_name, "WARN",
                    "未安装（{}：{}；安装流程完成后本项应变为 OK）".format(label, purpose))
    if not rep.full:
        return
    # POSIX 专属模块（litex_term / litex_server 使用）。
    for m in POSIX_MODULES:
        try:
            __import__(m)
            rep.add(s, "POSIX 模块 {}".format(m), "OK", "可导入（影响 litex_term/litex_server，扩展验收）")
        except ImportError as e:
            if os.name == "nt":
                rep.add(s, "POSIX 模块 {}".format(m), "INFO", "Windows 无此模块（预期）")
            else:
                rep.add(s, "POSIX 模块 {}".format(m), "WARN",
                        "不可导入: {}（若鸿蒙终端缺 termios/pty，litex_term 属于扩展阻塞层级）".format(e))
    # 串口枚举。
    try:
        from serial.tools import list_ports
        ports = list(list_ports.comports())
        if ports:
            rep.add(s, "串口枚举 (pyserial)", "OK",
                    "{} 个: {}".format(len(ports), ", ".join(p.device for p in ports[:8])))
        else:
            rep.add(s, "串口枚举 (pyserial)", "INFO",
                    "枚举能力正常，当前无设备（扩展验收需接设备或回环）")
    except ImportError:
        rep.add(s, "串口枚举 (pyserial)", "WARN", "pyserial 未安装，无法枚举")
    except Exception as e:
        rep.add(s, "串口枚举 (pyserial)", "WARN", "枚举异常: {}".format(e))

# 仓库基线信息 ---------------------------------------------------------------------------------------------

def probe_repo(rep):
    s = "仓库基线"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not (os.path.exists(os.path.join(root, "setup.py")) and os.path.isdir(os.path.join(root, "litex"))):
        rep.add(s, "LiteX 仓库", "INFO", "脚本不在 LiteX 仓库内运行: {}".format(root))
        return
    rep.add(s, "仓库根目录", "INFO", root)
    if shutil.which("git"):
        rc, out = run_cmd(["git", "rev-parse", "HEAD"], cwd=root, timeout=15)
        rc2, br  = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, timeout=15)
        if rc == 0:
            rep.add(s, "当前 commit", "INFO", "{} ({})".format(out, br if rc2 == 0 else "?"))
        rc, out = run_cmd(["git", "status", "--porcelain"], cwd=root, timeout=15)
        if rc == 0:
            rep.add(s, "工作区状态", "INFO", "干净" if not out else "有未提交修改（{} 行）".format(len(out.splitlines())))
    try:
        with open(os.path.join(root, "setup.py"), "r", encoding="utf-8") as f:
            m = re.search(r'version\s*=\s*"([^"]+)"', f.read())
        if m:
            rep.add(s, "LiteX 版本 (setup.py)", "INFO", m.group(1))
    except OSError:
        pass
    mig_sha = None
    try:
        with open(os.path.join(root, "litex_repos.py"), "r", encoding="utf-8") as f:
            m = re.search(r'"migen".*?sha1\s*=\s*(0x[0-9a-fA-F]+)', f.read(), re.S)
        if m:
            mig_sha = "{:040x}".format(int(m.group(1), 16))
    except OSError:
        pass
    rep.add(s, "Migen 基线 SHA1 (litex_repos.py)", "INFO", mig_sha or "未找到")

# 汇总 ---------------------------------------------------------------------------------------------------

def print_text(rep):
    mode = "全量（--full）" if rep.full else "快速（未测网络/Git 远端/venv 实测/工具版本）"
    print("=" * 78)
    print(" LiteX @ HarmonyOS PC 环境检测报告   模式: {}".format(mode))
    print(" 时间: {}".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    print("=" * 78)
    for section, entries in rep.sections():
        print("\n--- {} ---".format(section))
        for e in entries:
            print("{} {:<34} {}".format(tag(e["status"]), e["name"], e["detail"]))
    required = [e for e in rep.entries if e["required"]]
    blockers = rep.blockers()
    print("\n" + "=" * 78)
    print(" 核心必达能力汇总")
    print("=" * 78)
    for e in required:
        print("{} {:<34} {}".format(tag(e["status"]), "/".join([e["section"], e["name"]]), e["detail"][:60]))
    if blockers:
        print("\n共 {} 个 FAIL（核心必达受阻项 {} 个）：".format(
            len(blockers), sum(1 for e in blockers if e["required"])))
        for e in blockers:
            print("  FAIL {} —— {}".format("/".join([e["section"], e["name"]]), e["detail"]))
        print("\n处理要求（分工文档第六节）：阻塞问题必须附命令、完整日志、环境版本和复现步骤，")
        print("按 docs/harmonyos-environment-setup.md 的《阻塞报告模板》整理后同步全组；")
        print("若原生 CPython/pip 受阻（分类: C），立即上报，不得改用虚拟机/容器/兼容层。")
    else:
        missing_required = [e for e in required if e["status"] == "SKIP"]
        if missing_required and not rep.full:
            print("\n未发现 FAIL；另有 {} 项需 --full 模式补测（网络/Git 远端/venv 实测等）。".format(
                len(missing_required)))
        else:
            print("\n未发现 FAIL 项。")
    print("\n合计: {} 项 | OK={} WARN={} FAIL={} SKIP={} INFO={}".format(
        len(rep.entries),
        *[sum(1 for e in rep.entries if e["status"] == s) for s in ["OK", "WARN", "FAIL", "SKIP", "INFO"]]))

def main():
    parser = argparse.ArgumentParser(description="LiteX HarmonyOS PC 环境检测（2 号交付物）")
    parser.add_argument("--full", action="store_true",
                        help="全量模式：+ 网络连通 / Git ls-remote / venv 实测创建 / 外部工具版本")
    parser.add_argument("--json", metavar="PATH", default=None, help="同时输出 JSON 报告到指定文件")
    args = parser.parse_args()

    rep = Report(full=args.full)
    probe_system(rep)
    probe_python(rep)
    if args.full:
        probe_venv_creation(rep)
    probe_encoding(rep)
    probe_filesystem(rep)
    probe_subprocess(rep)
    probe_git(rep)
    probe_network(rep)
    probe_tools(rep)
    probe_pydeps(rep)
    probe_repo(rep)

    print_text(rep)

    if args.json:
        out_dir = os.path.dirname(os.path.abspath(args.json))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rep.to_json(), f, ensure_ascii=False, indent=2)
        print("JSON 报告已写入: {}".format(args.json))

    return 1 if rep.blockers() else 0

if __name__ == "__main__":
    sys.exit(main())
