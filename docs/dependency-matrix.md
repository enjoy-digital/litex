# LiteX @ HarmonyOS PC 依赖兼容矩阵（2 号交付物）

- 基线：`litex` @ `db643c5f29d588df1e844e8a53267e1e48553ee5`（分支 `port/harmonyos-pc`，`setup.py` 版本 `2026.04`）；
  Migen 基线 SHA1 `4c2ae8dfeea37f235b52acb8166f12acaaae4f7c`（`litex_repos.py:23-28`，recursive 克隆、非 editable）。
- 分级定义（分工文档 2 号任务）：**① 可直接安装 / ② 需指定版本 / ③ 需源码构建 / ④ 暂不可用**。
- **本表"真机实测"列只填真机验证结果，未验证的一律标注"待测"**。"静态分析"列是从源码与 PyPI 分发形态得出的预判，供真机测试聚焦。
- 检测工具：`scripts/check_environment.py`（对应各项探测点）；参考环境实测记录：`logs/check-environment-windows-reference.txt / .json`。

## 1. 前置运行时（核心必达门槛，决定第 5 天 A/B/C 分类）

| 项 | LiteX 源码引用 | 获取途径 | 静态分析分级 | 真机验证点（check_environment.py 章节） | 鸿蒙真机实测 |
|---|---|---|---|---|---|
| 原生 CPython ≥3.7（`python_requires ~=3.7`） | `setup.py:23` | 鸿蒙 PC 系统侧提供 | 待测——**第一优先项**；不可用即 C 类阻塞 | Python / 解释器版本、sys.executable | 待测 |
| pip | `litex_setup.py:508`（`sys.executable -m pip`） | 随 CPython | 待测；不可用即 C 类阻塞 | Python / pip 可用性 | 待测 |
| venv + ensurepip | `litex_setup.py:531` 推荐 venv 流程 | 随 CPython | 待测 | venv 实测（--full） | 待测 |
| Git（clone / checkout SHA1 / submodule / pull --ff-only） | `litex_setup.py:364, 243, 256, 477` | 设备端提供 | 待测；不可用则需离线导入仓库源码（见 §7 兜底） | Git / git 可执行文件、ls-remote | 待测 |
| PEP 668 `EXTERNALLY-MANAGED` | `litex_setup.py:524`（存在则拒绝直装） | — | 视系统 Python 策略而定 | Python / PEP 668 标记 | 待测 |

**网络端点**（`--full` 模式探测）：

| 端点 | 用途 | 不通时的影响 | 鸿蒙真机实测 |
|---|---|---|---|
| pypi.org / files.pythonhosted.org | pip 安装 §3 依赖 | **核心必达受阻** | 待测 |
| git.m-labs.hk | 克隆 Migen（唯一官方源） | 核心必达受阻（或走 §7 离线兜底） | 待测 |
| github.com | `litex_setup.py --init` standard/full 配置；手动 minimal 不需要 | 扩展 | 待测 |
| raw.githubusercontent.com | `litex_setup.py:25-26` 自更新 + `litex_repos.py` 下载；仓库内已有该文件且失败被 `except: pass` 吞掉（`litex_setup.py:187-197`） | 不阻塞（用 `--dev` 或在仓库内运行） | 待测 |

## 2. Migen —— ③ 需源码构建（预判）

| 要点 | 依据 |
|---|---|
| 不在 PyPI 分发，必须从 `git.m-labs.hk/M-Labs/migen.git` 克隆安装 | `litex_repos.py:23-28`；`pip install migen` 不可作为安装途径 |
| 基线为固定 SHA1，克隆后 `git checkout` 到 40 位哈希 | `litex_setup.py:406` 逻辑；`scripts/setup_harmonyos.sh` 已固化同一 SHA1 |
| recursive 克隆（含子模块） | `GitRepo(clone="recursive")`，`git submodule sync/update --recursive`（`litex_setup.py:240-252`） |
| Migen 本体为纯 Python（预判①安装无障碍，但分发形态是源码）→ 需要 setuptools/wheel 在 venv 内就绪（`--no-build-isolation` 路线避免再联网） | `setup_harmonyos.sh` 第 3 步 |
| 风险：git.m-labs.hk 为自托管 Gitea，境外站点，连通性需真机确认 | §1 网络表 |

## 3. PyPI Python 依赖 —— 预判 ① 可直接安装

| 包 | LiteX 用途（源码位置） | 分发形态与风险 | 分级预判 | 真机验证点 |
|---|---|---|---|---|
| `packaging>=24.2` | `builder.py:22` 版本比较；`litex_setup.py:629` | 纯 Python wheel | ① | pip 安装 + import |
| `pyserial` | `setup.py:27`；`litex_term.py:16`、`comm_uart.py:7`（模块级 import）；`lattice/programmer.py:151`（懒加载） | 纯 Python wheel；**import 必然成功**，串口枚举依赖 OS 设备节点模型 | ①（import）；**串口实际能力单列为扩展项待测** | 检测报告"串口枚举"行；真机需确认 `/dev/tty*` 或鸿蒙等价设备模型是否存在 |
| `requests` | `setup.py:28`；核心生成路径仅 `generic_programmer.py:52` 懒加载 | wheel，依赖链 urllib3/idna/certifi 纯 Python；`charset_normalizer` 的 C 加速扩展是**可选**，装不上会回落纯 Python | ①（预判） | pip 安装日志中留意 charset_normalizer 是否触发源码编译 |
| `setuptools>=65.5`、`wheel` | `litex_setup.py:626-631` 构建依赖 | 官方 wheel 仅覆盖常见平台标签（manylinux/musllinux/win/arm64 等）；**若鸿蒙 CPython 的平台标签不匹配，pip 将回退 sdist → 源码构建 → 需要可用的 C 编译器** | ①/③ 取决于真机 | 真机重点观察：`pip install` 是否出现 "Building wheel for setuptools"；同时看检测报告 C/C++ 编译器行 |

## 4. LiteX 本体

| 要点 | 依据 |
|---|---|
| 本地仓库 `pip install -e`（对齐 `litex_setup.py` 对 develop 仓库的处理：`--no-build-isolation` + editable） | `litex_setup.py:671-683`、`litex_repos.py:34` |
| 安装前必须先装好 Migen，否则依赖解析会去 PyPI 找 `migen` 并失败 | `setup.py:24-29`（install_requires 含 migen） |
| console scripts（`litex_sim` 等 15 个入口）落在 venv 的 `bin/`（POSIX）——依赖**可执行位**与 PATH | `setup.py:54-82`；检测报告"可执行位"行 |
| `litex_setup.py --user` 模式提示 `~/.local/bin` 需进 PATH | `litex_setup.py:739-743`；HOME 可写性见检测报告 |

## 5. 扩展工具链（对应"扩展验收标准"，不阻塞核心）

| 工具 | 用途 | 静态分析结论 | 鸿蒙真机实测 |
|---|---|---|---|
| C/C++ 编译器（cc/gcc/clang） | litex_sim 的 C 仿真构建、依赖 sdist 兜底 | 由平台方提供与否未知；`litex_setup.py` 不安装它 | 待测（检测报告外部工具节） |
| meson / ninja | `litex_sim` 构建（`setup.py` extras: develop） | meson 纯 Python 可 pip 装；ninja pip 包为**平台二进制 wheel**，标签不匹配即 ④ | 待测 |
| Verilator | `litex_sim` 仿真 | 无 pip/官方鸿蒙分发路径；需平台方提供或自编译 → 预判 ④（若不可用，按分工文档记录为扩展阻塞层级） | 待测 |
| RISC-V GCC（`riscv64-unknown-elf-gcc` 等） | BIOS/固件编译 | `litex_setup.py:878-904` 的自动安装仅识别 apt/dnf/pacman/apk/brew，鸿蒙必走 `toolchain_manual_install` 分支 → **自动化不可用，需人工/④** | 待测 |
| FPGA 厂商工具（quartus/vivado 等） | 综合/布局布线 | 分工文档首期不纳入 | 不测 |
| 终端类 POSIX 模块 `termios`/`pty`（`litex_term.py:61-62`）、`select`（:223）、`signal`（:395） | litex_term / litex_server | 若鸿蒙 Python 为标准 POSIX 构建则存在；缺一即 litex_term 不可用（扩展层级） | 待测（--full 报告 POSIX 模块行） |

## 6. 文件系统与 OS 能力

| 能力 | LiteX 引用 | 结论 |
|---|---|---|
| 子进程 spawn（argv 形式） | 39 个文件 66 处 `subprocess.*` | **核心必达**；`--full` 报告"子进程能力"实测 |
| `os.execl` 自更新重启 | `litex_setup.py:100` | 失败被外层 `except Exception: pass` 容忍（:196-197），不构成阻塞；`--dev` 可完全跳过 |
| 符号链接 `os.symlink` | 核心安装流程**不使用**；仅 `litex/soc/software/libxil/__init__.py:122`（Xilinx 扩展路径） | 真机不支持只影响扩展，记 ④（扩展） |
| 文件名大小写 | 上游按 POSIX 大小写敏感设计 | 真机记录实测行为即可（Windows 参考环境已实测：不敏感） |
| 255 字节文件名 / 深层长路径 | build/<config> 输出目录嵌套 | 真机记录组件与总长上限；参考环境实测：Windows 受 MAX_PATH 260 限制（见 logs WARN 项） |
| 可执行位 | venv/bin、console scripts | POSIX 真机必测（报告"可执行位"行，已列为核心必达） |

## 7. 真机前风险预案（不改变验收口径，仅提高成功率）

1. **平台标签风险**（§3 setuptools/wheel 行）：若真机 pip 无法命中 wheel 且无 C 编译器，可在参考环境对纯 Python 依赖执行 `pip download --no-deps --only-binary=:all: <pkg>` 生成 wheel，连同 Migen 源码包（纯 Python，跨平台）经可信渠道拷入真机离线安装。**所有版本选择记录到本矩阵"真机实测"列。**
2. **Migen 单源风险**：git.m-labs.hk 不通时，由已在参考环境克隆好的基线 SHA1 仓库整体拷贝/打包传递（版本以 SHA1 为准，来源可审计）。
3. 以上两条均不满足时，按分工文档提交 C 类阻塞报告（模板见 `docs/harmonyos-environment-setup.md`），**不得改用虚拟机/容器/兼容层达成验收**。

## 8. 参考环境（Windows 11）实测快照

环境：Windows 11 (10.0.26200) / CPython 3.13.5 / pip 25.1.1 / Git 2.51.0.windows.2 / MinGW gcc 14.2.0（不在 PATH 亦可，仅扩展用）。
完整输出：`logs/check-environment-windows-reference.txt`（84 项，0 FAIL）。要点：

| 探测项 | 参考环境结果 |
|---|---|
| Python / pip / venv 实测（含 ensurepip） | OK / OK / OK（venv 创建 6.8s） |
| 子进程、环境变量继承、cwd、sh -c | 全 OK |
| 临时目录写入 / HOME 可写 / 硬链接 | OK；符号链接因 Windows 特权限制 WARN |
| 网络 5 端点 | 全可达（files.pythonhosted.org 根路径 HTTP 404 = 服务可达） |
| git ls-remote m-labs | OK（master `beffe831…`）；GitHub 443 直连一次超时 → 已记 WARN，HTTPS 站点可达 |
| 外部工具 | 仅 gcc 存在；meson/ninja/verilator/riscv 均未装（参考环境同样只保核心必达） |
| Python 依赖 8 项 | 未装（参考环境为"干净起点"，安装后复跑应变 OK）——真机对比基线 |

## 9. 待办（真机执行时回填）

- [ ] `python3 scripts/check_environment.py --full --json logs/check-environment-harmonyos.json`（真机终端执行）
- [ ] `sh scripts/setup_harmonyos.sh` 全流程日志
- [ ] 回填 §1–§6 所有"待测"列；给出第 5 天 A/B/C 分类结论及证据链接
