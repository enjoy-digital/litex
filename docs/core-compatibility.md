# LiteX 核心鸿蒙 PC 兼容性核查（3 号，第一周）

核查日期：2026-09-30。代码基线为 `6bd66c63f77e3c32452e8b5f7dbfb50df45ad501`，Migen 固定提交为 `4c2ae8dfeea37f235b52acb8166f12acaaae4f7c`。

## 结论与证据边界

现有证据未显示首期 LiteX Python 核心需要鸿蒙专属补丁。本次不修改 `litex/` 源码，也不把缺少可选生态包或外部工具链写成核心故障。`examples/harmonyos_minimal_soc.py` 复用组内已经验证的导出型最小 SoC 用例，避免维护第二套 SoC 描述。

- **鸿蒙原生结果（4 号成员实测，本次核查其提交证据，非 3 号独立重跑）：** [PR #3 的移植报告](https://github.com/litex-harmonyos/litex-harmonyos-pc/blob/feature/tests-docs/PORTING_REPORT.md)记录了 Python 3.12.14、5/5 必达步骤、24/24 核心测试及 Verilog、CSR、头文件生成成功。该报告还记录了对 [PR #1 安装脚本](https://github.com/litex-harmonyos/litex-harmonyos-pc/pull/1)指定提交的全新虚拟环境复现。两份 PR 均尚未合入本代码基线。
- **本机参考复测（3 号本次执行）：** macOS arm64、Python 3.11.3、Migen 0.9.2、LiteX 2026.4；运行 `python scripts/run_acceptance.py --output-dir /private/tmp/litex-core-compat-acceptance`，5/5 必达步骤通过，24/24 核心测试通过。日志和 JSON 位于该临时目录，不作为鸿蒙真机证据。`litex_sim --help` 因未安装 `liteeth` 标为 `OPTIONAL_FAIL`。

## 平台边界核查

| 边界 | 源码与检查结果 | 判断 |
| --- | --- | --- |
| 模块导入与自动命名 | `litex/gen/`、`litex/soc/integration/soc.py`；鸿蒙实测的导入、24 项测试、最小 SoC 生成均通过 | 当前基准无可复现核心故障；不能把其他 Python 版本上的 Migen 命名失败归因于鸿蒙 |
| 路径、目录和权限 | `litex/build/generic_toolchain.py` 用 `os.makedirs` 建目录，生成 Verilog 后恢复工作目录；`builder.py` 对输出路径使用 `os.path` 并创建父目录 | 本次鸿蒙生成产物齐全；暂无路径或权限补丁依据 |
| 文本编码与换行 | `litex/build/tools.py::write_to_file` 使用宿主默认编码、换行；PR #3 比较工具对日期及 CRLF/LF 作了明确处理 | 当前生成成功；不同宿主的原始字节哈希不能直接等同语义差异 |
| 层级树注释 | `litex/gen/fhdl/hierarchy.py:17-24` 明确在 Windows 使用 ASCII 连接符，在其他平台使用 Unicode 连接符；[比较明细](https://github.com/litex-harmonyos/litex-harmonyos-pc/blob/feature/tests-docs/docs/evidence/2026-09-28/comparison.json)只显示该注释块的连接符差异 | 保留机器报告的 `DIFFERENT`，说明其不改变 HDL 逻辑；不为凑齐产物哈希而改动生成代码 |
| 子进程与工具链 | 导出型最小用例设置 `compile_software=False`、`compile_gateware=False`、`run=False`；`builder.py` 的 Meson/Make 调用属于软件构建路径 | 首期导出无需 Meson、Verilator、RISC-V GCC；后续工具链能力另行验证 |
| 串口与 CLI | `litex/tools/litex_term.py` 的 Windows 与 POSIX 控制台分支、PySerial 实际设备访问不在最小 SoC 路径；核心 `litex_client --help` 已通过 | CLI 帮助可用不代表串口真机通信已验证；不得写为已通过 |

## 可运行示例与复核

在已安装 LiteX/Migen 的环境中，从仓库根目录运行：

```sh
python examples/harmonyos_minimal_soc.py --output-dir build/harmonyos-minimal-soc --clean
python scripts/run_acceptance.py --output-dir build/acceptance-core
```

示例沿用 `examples/minimal_soc_baseline.py` 的参数、生成文件检查和 SHA-256 清单。预期至少生成 `gateware/minimal_soc.v`、`csr.csv`、`csr.json`、`software/include/generated/csr.h` 与 `soc.h`。

若之后在鸿蒙真机发现新的核心失败，应保存原始命令、解释器和依赖版本、完整 traceback、最小复现及修复前后结果，再在平台边界作最小修改并补充回归测试。本次没有此类失败，因此没有虚构补丁或修复前日志。

## 本周交接

1. 1 号审核“当前无需修改核心源码”的结论，并确认层级树注释差异的验收口径。
2. 2 号提供环境矩阵真机回填，继续区分 Python 核心与可选工具链。
3. 4 号 PR #3 保留原始 `DIFFERENT` 报告；最终集成提交的重新验收由集成负责人安排。
