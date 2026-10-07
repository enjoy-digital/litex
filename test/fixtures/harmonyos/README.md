# 最小 SoC 的实测参考数据

[minimal-soc-csr.json](minimal-soc-csr.json) 原样取自 2026-09-28 的 Windows 参考生成结果，不是手工编造的预期文件。

- LiteX：`6bd66c63f77e3c32452e8b5f7dbfb50df45ad501`。
- Migen：`4c2ae8dfeea37f235b52acb8166f12acaaae4f7c`。
- 用例：`examples/minimal_soc_baseline.py`，时钟 1 MHz，CPU=None，包含控制器、标识存储区及 timer0。
- 固定 CSR 基址：ctrl=0、identifier_mem=2048、timer0=4096；CSR 总区域大小 65536，数据宽度 32。
- 原始 SHA-256：`71a922c4350c79dcad2aa4a1b23e6fad9a1d893ed8a13f301e96dbfafe16cab0`。
- 上述哈希对应原始 Windows 产物；Git 检出可能转换换行，仓库副本应按 JSON 结构和值比较。
- 鸿蒙实测 CSR JSON 与该文件在对象结构和值上相同，原始字节因换行不同而不同。

完整产物的两端哈希及差异见 [比较报告](../../../docs/evidence/2026-09-28/comparison.json)。本文件只提供可审阅的 CSR 摘要，不足以代替完整 HDL/头文件比较；`scripts/compare_baseline.py` 接收两个完整的生成目录。团队基线或配置改变时应重新生成并说明来源，不能静默更新以掩盖失败。
