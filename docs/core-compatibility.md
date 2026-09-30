# LiteX 核心鸿蒙 PC 兼容性核查（3 号，第一周）

核查日期：2026-09-30。范围对应四人分工文件中三号第一周六项要求。
LiteX 基线：`6bd66c63f77e3c32452e8b5f7dbfb50df45ad501`；Migen：`4c2ae8dfeea37f235b52acb8166f12acaaae4f7c`。

## 结论

现有证据没有显示首期 Python 核心及最小 SoC 导出需要鸿蒙专属补丁。本分支提供可运行示例、平台审计、复测日志和已知限制；`litex/` 与原有 SoC/HDL 生成逻辑未改动。
补充测试发现一个 macOS 临时路径别名导致的测试误报，已修正该测试的路径比较。

三号第一周技术交付已齐备；这不代表全组验收或 PR 已获批准。交叉验证、组长审核，以及全量 CI 的 LiteEth 依赖冲突仍待处理。原生鸿蒙独立重跑、BIOS/仿真及最终集成回归属于后续工作。

## 第一周要求与交付对应

| 要求 | 完成内容与证据 |
| --- | --- |
| 阅读 gen/build/soc/CLI 关键路径 | 下文调用链与平台审计，结合一号[核心流程](litex-core-flow.md) |
| 运行一号最小用例，定位安装/导入/执行问题 | 本机验收 5/5 必达步骤、24/24 核心测试和最小生成成功；日志已归档 |
| 检查八类平台边界 | 下表逐项列出源码位置、检查方式、结果及边界；补充 25 项测试、5 项宿主检查、4 个 CLI 帮助检查 |
| 根据二号环境结果做最小修改 | 审阅安装方案与四号原生复现记录；未发现需修改核心的证据；实际修复限于路径测试断言 |
| 保持 SoC/HDL 逻辑不变 | `litex/` 与基线一致，鸿蒙示例复用一号用例 |
| 无需改源码时提交记录与示例 | 本文、[证据与复现](evidence/core-compatibility/2026-09-30/README.md)、[鸿蒙示例](../examples/harmonyos_minimal_soc.py) |

## 证据来源与版本

### 本次执行：macOS 补充检查

macOS 26.5.2 arm64、CPython 3.11.3、LiteX 2026.4、Migen 0.9.2、PySerial 3.5。
使用独立 venv、固定 Migen 提交及本工作分支的可编辑 LiteX。第一次验收运行于基线 `6bd66c6`；补充检查运行于 `75c85fd` 加本次测试修正，受测文件 SHA-256 随证据保存。
本机结果不能代替项目要求的 Windows/Linux 参考环境或鸿蒙原生结果。

| 检查 | 结果 | 证据目录中的记录 |
| --- | --- | --- |
| 一号验收脚本 | 5/5 必达步骤，24/24 核心测试通过；总计 5/6 | `acceptance/` |
| 初次扩展检查 | 27 项中 24 通过、1 失败、2 错误，完整保留 | `review/targeted-tests.txt` |
| 修正后、排除 BIOS 依赖的检查 | 25/25 通过 | `review/targeted-core-tests-after.txt` |
| VCD 临时文件、中文路径/编码、拒绝写入、子进程、串口枚举 | 5/5 通过，其中串口为可选检查 | `review/host-probe.json` |
| client、term、soc_gen、periph_gen 帮助 | 4/4 返回 0 | `review/cli-results.json` 及帮助日志 |
| 鸿蒙示例入口 | 普通路径及“中文 空格”路径均生成 9 个文件及摘要 | `example/`、`review/unicode-example.txt` |

`litex_sim --help` 因缺少 LiteEth 保留为 `OPTIONAL_FAIL`，尚未进入 Verilator 阶段。
初次扩展检查中的两个错误来自缺少 `pythondata-software-picolibc` 的 BIOS 相关测试；后续 25 项明确排除这两项，没有把 27 项写成全部通过。

### 已审阅：四号提交的 Windows/鸿蒙原生证据

证据固定至四号提交 `f2d859bb78bb02d18587c6a74c737954ad28fb46`：

- [两端摘要](https://github.com/litex-harmonyos/litex-harmonyos-pc/blob/f2d859bb78bb02d18587c6a74c737954ad28fb46/docs/evidence/2026-09-28/summary.json)：同一 LiteX/Migen 提交，双方 5/5 必达步骤和 24/24 测试通过。Windows Python 3.12.10、鸿蒙 HarmonyBrew Python 3.12.14；补丁版本不完全一致，需组长确认口径或安排对齐复测。
- [全新安装记录](https://github.com/litex-harmonyos/litex-harmonyos-pc/blob/f2d859bb78bb02d18587c6a74c737954ad28fb46/docs/evidence/2026-09-28/clean-install.json)：采用二号 `f6d66ae576baef2d3a29bb55be5cf40c7506e0ad` 未修改的安装脚本、全新 venv/cache、核对哈希的 Git bundle；未验证从远端直接 clone 全套生态，未启用 `--with-litex-setup`。
- [产物比较](https://github.com/litex-harmonyos/litex-harmonyos-pc/blob/f2d859bb78bb02d18587c6a74c737954ad28fb46/docs/evidence/2026-09-28/comparison.json)：8 个文件中 7 个按既定规则归一化后相同；Verilog 层级树注释连接符不同，保留 `DIFFERENT`，团队例外确认待定。

鸿蒙记录的 `platform.system()` 为 `Linux`，完整字符串为 `HarmonyOS-HongMeng_Kernel_1.12.0-aarch64-64bit-ELF`。不能仅凭前者认定是模拟环境，也不能据此推断 PySerial 的 `sys.platform` 分支。
三号本次审阅的是四号已提交记录，没有独立重跑鸿蒙，也没有重放四号完整原始证据包。

## 关键调用链

`setup.py` 安装包与 console scripts → `litex/__init__.py` 的 Migen/Python 兼容初始化 → `litex.gen` 模块、上下文及仿真入口 → `SoCMini`/SoC 总线与 CSR 注册 → `Builder` 创建目录并导出 CSR/头文件 → `GenericToolchain.build` finalize、Verilog 转换及文件写入。

示例设置 `compile_software=False`、`compile_gateware=False`、`run=False`，无 CPU/BIOS，不执行厂商综合或 CPU 编译。CLI 入口定义在 `setup.py`；帮助解析与实际设备访问属于不同阶段。

## 平台边界审计

| 边界 | 源码及检查 | 结果与限制 |
| --- | --- | --- |
| 平台判断 | `litex/__init__.py::_migen_python_compat`、`litex/gen/fhdl/hierarchy.py`、`litex/tools/litex_term.py` | 核查 Python opcode 兼容、Windows/非 Windows 注释分支及 Windows/POSIX 控制台分支。Migen 相关 2 项测试通过，不等于运行过 Python 3.14。没有增设鸿蒙判断。 |
| 路径分隔符与软链接 | `builder.py::__init__/_create_dir/_export_write`、`generic_platform.py::add_source`、`generic_toolchain.py::build` | 使用 os.path；25 项测试覆盖路径/构建行为及异常后恢复 cwd。完整示例的中文空格路径成功。软件 Make 路径对空格和 # 有额外限制，不能外推 BIOS。 |
| 文件权限 | Builder/工具链文件写入、安装的 console scripts | 自建只读目录确实抛出 PermissionError，随后恢复权限并清理。使用 python 运行示例无需给 .py 增加可执行位。设备节点权限未验证。 |
| 临时目录与释放 | `litex/gen/sim/vcd.py::VCDWriter`、`litex/tools/litex_build_bundle.py::run_local` | VCD 使用 TemporaryFile，目标父目录或系统临时目录须可写；相对文件名和中文父目录、句柄关闭及清理实测通过。构建包入口的 mkdtemp/清理仅静态核查。鸿蒙临时目录专项原始记录尚缺。 |
| 字符编码与换行 | `litex/build/tools.py::write_to_file`、Builder 导出、hierarchy 注释 | 使用宿主默认文本编码；本次 PYTHONUTF8=1，中文写读及未变化文件不重写通过。非 UTF-8 locale 未测。四号比较中的注释差异不改变 HDL 逻辑，仍保留原比较状态。 |
| subprocess | `litex/build/tools.py::subprocess_call_filtered`、Builder Meson/Make、构建包 argv/cwd/env | 中文空格参数不拆分，UTF-8 stdout 与子进程返回码 7 原样传播。解码受宿主编码影响；鸿蒙全部外部程序行为未测试。 |
| 串口枚举与通信 | `litex_term.py`、`remote/comm_uart.py`、PySerial 3.5 `serial.tools.list_ports*` | PySerial 按 os.name/sys.platform 选后端。本机 list_ports_osx 枚举 3 项，未打开端口。鸿蒙 sys.platform/枚举明细未提交；环境脚本可选 WARN 不计 FAIL，不能由“0 FAIL”推断枚举通过。 |
| 外部命令 | Builder 软件编译路径、`litex_sim.py`、一号用例 | 当前导出无需 Meson/Verilator/RISC-V GCC。四号环境快照中 Clang/Make/Ninja/CMake 可见，其余上述三项不在 PATH；不代表不能安装。LiteEth 缺失与 CI LiteEth 版本冲突分别记录。 |

## 实际修改与复现

`examples/harmonyos_minimal_soc.py` 调用 `minimal_soc_baseline.main`，沿用参数、产物检查和 SHA-256 清单。

`test/build/test_generic_platform_toolchain.py` 原先比较登记路径字符串。本机临时目录经 getcwd() 解析后出现 /var/... 与 /private/var/...；samefile 和 realpath 均确认是同一文件。现比较两侧 realpath，仍验证生成的 top.v 已登记。修复前失败日志、诊断及修复后 25 项测试均归档。这是测试可移植性修复，不是鸿蒙核心故障。

在仓库根目录、已安装项目固定依赖的环境中运行：

```sh
PYTHONUTF8=1 python examples/harmonyos_minimal_soc.py --output-dir build/harmonyos-minimal-soc --clean
PYTHONUTF8=1 python scripts/run_acceptance.py --output-dir build/acceptance-core
PYTHONUTF8=1 python docs/evidence/core-compatibility/2026-09-30/host_probe.py
```

完整补充命令、环境与哈希见[证据说明](evidence/core-compatibility/2026-09-30/README.md)。--clean 只指向本次专用生成目录。

## 已知问题与交接

1. **全量 CI 未通过：** [运行 36674290272](https://github.com/litex-harmonyos/litex-harmonyos-pc/actions/runs/36674290272) 的分片 1、4 共三个用例失败，均为 LiteEth mac/padding.py:89 调用本基线没有的 stream.byte_count。工作流安装动态生态依赖后再安装本项目，应由集成负责人固定并验证兼容生态提交。失败调用栈已归档。本周未为此修改 HDL 或跳过 CI 测试，不能宣称全量回归通过。
2. **交叉验证与审核：** 另一名成员按证据说明复现，组长审核无需核心补丁的结论与测试修正后决定合并 PR #4；当前没有代写通过意见。
3. **版本与比较口径：** 组长/四号确认 Python 补丁版本差异及注释差异验收规则，保留机器报告 DIFFERENT。
4. **真机专项检查：** 进入串口或仿真扩展时，由二号/四号回填鸿蒙 sys.platform、枚举后端/结果、设备权限及工具链版本；可复用本次宿主探测脚本。
5. **新失败处理：** 先保存提交、解释器/依赖、命令、完整 traceback 与最小复现，再修改对应边界并做前后对照。目前没有额外核心补丁依据。
