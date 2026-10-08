# 2026-10-08 集成验收证据

受测 LiteX：`ed0c556c32c0f52a82730dfabd40aea08a192a19`；Migen：`4c2ae8dfeea37f235b52acb8166f12acaaae4f7c`。Windows Python 3.12.10，原生 HarmonyBrew Python 3.12.14。

- [summary.json](summary.json)：两端 5/5 必达、24/24 核心、6/6 补充，以及真实未执行项。
- [environment.json](environment.json)、[clean-install.json](clean-install.json)：全新在线安装的完整预检和来源；安装后包版本、隔离路径见完整包。
- [comparison.json](comparison.json)、[comment-diff-review.json](comment-diff-review.json)：8 个文件中 7 个按原规则一致，仅 Verilog 层级注释连接字符不同，保留 `DIFFERENT`。
- [repeat-comparison.json](repeat-comparison.json)、[supplement.json](supplement.json)：鸿蒙中文空格路径重复生成、CLI、异常时钟参数和清理保护。
- [blockers.md](blockers.md)：仿真扩展条件及团队待确认事项。
- [full-evidence.zip](full-evidence.zip)、[full-evidence.sha256](full-evidence.sha256)：原始两端日志、生成文件、两张原生截图、固定约束与本次实际执行器。解压后可用 `sha256sum -c SHA256SUMS.txt` 逐文件核验；PowerShell 可用 `Get-FileHash -Algorithm SHA256` 核对包校验值。

所有本次正式鸿蒙检查来自同一全新在线安装环境 `qa-final-20261008-online-r2`。截图标记为保存结果展示，没有为截图重跑测试。完整包是证据包，不包含源码 bundle、wheel 或系统运行时；源码提交和传输哈希可追溯，复现步骤见[使用说明](../../harmonyos-pc.md)。本次只改文档/证据，受测源码提交与收尾文档提交分别记录。
