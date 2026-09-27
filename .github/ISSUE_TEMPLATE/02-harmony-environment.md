---
name: 第一周-鸿蒙环境与依赖
about: 鸿蒙 PC 的 Python、pip、依赖和工具链探测
title: "[W1][Environment] 完成鸿蒙 PC 环境与依赖探测"
labels: "porting,environment"
assignees: ""
---

## 目标

确认鸿蒙 PC 原生环境是否满足 LiteX 核心运行条件，并形成可复现的安装记录。

## 任务

- [ ] 记录系统版本、CPU 架构、Shell 和权限范围。
- [ ] 记录 Python、pip、Git 的来源与版本。
- [ ] 安装 LiteX/Migen 依赖并运行 `python -m pip check`。
- [ ] 执行 LiteX/Migen 导入和 CLI `--help` 检查。
- [ ] 建立依赖矩阵，区分核心必需项与可选工具链。
- [ ] 将完整命令、输出和阻塞原因提交到 `feature/harmony-environment`。

## 验收证据

- 环境探测日志和版本清单
- 安装步骤文档
- 失败项的最小复现与完整错误信息
- 面向 `port/harmonyos-pc` 的 PR 链接
