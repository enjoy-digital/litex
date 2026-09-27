---
name: 第一周-测试与文档
about: 鸿蒙 PC 测试执行、差异分类和移植报告维护
title: "[W1][QA] 完成鸿蒙 PC 测试与移植文档"
labels: "porting,testing,documentation"
assignees: ""
---

## 目标

建立鸿蒙 PC 测试证据，区分核心问题、可选依赖问题和外部工具链问题。

## 任务

- [ ] 运行 24 项便携核心测试并保存日志。
- [ ] 运行最小 SoC 导出和验收脚本。
- [ ] 对照 Windows 基线分类失败项。
- [ ] 记录生成文件、退出码、耗时和环境信息。
- [ ] 更新安装、测试、已知限制和复现步骤。
- [ ] 在 `feature/tests-docs` 上提交 PR。

## 验收证据

- `acceptance-report.json` 与步骤日志
- Windows/鸿蒙差异表
- 已知限制和后续测试清单
- 面向 `port/harmonyos-pc` 的 PR 链接
