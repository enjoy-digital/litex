# LiteX @ HarmonyOS PC 依赖兼容矩阵（2 号交付物）

- 原始基线：`litex` @ `db643c5f29d588df1e844e8a53267e1e48553ee5`（分支 `port/harmonyos-pc`，`setup.py` 版本 `2026.04`）；
  Migen 基线 SHA1 `4c2ae8dfeea37f235b52acb8166f12acaaae4f7c`（`litex_repos.py:23-28`，recursive 克隆、非 editable）。
- 分级定义（分工文档 2 号任务）：**① 可直接安装 / ② 需指定版本 / ③ 需源码构建 / ④ 暂不可用**。
- **本表"真机实测"列只填真机验证结果，未验证的一律标注"待测"**。"静态分析"列是从源码与 PyPI 分发形态得出的预判，供真机测试聚焦。
- 检测工具：`scripts/check_environment.py`（对应各项探测点）。
- 按组内决定（2026-09-25）：**Windows 参考环境探测报告不作为交付物**（不代表鸿蒙环境）；本矩阵所有分级最终一律以鸿蒙真机实测回填为准，参考环境仅用于复现与调试安装流程（方法见 `docs/harmonyos-environment-setup.md` §6）。
- **参考环境一致性备案（2 号，2026-10-09）**：1 号 Windows/Python 3.12.10；4 号 Windows/3.12.10 与鸿蒙原生/3.12.14；**3 号 2026-09-30 核心兼容性证据产自 macOS/Python 3.11.3**。分工文档 §1 要求"参考环境 Python 版本与鸿蒙 PC 端可用版本保持一致"——3 号结果可作功能旁证，**不宜作为两端生成对比的"参考环境"基准**；涉及 Python 小版本敏感行为（风险 R2：Migen 名称推断）的结论，以 3.12.x 环境记录为准。

2026-10-08 回填（4 号采集，供 2 号复核）：受测集成提交 `ed0c556c32c0f52a82730dfabd40aea08a192a19`。原生证据见[本次目录](evidence/2026-10-08/)，正式记录采用网络正常后的全新在线安装；完整探测为 0 FAIL。下表的“未在 PATH 发现”不代表鸿蒙平台不可移植或不可安装。

## 1. 前置运行时（核心必达门槛，决定第 5 天 A/B/C 分类）

| 项 | LiteX 源码引用 | 获取途径 | 静态分析分级 | 真机验证点（check_environment.py 章节） | 鸿蒙真机实测 |
|---|---|---|---|---|---|
| 原生 CPython ≥3.7（`python_requires ~=3.7`） | `setup.py:23` | 鸿蒙 PC 系统侧提供 | 待测——**第一优先项**；不可用即 C 类阻塞 | Python / 解释器版本、sys.executable | 原生 HarmonyBrew CPython 3.12.14 / aarch64 可运行；预装运行时，本次未重装 |
| pip | `litex_setup.py:508`（`sys.executable -m pip`） | 随 CPython | 待测；不可用即 C 类阻塞 | Python / pip 可用性 | 26.2.1 可运行 |
| venv + ensurepip | `litex_setup.py:531` 推荐 venv 流程 | 随 CPython | 待测 | venv 实测（--full） | 创建、独立解释器和 ensurepip 均 OK |
| Git（clone / checkout SHA1 / submodule / pull --ff-only） | `litex_setup.py:364, 243, 256, 477` | 设备端提供 | 待测；不可用则需离线导入仓库源码（见 §7 兜底） | Git / git 可执行文件、ls-remote | Git 2.55.0；本地 bundle fetch/checkout OK；两处远端 ls-remote OK；未验证完整 clone/pull/submodule 网络流程 |
| PEP 668 `EXTERNALLY-MANAGED` | `litex_setup.py:524`（存在则拒绝直装） | — | 视系统 Python 策略而定 | Python / PEP 668 标记 | 存在 EXTERNALLY-MANAGED；采用 venv，未修改系统保护 |

**网络端点**（`--full` 模式探测）：

| 端点 | 用途 | 不通时的影响 | 鸿蒙真机实测 |
|---|---|---|---|
| pypi.org / files.pythonhosted.org | pip 安装 §3 依赖 | **核心必达受阻** | 端点可达，在线 pip 下载与安装成功 |
| git.m-labs.hk | 克隆 Migen（唯一官方源） | 核心必达受阻（或走 §7 离线兜底） | HTTPS / git ls-remote OK；源码使用固定提交 bundle |
| github.com | `litex_setup.py --init` standard/full 配置；手动 minimal 不需要 | 扩展 | HTTPS / git ls-remote OK |
| raw.githubusercontent.com | `litex_setup.py:25-26` 自更新 + `litex_repos.py` 下载；仓库内已有该文件且失败被 `except: pass` 吞掉（`litex_setup.py:187-197`） | 不阻塞（用 `--dev` 或在仓库内运行） | HTTP 200 |

## 2. Migen —— ③ 固定源码安装（主路径，已实测）；PyPI sdist 仅备用

本次固定提交构建/安装成功，版本 0.9.2；依赖 Colorama 0.4.6。使用本地 Git bundle，不把远端连通探测当成完整递归克隆的证明。2026-10-09 的补充审计确认 PyPI 0.9.2 与固定 SHA1 不等价，因此项目验收继续按固定源码主路径归为 ③。

| 要点 | 依据 |
|---|---|
| **修订**：矩阵旧版"不在 PyPI 分发、`pip install migen` 不可作为安装途径"**有误**。实测 PyPI 存在 migen 0.9 / 0.9.1 / **0.9.2**，分发形态为 **sdist 源码包**（无预成 wheel）；它需要 setuptools/wheel 在本地构建，且与固定 SHA1 不等价，所以不能作为 ① 直接安装，也不改变主路径的 ③ 分类 | 参考环境 `pip index versions migen`、`pip download migen==0.9.2` 实测（得 migen-0.9.2.tar.gz）；`litex_repos.py:23-28` |
| 主路径不变：从 `git.m-labs.hk/M-Labs/migen.git` 克隆并 checkout 固定 SHA1——litex_setup 与 2 号脚本默认走此路线（来源可审计、与基线严格一致）；PyPI `migen==0.9.2` 仅作 m-labs 不可达时的备用（版本选择须记录，分工文档 §9"所有版本选择必须记录"） | `litex_repos.py:23-28`；`litex_setup.py:406`；§7 兜底 |
| 1 号基线 `pip install -e .` 成功且 venv 内 migen 为 0.9.2，与"PyPI 解析依赖"路线一致 | `PORT_BASELINE.md` 第 4 步与版本表 |
| recursive 克隆对 migen 本体冗余：基线提交 `4c2ae8df`（2024-12-02）经实测**无 `.gitmodules`/子模块**（175 个跟踪文件） | 2026-10-09 参考环境 m-labs 克隆实测；`litex_setup.py:240-252` |
| **等价性审计结论（2 号，2026-10-09，离线完成）：不等价**。PyPI `migen-0.9.2` sdist = **0.9.2 tag 点内容**；基线 SHA1 `4c2ae8df`（2024-12-02，"Add support for more call opcodes"）为 tag 之后的 master。实测 `diff -r --strip-trailing-cr`：migen 包 26 个 `.py` 内容不同，**其中含代码生成相关模块** `migen/fhdl/verilog.py、tracer.py、simplify.py、visit.py、specials.py`、`migen/build/generic_platform.py、tools.py`、`xilinx/*`、`lattice/*`、`sim/*`；基线另有 12 个 PyPI 不存在的文件（`build/quicklogic/`、`xilinx/symbiflow.py`、`test/test_vcd.py`、新平台文件）。含义：**备用途径存在生成行为漂移风险，仅限 m-labs 完全不可达时应急启用，启用即向 1 号报备并记入矩阵**；两端 Verilog 比较必须两端同用 SHA1 源码路线才严格成立 | 比对物：`pip download migen==0.9.2` vs `git.m-labs.hk/M-Labs/migen.git @ 4c2ae8df`；差异文件清单见本节 |
| **组长复核处理**：`PORT_BASELINE.md` 已区分历史 Windows 基线的 PyPI 0.9.2 与集成验收的固定 SHA1；后续两端生成比较统一使用固定 SHA1 | `PORT_BASELINE.md`；本节审计 |
| Migen 本体为纯 Python，平台兼容风险低，但分发形态仍是源码，需要 setuptools/wheel 在 venv 内就绪（`--no-build-isolation` 路线避免再联网） | `setup_harmonyos.sh` 第 3 步 |
| git.m-labs.hk 为自托管 Gitea；真机 HTTPS 与 `git ls-remote` 已通过，完整递归克隆仍未验证 | §1 网络表；2026-10-08 原生证据 |

## 3. PyPI Python 依赖 —— 预判 ① 可直接安装

| 包 | LiteX 用途（源码位置） | 分发形态与风险 | 分级预判 | 真机验证点 |
|---|---|---|---|---|
| `packaging>=24.2` | `builder.py:22` 版本比较；`litex_setup.py:629` | 纯 Python wheel | ① | pip 安装 + import |
| `pyserial` | `setup.py:27`；`litex_term.py:16`、`comm_uart.py:7`（模块级 import）；`lattice/programmer.py:151`（懒加载） | 纯 Python wheel；**import 必然成功**，串口枚举依赖 OS 设备节点模型 | ①（import）；**串口实际能力单列为扩展项待测** | 检测报告"串口枚举"行；真机需确认 `/dev/tty*` 或鸿蒙等价设备模型是否存在 |
| `requests` | `setup.py:28`；核心生成路径仅 `generic_programmer.py:52` 懒加载 | wheel，依赖链 urllib3/idna/certifi 纯 Python；`charset_normalizer` 的 C 加速扩展是**可选**，装不上会回落纯 Python | ①（预判） | pip 安装日志中留意 charset_normalizer 是否触发源码编译 |
| `setuptools>=65.5`、`wheel` | `litex_setup.py:626-631` 构建依赖 | 官方 wheel 仅覆盖常见平台标签（manylinux/musllinux/win/arm64 等）；**若鸿蒙 CPython 的平台标签不匹配，pip 将回退 sdist → 源码构建 → 需要可用的 C 编译器** | ①/③ 取决于真机 | 真机重点观察：`pip install` 是否出现 "Building wheel for setuptools"；同时看检测报告 C/C++ 编译器行 |

### 本次 Python 依赖实测

固定版本：Packaging 26.3、PySerial 3.5、Requests 2.34.2、Setuptools 84.0.0、Wheel 0.48.0、Colorama 0.4.6；Requests 依赖为 certifi 2026.7.22、charset-normalizer 3.5.1、idna 3.20、urllib3 2.8.0。均由 wheel 安装成功，pip check 通过；其中 charset-normalizer 使用 `cp312-cp312-musllinux_1_2_aarch64` wheel，其余为通用 Python wheel，没有现场编译这些包的 C 扩展。分类为①（所列版本可安装），固定版本用于结果比较，不表示两端包的二进制构建完全相同，也未证明其他版本一定不可用。

PySerial 可导入，`sys.platform=linux`，枚举正常但无设备；term 帮助通过，不代表串口收发通过。上方仍保留安装前的静态预判，最终以这些原生记录为准。

## 4. LiteX 本体

本次 2026.4 从集成提交可编辑安装成功，导入来自新源码，4 个已测 CLI 帮助通过；`litex_sim` 单列为缺 LiteEth。未测试全部 15 个 CLI 的业务功能。

| 要点 | 依据 |
|---|---|
| 本地仓库 `pip install -e`（对齐 `litex_setup.py` 对 develop 仓库的处理：`--no-build-isolation` + editable） | `litex_setup.py:671-683`、`litex_repos.py:34` |
| 安装前必须先装好 Migen，否则依赖解析会去 PyPI 找 `migen` 并失败 | `setup.py:24-29`（install_requires 含 migen） |
| console scripts（`litex_sim` 等 15 个入口）落在 venv 的 `bin/`（POSIX）——依赖**可执行位**与 PATH | `setup.py:54-82`；检测报告"可执行位"行 |
| `litex_setup.py --user` 模式提示 `~/.local/bin` 需进 PATH | `litex_setup.py:739-743`；HOME 可写性见检测报告 |

## 5. 扩展工具链（对应"扩展验收标准"，不阻塞核心）

| 工具 | 用途 | 静态分析结论 | 鸿蒙真机实测 |
|---|---|---|---|
| C/C++ 编译器（cc/gcc/clang） | litex_sim 的 C 仿真构建、依赖 sdist 兜底 | 由平台方提供与否未知；`litex_setup.py` 不安装它 | Clang 15.0.4 --version 成功；cc/gcc 未在 PATH 发现；未执行 C 编译 |
| meson / ninja | `litex_sim` 构建（`setup.py` extras: develop） | meson 纯 Python 可 pip 装；ninja pip 包为**平台二进制 wheel**，标签不匹配即 ④ | Ninja 1.13.2 可运行；Meson 未在 PATH 发现 |
| Verilator | `litex_sim` 仿真 | 无 pip/官方鸿蒙分发路径；需平台方提供或自编译 → 预判 ④（若不可用，按分工文档记录为扩展阻塞层级） | 未在 PATH 发现；未构建或启动，不能据此判定平台不支持 |
| RISC-V GCC（`riscv64-unknown-elf-gcc` 等） | BIOS/固件编译 | `litex_setup.py:878-904` 的自动安装仅识别 apt/dnf/pacman/apk/brew，鸿蒙必走 `toolchain_manual_install` 分支 → **自动化不可用，需人工/④** | 三个检测名称均未在 PATH 发现；固件编译未执行 |
| FPGA 厂商工具（quartus/vivado 等） | 综合/布局布线 | 分工文档首期不纳入 | 不测 |
| 终端类 POSIX 模块 `termios`/`pty`（`litex_term.py:61-62`）、`select`（:223）、`signal`（:395） | litex_term / litex_server | 若鸿蒙 Python 为标准 POSIX 构建则存在；缺一即 litex_term 不可用（扩展层级） | termios / pty / select / fcntl / signal 均可导入 |

## 6. 文件系统与 OS 能力

| 能力 | LiteX 引用 | 结论 |
|---|---|---|
| 子进程 spawn（argv 形式） | 39 个文件 66 处 `subprocess.*` | 原生 Python 子进程、环境继承、cwd 和 sh -c 均 OK |
| `os.execl` 自更新重启 | `litex_setup.py:100` | 失败被外层 `except Exception: pass` 容忍（:196-197），不构成阻塞；`--dev` 可完全跳过 |
| 符号链接 `os.symlink` | 核心安装流程**不使用**；仅 `litex/soc/software/libxil/__init__.py:122`（Xilinx 扩展路径） | 当前临时目录中符号链接可用；硬链接返回 EPERM，未影响核心 |
| 文件名大小写 | 上游按 POSIX 大小写敏感设计 | 当前测试文件系统大小写不敏感；不是对所有挂载点的结论 |
| 255 字节文件名 / 深层长路径 | build/<config> 输出目录嵌套 | 255 字节 ASCII 文件名和 302 字符总路径可创建；未测极限 |
| 可执行位 | venv/bin、console scripts | chmod +x 后直接执行成功 |

## 7. 真机前风险预案（不改变验收口径，仅提高成功率）

1. **平台标签风险**（§3 setuptools/wheel 行）：若真机 pip 无法命中 wheel 且无 C 编译器，可在参考环境对纯 Python 依赖执行 `pip download --no-deps --only-binary=:all: <pkg>` 生成 wheel，连同 Migen 源码包（纯 Python，跨平台）经可信渠道拷入真机离线安装。**所有版本选择记录到本矩阵"真机实测"列。**
2. **Migen 单源风险**：git.m-labs.hk 不通时，由已在参考环境克隆好的基线 SHA1 仓库整体拷贝/打包传递（版本以 SHA1 为准，来源可审计）。**优先于 PyPI 备用途径**——审计（§2）已证 PyPI 0.9.2 为 tag 点旧内容、与基线不等价，仅在 SHA1 源码确实无法传递时启用并报备。
3. 以上两条均不满足时，按分工文档提交 C 类阻塞报告（模板见 `docs/harmonyos-environment-setup.md`），**不得改用虚拟机/容器/兼容层达成验收**。

## 8. 参考环境（Windows 11）——不入库说明

按组内决定（2026-09-25），Windows 环境探测报告无实际验收意义，**不填入本矩阵、不随交付提交**；
`scripts/check_environment.py` 在参考环境的本地输出仅用于脚本调试与安装流程验证。
真机执行后，本矩阵各"真机实测"列即为唯一的分级结论来源。

## 9. 回填状态（2026-10-08）

- [x] 原生完整探测已执行，原始 JSON 随本次证据提交。
- [x] 未修改安装器的全新在线安装流程日志已保存。
- [x] §1–§6 按实测回填；技术分类建议为 B（核心可用，仿真/固件扩展条件不足），待 1/2 号签收确认。
- [x] 审计 PyPI `migen==0.9.2` sdist 与基线 SHA1 `4c2ae8df…` 的内容等价性（§2）——**2026-10-09 已完成，结论：不等价**（0.9.2 为 tag 点，基线为其后 master；fhdl 生成模块有差异，详见 §2 审计行）
