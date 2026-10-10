# LiteX 鸿蒙 PC 移植参考环境基线

## 1. 基线目的

本文档记录 LiteX 核心在 Windows 参考环境中的安装与测试结果，作为后续鸿蒙 PC 原生环境验证的对照基线。

本基线优先验证以下内容：

- Python 虚拟环境可正常创建；
- LiteX 与 Migen 可从项目环境正常导入；
- LiteX 源码可编辑安装；
- 选定的纯 Python 核心测试可稳定通过；
- 全量测试中的失败可按平台差异、可选依赖和外部工具链进行分类。

全量测试结果不直接作为“LiteX 是否安装成功”的唯一判断标准。LiteX 官方全量 CI 使用 Linux、完整 LiteX 生态、多个 GCC 工具链、Verilator 和 OSS CAD Suite，而本基线是 Windows 上的最小核心环境。

## 2. 源码基线

| 项目 | 值 |
|---|---|
| 仓库 | `https://github.com/litex-harmonyos/litex-harmonyos-pc` |
| 开发分支 | `feature/baseline-integration` |
| 集成分支 | `port/harmonyos-pc` |
| 基线 commit | `db643c5f29d588df1e844e8a53267e1e48553ee5` |
| LiteX 版本 | `2026.4` |
| Migen 版本 | `0.9.2`（本次 Windows 历史基线由 PyPI 解析；集成验收改用固定 SHA1 `4c2ae8dfeea37f235b52acb8166f12acaaae4f7c`，两者内容不等价） |
| 记录日期 | `2026-09-21` |

在开始鸿蒙 PC 对比验证前，不应随意改变上述 commit 和依赖版本。若必须更新，应新增一条基线记录并说明原因。

## 3. 参考环境

| 项目 | 值 |
|---|---|
| 操作系统 | Microsoft Windows 11 家庭中文版 |
| 系统版本 | `10.0.22631`，Build `22631` |
| 系统架构 | 64 位，AMD64 |
| Python | `3.12.10`，64 bit |
| pip | `26.2.1` |
| Git | `2.48.1.windows.1` |
| 虚拟环境 | 项目根目录下 `.venv` |
| 安装方式 | `python -m pip install -e .` |

Python 3.12.10 是本次 Windows 参考环境实际使用的版本。LiteX 官方当前 CI 使用 Python 3.9，因此涉及 Migen 自动命名、反射或字节码分析的测试结果需要单独核对，不能直接归因于操作系统。

## 4. 安装步骤

在 PowerShell 中执行：

```powershell
git clone https://github.com/litex-harmonyos/litex-harmonyos-pc.git
cd litex-harmonyos-pc
git switch feature/baseline-integration

py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
```

## 5. 基础安装验证

### 5.1 依赖一致性

执行：

```powershell
python -m pip check
```

结果：

```text
No broken requirements found.
```

结论：当前虚拟环境中未发现损坏或冲突的 Python 包依赖。

### 5.2 导入验证

执行：

```powershell
python -c "import litex, migen; print('LiteX and Migen import OK')"
```

结果：LiteX 与 Migen 均成功导入。LiteX 从当前仓库源码目录加载，Migen 从 `.venv` 中加载。

## 6. 核心测试基线

执行：

```powershell
python -m unittest -v `
    test.cores.test_code_8b10b `
    test.cores.test_ecc `
    test.soc.test_export
```

结果：

```text
Ran 24 tests in 18.167s

OK
```

结论：8b/10b 编解码、ECC 和 SoC CSR 导出等选定核心功能在 Windows 参考环境中通过。后续鸿蒙 PC 应至少执行同一组测试，并对比通过数量与输出。

## 7. 全量测试记录

执行：

```powershell
python -m unittest discover -s test -v 2>&1 |
    Tee-Object test-windows-full.log
```

有日志支撑的正式运行结果：

```text
Ran 1222 tests in 222.163s

FAILED (failures=14, errors=378, skipped=6)
```

按汇总数字计算，共有 824 项测试通过。此前一次终端运行记录为 14 个 failure、380 个 error 和 6 个 skipped；两次 error 数相差 2，说明部分全量测试可能受测试顺序、共享状态或运行环境影响。本基线以后一次生成并保存完整日志的结果为准。

### 7.1 主要异常类型

| 异常类型 | 日志计数 | 初步判断 |
|---|---:|---|
| `ValueError` | 343 | 主要涉及 Migen 时钟域名称或 LiteX CSR 名称自动提取，需要区分 Python 3.12 兼容性与测试运行方式影响 |
| `ModuleNotFoundError` | 24 | 主要检查缺少的可选 Core、CPU 数据包或完整 LiteX 生态依赖 |
| `ImportError` | 18 | 主要检查可选模块与平台相关组件 |
| `AssertionError` | 14 | 包含路径格式、文本编码、生成结果及平台行为差异 |
| `AttributeError` | 3 | 需要结合具体测试栈进一步定位 |
| `FileNotFoundError` | 2 | 主要检查外部程序、数据文件或工具链缺失 |
| `IndexError` | 2 | 需要结合具体测试栈进一步定位 |
| `ZeroDivisionError` | 2 | 需要结合具体测试栈进一步定位 |
| `PermissionError` | 1 | 检查 Windows 文件占用或临时文件清理行为 |

上述计数来自异常终止行，用于快速分类，不代表所有错误彼此独立。一个公共依赖或公共初始化问题可能造成大量测试连锁报错。

### 7.2 已确认的平台差异

首个 fail-fast 失败位于：

```text
build.test_altera_quartus.TestAlteraQuartus.test_ip_dir_uses_quartus_install_directory
```

差异为：

```text
期望：/opt/intelFPGA_lite/22.1/ip
实际：\opt\intelFPGA_lite\22.1\ip
```

该失败来自 Windows 路径分隔符转换，不能据此判定 LiteX 安装失败。它应作为鸿蒙 PC 移植时的平台路径处理检查项。

其他已观察到的 failure 还包括：

- 层级 Verilog 文本树形字符出现编码差异；
- Builder 生成变量中的 Windows 路径转义和末尾 `.` 差异；
- 部分 FPGA 工具链约束文本与期望值不一致。

### 7.3 与官方 CI 的差异

LiteX 官方 CI 当前使用 Ubuntu 22.04，并安装完整 LiteX 配置、Meson、多个 CPU GCC 工具链、Verilator、OSS CAD Suite、QEMU 以及相关系统库，随后使用 `pytest` 进行分片测试。本 Windows 最小环境没有复现该完整 CI 环境，因此全量结果仅用于建立移植问题清单。

官方 CI 配置：

`https://github.com/enjoy-digital/litex/blob/master/.github/workflows/ci.yml`

## 8. 基线结论

当前 Windows 参考环境满足 LiteX 核心移植的初始基线要求：

1. LiteX 与 Migen 安装成功；
2. Python 包依赖检查通过；
3. LiteX 与 Migen 导入成功；
4. 选定的 24 项核心测试全部通过；
5. 全量测试已执行并保存日志；
6. 已确认至少一项 Windows 路径差异，并初步完成异常分类。

因此，当前状态应记录为：

> LiteX 核心安装、导入及选定核心功能测试已通过；全量测试存在 Python 版本差异、Windows 平台行为、可选依赖和外部工具链缺失导致的失败，需按类别进一步分析，但不阻塞进入鸿蒙 PC 环境验证阶段。

## 9. 鸿蒙 PC 对比要求

鸿蒙 PC 端应记录同样的信息，并优先完成以下命令：

```text
python3 --version
python3 -m pip --version
git --version
python3 -m pip check
python3 -c "import litex, migen; print('LiteX and Migen import OK')"
```

随后运行第 6 节的 24 项核心测试，并从以下方面与本基线对比：

- 安装是否成功；
- 模块是否可导入；
- 24 项核心测试通过数量；
- 路径分隔符和临时目录行为；
- 默认字符编码；
- 文件权限和文件清理行为；
- `subprocess` 与外部命令调用行为。

## 10. 本地生成文件

测试过程中生成了以下本地文件：

- `.venv/`；
- `i2c.vcd`；
- `sim.vcd`；
- `test-windows-full.log`。

这些文件用于本地环境和测试分析，不应直接提交到项目仓库。提交时仅提交本基线文档及后续经过筛选的测试摘要或压缩日志附件。
