# 三号第一周证据（2026-09-30）

这是 macOS 补充核查记录。鸿蒙原生证据来源及第一周逐项结论见 [核心兼容性说明](../../../core-compatibility.md)。
本目录含成功与失败记录，不表示全量 CI 或组员审核已通过。

## 文件与完整性

- `summary.json`：提交、计数、原始 ZIP 哈希及待处理项。
- `acceptance/`：一号验收脚本原始 JSON、控制台日志副本和全部生成文件。
- `example/`：鸿蒙示例入口第一次运行的生成文件及摘要。
- `review/`：27 项首次检查、25 项复测、宿主探测、4 个帮助命令、中文空格路径生成、包版本、路径别名诊断及 CI 失败摘录。
- `source/`：受测文件 SHA-256、Migen 提交、相对 75c85fd 的测试修正；core-diff-from-baseline.txt 为空，表示 litex/ 与基线没有差异。
- `host_probe.py`：与本次执行脚本相同的便捷入口；不会打开串口。
- `manifest.json`：每个原始文件在 ZIP 中的路径/哈希及公开副本路径/哈希。

原始 ZIP 已保存到三号电脑**主仓库**的 `build/core-compatibility-2026-09-30.zip`，不再只依赖临时目录。
ZIP 按 .gitignore 留在本地，包含完整生成文件、原始日志和 raw-sha256.json。
公开副本可直接供仓库审阅；ZIP 中有本机绝对路径，交接时按需提供。
ZIP 的 SHA-256 见 summary.json，解压后可逐项对照 raw-sha256.json。

公开副本只替换路径，不删失败行或改计数：
工作树→`<WORKTREE>`，主仓库→`<PRIMARY_CHECKOUT>`，用户主目录→`<USER_HOME>`，
系统临时目录的 /var 别名→`<TMPDIR_ALIAS>`，/private/var 实际路径→`<REAL_TMPDIR>`。
保留两种临时路径的区别以解释测试误报；.log 后缀改为 .log.txt 以纳入版本管理。
baseline-summary.json 中产物哈希指向 **ZIP 的原始字节**，公开文件应按 manifest.json 的 public_sha256 核对。
CI 两个文件明确为 GitHub 日志摘录，非完整运行日志。

## 源码与环境复现

历史验收对应 LiteX `6bd66c63f77e3c32452e8b5f7dbfb50df45ad501`。
补充检查对应 `75c85fd66618332a637f0382e9c100b0e3755437` 加 source/test-path-fix.patch。
当前 PR 已包含该修正；不要重复应用。Migen 固定为 `4c2ae8dfeea37f235b52acb8166f12acaaae4f7c`。
review/packages.txt 保存实际包版本；其中可编辑 LiteX 路径已脱敏，不能直接把该文件当安装命令执行。

在 CPython 3.11.3 的独立 venv 安装固定 Migen，再从本仓库执行 `python -m pip install -e .`。
鸿蒙使用二号安装流程和已验证的 HarmonyBrew Python；不要用本机 Python 版本替代真机版本。
补充命令均从本仓库根目录执行，并设置 `PYTHONUTF8=1`、`PYTHONDONTWRITEBYTECODE=1`。

```sh
export PYTHONUTF8=1
export PYTHONDONTWRITEBYTECODE=1
python scripts/run_acceptance.py --output-dir build/core-week1-review/acceptance
python examples/harmonyos_minimal_soc.py --output-dir 'build/core-week1-review/中文 空格/minimal-soc' --clean
python docs/evidence/core-compatibility/2026-09-30/host_probe.py
python -m unittest -v \
  test.build.test_generic_platform_toolchain.TestGenericToolchain \
  test.soc.test_builder.TestBuilderPaths \
  test.soc.test_builder.TestBuilderGeneratedFiles.test_generate_includes_without_bios_writes_runtime_headers_only \
  test.soc.test_builder.TestBuilderGeneratedFiles.test_generate_csr_map_writes_default_csv_and_json_exports \
  test.soc.test_builder.TestBuilderGeneratedFiles.test_variables_contents_remaps_replay_support_paths \
  test.hdl.test_migen_compat
python -m litex.tools.litex_client --help
python -m litex.tools.litex_term --help
python -m litex.tools.litex_soc_gen --help
python -m litex.tools.litex_periph_gen --help
```

上述 25 项选择为 17 项 GenericToolchain、3 项 BuilderPaths、3 项无需 BIOS 的生成文件测试、2 项 Migen 兼容测试。
第一次命令使用整个 TestBuilderGeneratedFiles 类，因此共有 27 项：24 通过、路径断言 1 失败、BIOS 包缺失 2 错误。
排除的是 test_generate_includes_with_bios_writes_linker_files 和 test_variables_contents_escapes_makefile_paths_and_validates_console。
这两个错误仍未在本机修复，不属于本周无 CPU 的生成范围。

宿主探测的权限细项要求非 root POSIX 进程：若 detail.exercised=false，该项没有实际执行，不能声称权限验证通过。
枚举为空也不证明串口通信可用；本次 macOS 返回 3 项且未打开端口。
四号鸿蒙专项回填及另一名组员的交叉验证仍待执行。
