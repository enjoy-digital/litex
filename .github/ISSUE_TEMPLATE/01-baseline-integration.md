---
name: 第一周-基线与集成
about: 组长负责的基线、流程梳理、最小 SoC 与集成验收
title: "[W1][Lead] 完成 LiteX 移植基线与集成验收"
labels: "porting,baseline"
assignees: ""
---

## 目标

建立可复现的 LiteX 核心移植基线，并负责向 `port/harmonyos-pc` 集成。

## 任务

- [ ] 固定上游提交、Python 版本和依赖版本。
- [ ] 记录 Windows 对照环境和测试结果。
- [ ] 梳理 LiteX 核心执行流程与平台边界。
- [ ] 运行 `examples/minimal_soc_baseline.py`，确认生成 Verilog、CSR 和头文件。
- [ ] 运行 `scripts/run_acceptance.py`，保存 JSON 报告和日志。
- [ ] 汇总其他成员 PR，并检查目标分支均为 `port/harmonyos-pc`。

## 验收证据

- `PORT_BASELINE.md`
- `docs/litex-core-flow.md`
- `build/acceptance/acceptance-report.json`
- 合并到 `port/harmonyos-pc` 的 PR 链接
