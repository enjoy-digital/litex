# LiteX 鸿蒙 PC 第一周验证报告

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
| 新空环境全流程复现 | 未执行 | 未执行，复用已有公共虚拟环境 |

耗时仅为当次运行记录，不作为性能结论。两端使用的现有验收脚本未因可选项失败而跳过核心步骤。

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

## 证据位置

- 仓库内提交上述摘要和比较报告，以及 [CSR 参考数据](test/fixtures/harmonyos/README.md)。这些是从实际产物提取的交付内容。
- 原始 Windows 验收 JSON、完整日志、9 个生成文件及原始哈希留在本地 `build/acceptance-windows-20260928/`。
- 鸿蒙完整安装记录、验收 JSON、日志和产物已逐字节回收至本地 `build/acceptance-harmonyos-20260928/`；设备原件在 `~/projects/litex/qa-20260928/results/`。
- 本地另保存完整证据 ZIP 供交接，不将大型原始运行目录混入源码。临时 USB 转发及本机传输服务已关闭。

## 尚待完成

1. 组长/另一名成员交叉验证本次结果，确认 Python 3.12.10/3.12.14 的比较口径和层级注释差异；不影响保留当前实测证据。
2. 待 2 号安装流程集成后，从新的虚拟环境复现安装与核心验收；当前结果不能替代此项。
3. 与 2 号确定是否推进 LiteEth 等生态依赖、Verilator 和交叉编译工具链。当前阻塞在可选 Python 导入层，不能宣称 Verilator 已不可用。
4. 形成最终演示、完成团队审阅并向集成分支合并。
