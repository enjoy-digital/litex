---
name: 第一周-核心兼容性
about: 分析并修复 LiteX 核心在鸿蒙 PC 上的兼容问题
title: "[W1][Core] 分析 LiteX 核心兼容性并提交最小修复"
labels: "porting,compatibility"
assignees: ""
---

## 目标

定位路径、编码、进程和临时文件等平台边界，提交范围明确且可回归验证的修复。

## 任务

- [ ] 审计核心代码中的平台判断和外部命令调用。
- [ ] 在鸿蒙 PC 复现首个核心失败并保存完整 traceback。
- [ ] 与 Windows 基线对比，确认问题归属。
- [ ] 编写最小修复，避免改动无关算法。
- [ ] 为修复补充回归测试或最小复现脚本。
- [ ] 在 `feature/core-compatibility` 上提交 PR。

## 验收证据

- 问题根因说明
- 修复前后日志
- 新增或通过的回归测试
- 面向 `port/harmonyos-pc` 的 PR 链接
