# LiteX 鸿蒙 PC 验证报告

## 2026-10-08 集成版本回归

4 号已在 Windows 与原生鸿蒙 PC 上验证集成提交 `ed0c556c32c0f52a82730dfabd40aea08a192a19`，两端均通过 **5/5 必达步骤、24/24 核心测试及 6/6 定向回归**。本次只更新文档和证据；受测集成代码已有 `stream.byte_count`、`stream.byte_mask`、Pmod 辅助代码及路径测试修正，不应沿用旧版“核心未改动”的描述。

| 项目 | 本次结果 |
| --- | --- |
| 固定输入 | LiteX `ed0c556c32c0f52a82730dfabd40aea08a192a19`；Migen `4c2ae8dfeea37f235b52acb8166f12acaaae4f7c`；CPU=None、1 MHz、PYTHONUTF8=1 |
| 解释器 | Windows 3.12.10 / AMD64；HarmonyBrew 3.12.14 / aarch64，补丁及构建差异保留 |
| 必达验收 | 两端均无 skip：pip check、导入、client 帮助、24 项核心测试、最小 SoC 生成通过 |
| 定向回归 | 两端各 6 项：byte_count、byte_mask、3 项 Pmod、生成工具链路径回归通过 |
| 鸿蒙 CLI | client、term、soc_gen、periph_gen 帮助均返回 0 |
| 两端产物 | 8 个文件，7 个按原规则一致；Verilog 仅层级注释字符差异，机器状态 `DIFFERENT` |
| 鸿蒙重复性 | 第二次生成使用 `重复生成 空格` 目录，8 个文件比较 `MATCH` |
| 异常输入 | 时钟 0、-1、非数字分别退出 1、1、2，均未生成输出目录 |
| 清理保护 | 在专用临时目录以 `--output-dir . --clean` 调用，退出 1，原有标记文件保留 |
| 可选仿真 | 两端 `litex_sim --help` 缺 LiteEth；未进入 Verilator |

6 项回归及异常检查使用本次独立在线安装环境。运行后确认设备仓库受版本控制的文件无差异，仅有新建 venv 和日志目录；`include-system-site-packages=false`，导入路径没有旧项目 venv。完整版本、命令和安装方式见[复现说明](docs/harmonyos-pc.md)。

两端比较没有扩大忽略规则。对生成的 `MinimalSoC` 块注释单独将三个 Unicode 树连接符映射为对应 ASCII 字符后，规范化文件全文相同；该核查与机器比较分别保存在[比较报告](docs/evidence/2026-10-08/comparison.json)及[注释差异核查](docs/evidence/2026-10-08/comment-diff-review.json)。是否接受例外仍由组长确认。

PR #1/#3/#4 已于 10 月 7 日合并。受测提交的[四组 Ubuntu CI](https://github.com/litex-harmonyos/litex-harmonyos-pc/actions/runs/37606624203)已成功；主要测试解释器为 Python 3.9，不能替代本次原生验收。比较工具未变化，继续复用已有 8 项测试及 CI 证据。当前没有新增鸿蒙专属补丁依据。

### 安装与扩展边界

在全新目录 `~/projects/litex/qa-final-20261008-online-r2/` 使用空缓存和固定依赖约束，调用未修改的 `sh scripts/setup_harmonyos.sh`。PyPI 公共依赖下载、安装和核心验收全部通过；安装前完整探测为 **0 FAIL**，M-Labs/GitHub 的 git ls-remote 与 5 个 HTTPS 端点均可达。源码通过 SHA-256 校验的 Git bundle 提供，没有把连通性检查写成完整远端递归克隆验证。已有原生 HarmonyBrew Python/Git 和可写 TMPDIR 是前提，未重装基础工具。

Clang 15.0.4、Make 4.4.1、Ninja 1.13.2、CMake 4.4.3 可启动；Meson、Verilator 和三个 RISC-V GCC 名称未在 PATH 发现，不能据此判定平台不支持。PySerial 枚举正常但无设备，未验证真实通信。BIOS、完整仿真和 FPGA 板级结果均不在本次通过结论内。[阻塞记录](docs/evidence/2026-10-08/blockers.md)列出完整错误、负责人及后续条件。

### 交付与剩余团队事项

[证据目录](docs/evidence/2026-10-08/)提供摘要、原生探测、两端比较和重复性记录；[完整证据包](docs/evidence/2026-10-08/full-evidence.zip)包含原始日志、产物、安装约束、实际执行器、原生截图和逐文件 SHA-256，可随收尾 PR 下载。原设备结果及本地 `build/acceptance-*-20261008/` 分别保留，没有覆盖 9 月证据。[演示流程](docs/week1-demo.md)已更新，第二次生成兼作执行流程演练；截图明确标注为保存结果展示，未录制视频。

四号技术交付已形成可审阅证据。仍需一号确认 Python 补丁版本和注释例外、决定扩展范围、亲自完成最终空目录复现，并由另一成员复核收尾 PR、一号合并和完成课程提交。Issues 当前关闭，是否使用 PR 跟踪替代由一号决定；没有代写团队通过意见。

---

## 2026-09-28 历史验证记录

日期：2026-09-28；责任范围：4 号测试、结果比较与交付。

## 结论

同一 LiteX 提交与固定 Migen 提交在 Windows 参考环境、鸿蒙 PC 原生环境中均通过 5/5 必达验收步骤和 24/24 便携核心测试，均成功生成最小 SoC 的 HDL、CSR 和软件头文件。本次没有修改 LiteX 核心代码。

8 个生成文件中，7 个按已记录规则一致；剩余 Verilog 差异仅为生成的层级树注释采用 ASCII 或 Unicode 连接字符。节点名称、树结构及其余文本一致（已先处理页眉/页尾日期和换行）。这支持本次最小用例的代码生成兼容结论，不等于固件编译、完整仿真或 FPGA 硬件验证。

## 环境与来源

| 项目 | Windows 参考运行 | 鸿蒙原生运行 |
| --- | --- | --- |
| 系统 | Windows 11，10.0.26200，AMD64 | HarmonyOS / HongMeng Kernel 1.12.0，aarch64 |
| Python | 3.12.10，项目内 CPython | 3.12.14，HarmonyBrew 原生 Python |
| LiteX | 2026.4；`6bd66c63f77e3c32452e8b5f7dbfb50df45ad501` | 相同 |
| Migen | 0.9.2；`4c2ae8dfeea37f235b52acb8166f12acaaae4f7c` | 相同 |
| 配置 | MinimalSoC，1 MHz，CPU=None | 相同 |
| 验收选项 | 无 skip，PYTHONUTF8=1 | 相同 |

鸿蒙解释器的 `platform.system()` 返回 `Linux`，`platform.platform()` 返回 `HarmonyOS-HongMeng_Kernel_1.12.0-aarch64-64bit-ELF`；保留原始值，设备和原生 HiShell 路径有实际操作与日志证据。没有把该单个字段当成 Linux/虚拟机判据。

公共依赖版本两端一致，完整版本与复现步骤见 [使用说明](docs/harmonyos-pc.md)。Python 补丁版本和系统/编译器构建差异尚需组长确认比较口径；本次不声称只改变了操作系统一个变量。

## 实际结果

| 项目 | Windows | 鸿蒙 |
| --- | --- | --- |
| pip check | PASS | PASS |
| LiteX/Migen 导入 | PASS | PASS |
| litex_client 帮助 | PASS | PASS |
| 便携核心测试 | 24/24，测试日志 17.000 秒 | 24/24，测试日志 31.556 秒 |
| 最小 SoC 生成 | PASS | PASS |
| 必达步骤汇总 | 5/5 | 5/5 |
| 可选 litex_sim 帮助 | OPTIONAL_FAIL：缺少 LiteEth | 相同 |
| BIOS / 固件编译 | NOT_RUN | NOT_RUN |
| Verilator 完整仿真 | NOT_RUN | NOT_RUN |
| 新空环境全流程复现 | 未执行 | PR #1 全新虚拟环境已通过，详见下节 |

耗时仅为当次运行记录，不作为性能结论。两端使用的现有验收脚本未因可选项失败而跳过核心步骤。

## 全新虚拟环境安装复现

4 号已在鸿蒙原生 HiShell 中交叉验证 2 号 PR #1 的 `f6d66ae576baef2d3a29bb55be5cf40c7506e0ad`：在新的 `~/projects/litex/qa-clean-20260928-r2/` 目录运行未修改的 `sh scripts/setup_harmonyos.sh`，安装和核心验收退出码均为 0，5/5 必达步骤与 24/24 核心测试通过（测试日志 31.447 秒）。`litex_soc_gen`、`litex_periph_gen` 的帮助入口也通过；`litex_sim` 仍缺 LiteEth。

运行前项目虚拟环境和 Migen 源码目录均不存在，包缓存独立且初始为空；`include-system-site-packages = false`，Migen 导入来自新虚拟环境，LiteX 导入来自新检出的仓库。依赖版本与原记录一致。已有原生 HarmonyBrew Python/Git 是安装前提；本次未重装操作系统或基础工具。源码通过校验 SHA-256 的 Git bundle 传入，安装脚本使用 `LITEX_MIGEN_URL` 指向本地 bundle；公共依赖由 PyPI 下载，未验证源码的直接网络克隆路径。

安装前完整环境探测、安装后快速探测均为 0 个 FAIL；完整探测保留 `raw.githubusercontent.com` TLS 超时的可选警告。当前 PATH 未发现 Meson、Verilator 和 RISC-V GCC；未尝试移植或构建这些扩展工具。新结果与此前鸿蒙结果相比，CSR JSON 和初始化文件逐字节一致，其余 6 个文件只剩 LiteX 提交号标记变化；机器比较仍为 `DIFFERENT`。源码提交变化来自环境文件，核心代码、最小示例和验收入口未变。

证据：[全新环境摘要](docs/evidence/2026-09-28/clean-install.json)、[与原鸿蒙产物比较](docs/evidence/2026-09-28/clean-install-comparison.json)。这完成了 PR #1 指定提交的安装流程交叉验证，最终集成提交仍需组长复现。

## 产物比较与例外

机器可读证据：[运行摘要](docs/evidence/2026-09-28/summary.json)、[两端比较](docs/evidence/2026-09-28/comparison.json)、[Windows 重复生成比较](docs/evidence/2026-09-28/windows-repeat.json)。

| 产物 | 结果 |
| --- | --- |
| csr.json | 结构一致；地址、大小、访问类型、常量及区域均相同 |
| csr.csv | 换行及生成日期处理后一致 |
| minimal_soc_mem.init | 仅换行差异，初始化内容相同 |
| csr.h / soc.h / mem.h / git.h | 换行及生成日期处理后一致，Git 标识保留 |
| minimal_soc.v | 页眉/页尾日期与换行之外，只剩层级树注释连接字符差异 |

树字符差异来自 [hierarchy.py](litex/gen/fhdl/hierarchy.py)：Windows 使用 `|--`、反引号分支、`|`，其他平台使用 `├──`、`└──`、`│`。人工核查只在这一生成块注释内对应替换三个连接符后，整个文件与参考结果一致；没有删除其他注释或代码。比较工具仍如实输出 `DIFFERENT`，该例外留给组长交叉确认。

Windows 额外进行了一次最小 SoC 生成，8 个产物在已记录规则下全部一致。比较工具的 8 项定向测试通过。已有 24 项核心测试未为文档或比较工具变更重复运行。

PR #3 的提交 `c39782399c28f3f5962ad6acbeb6c1a70b843548` 已通过 [四组 Ubuntu CI](https://github.com/litex-harmonyos/litex-harmonyos-pc/actions/runs/36397687638)。此结果对应上述提交；后续文档提交的 CI 状态应查看 PR 最新 Checks。Ubuntu CI 与鸿蒙原生验收分别记录。

## 证据位置

- 仓库内提交上述摘要和比较报告，以及 [CSR 参考数据](test/fixtures/harmonyos/README.md)。这些是从实际产物提取的交付内容。
- 原始 Windows 验收 JSON、完整日志、9 个生成文件及原始哈希留在本地 `build/acceptance-windows-20260928/`。
- 鸿蒙完整安装记录、验收 JSON、日志和产物已逐字节回收至本地 `build/acceptance-harmonyos-20260928/`；设备原件在 `~/projects/litex/qa-20260928/results/`。
- 新环境的 31 份原始日志/JSON/产物及两张原生终端截图位于本地 `build/acceptance-harmonyos-clean-20260928-r2/`；设备原件在同名 `qa-clean-20260928-r2/results/`。截图展示保存的结果，未重复运行测试。
- 首次传输在 bundle 分支检出阶段失败，安装器尚未运行；已修正传输调用并保留该次记录，未将它记作安装器失败。
- 本地另保存完整证据 ZIP 供交接，不将大型原始运行目录混入源码。临时 USB 转发及本机传输服务已关闭。

## 尚待完成

1. 组长/另一名成员交叉验证本次结果，确认 Python 3.12.10/3.12.14 的比较口径和层级注释差异；不影响保留当前实测证据。
2. PR #1 指定提交的全新环境安装已通过；待相关 PR 集成后，由组长对最终提交进行空目录复现。
3. 与 2 号确定是否推进 LiteEth 等生态依赖、Verilator 和交叉编译工具链。当前阻塞在可选 Python 导入层，不能宣称 Verilator 已不可用。
4. 已补齐 [五分钟演示流程与交接清单](docs/week1-demo.md) 和两张原生终端证据截图，最终视频尚未录制；完成另一成员对 4 号交付的复核后，由组长审核并向集成分支合并。
