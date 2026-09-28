# 鸿蒙 PC 核心验证与复现

2026-09-28：4 号在 Windows 与鸿蒙 PC 原生 HiShell 中分别运行了现有 `scripts/run_acceptance.py`，两端均为 5/5 必达步骤通过、24/24 核心测试通过。详细结果见 [移植报告](../PORTING_REPORT.md) 和 [证据摘要](evidence/2026-09-28/summary.json)；交接时可使用 [五分钟演示流程及组长确认清单](week1-demo.md)。

## 固定输入

| 项目 | 本次实际值 |
| --- | --- |
| LiteX 源码与验收脚本 | `6bd66c63f77e3c32452e8b5f7dbfb50df45ad501`（集成分支合入基线后的提交） |
| 上游起始基线 | `db643c5f29d588df1e844e8a53267e1e48553ee5` |
| Migen | `4c2ae8dfeea37f235b52acb8166f12acaaae4f7c`，安装后版本 0.9.2 |
| Python | Windows 3.12.10；鸿蒙 3.12.14，补丁版本差异如实保留 |
| 最小用例 | `examples/minimal_soc_baseline.py`，默认 1,000,000 Hz，CPU=None，无随机输入 |
| 公共依赖 | Packaging 26.3、PySerial 3.5、Requests 2.34.2、Setuptools 84.0.0、Wheel 0.48.0；Migen 另需 Colorama 0.4.6 |
| 其他已安装依赖 | pip 26.2.1、certifi 2026.7.22、charset-normalizer 3.5.1、idna 3.20、urllib3 2.8.0 |

这是 4 号重新建立的参考运行，不替代组长 9 月 21 日的原始记录。Windows 使用项目内 uv 管理的 CPython 3.12.10，与组长机器的系统版本和 Python 编译器构建信息不同。

## 鸿蒙本次实际安装路径

复用了已配置的 `~/projects/litex/.venv`，通过 HDC USB 反向转发传入 Git bundle 和 Colorama wheel；核对 SHA-256 后，在新的 `~/projects/litex/qa-20260928/` 目录内检出上表两个完整提交。没有调用尚未合并的 2 号安装脚本，也没有运行 VM、容器或兼容层。

源码目录为 `~/projects/litex/qa-20260928/litex`，Migen 目录为相邻的 `migen`。激活已有环境后，本次离线安装的核心命令如下（在 `qa-20260928` 目录内执行）：

```sh
source ~/projects/litex/env.zsh
python -m pip install --no-index --no-deps ./colorama-0.4.6-py2.py3-none-any.whl
python -m pip install --no-index --no-deps --no-build-isolation ./migen
python -m pip install --no-index --no-deps --no-build-isolation -e ./litex
```

`--no-deps` 依赖已有公共环境，安装后验收入口中的 `pip check` 已通过。这些命令不能作为空环境的完整安装方案；从零安装流程由 2 号维护，待其 PR 集成后另做复现。

## 运行核心验收

两端都在 LiteX 仓库根目录、指定虚拟环境中运行：

```sh
python scripts/run_acceptance.py --output-dir <新的专用输出目录>
```

本次两端均设置 `PYTHONUTF8=1`，且没有使用 `--skip-*`。本次输出位置：

- Windows：仓库内 `build/acceptance-windows-20260928/`。
- 鸿蒙：`~/projects/litex/qa-20260928/results/acceptance/`。
- 回收至 Windows：仓库内 `build/acceptance-harmonyos-20260928/acceptance/`。

验收入口会清理其输出目录下面的 `minimal-soc` 子目录，因此为每次正式运行使用新的专用目录。输出包括环境 JSON、步骤日志、验收 JSON、生成产物和 `baseline-summary.json` 哈希清单。

必达步骤为依赖一致性、LiteX/Migen 导入、`litex.tools.litex_client --help`、24 项核心测试和最小 SoC。`litex_sim --help` 是可选步骤；本次两端均因缺少 LiteEth 失败，尚未执行 Verilator。

## 比较生成产物

将两端的 `minimal-soc` 原始目录放在同一机器，执行：

```sh
python scripts/compare_baseline.py <Windows-minimal-soc目录> <鸿蒙-minimal-soc目录> --output <输入目录以外的comparison.json>
```

退出码 0 表示 `MATCH`，1 表示 `DIFFERENT`，2 表示缺失、损坏或无效输入 `INVALID`。工具核对生成器清单和文件 SHA-256，保留原件，仅在内存中比较。

规则如下：

- 比较全部生成文件，包括存储初始化文件；`litex.log` 和 `baseline-summary.json` 是运行记录，不作为产物文本比较。清单仍用于完整性检查，构建名称和时钟配置必须一致。
- 统一 CRLF/LF；CSR JSON 仅忽略对象键顺序与格式，保留类型和数组顺序，拒绝重复键和非标准数字。
- 仅处理当前生成器的时间戳字段：CSV/头文件页眉，以及 Verilog 页眉、页尾。Git 提交号、寄存器地址、位宽、有效代码、初始化数据、任意其他注释及绝对路径均保留。
- 缺少任何必需产物、清单与文件不符、额外未登记文件或关键值差异都不会报告一致。

本次机器比较为 `DIFFERENT`：7 个文件规范化后一致，Verilog 仅层级树注释的连接字符不同。差异解释在报告中保留，未自动忽略或将其改报为全文件匹配。

## 检查比较工具

```sh
python -m unittest -v test.test_compare_baseline
```

8 项针对性测试覆盖生成日期/换行/JSON 排序、CSR 地址变化、HDL 与初始化数据变化、Git 提交差异、重复 JSON 键、缺失产物、旧哈希和不同配置。本次仅在 Windows 执行此工具测试；鸿蒙执行的是原有核心验收入口。
