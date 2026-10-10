# 2026-10-08 阻塞与交接

受测源码：`ed0c556c32c0f52a82730dfabd40aea08a192a19`，原生 HarmonyBrew Python 3.12.14 / aarch64。

## 完整仿真与固件工具链

核心入口的可选命令：`python -m litex.tools.litex_sim --help`。当前失败停在 `ModuleNotFoundError: No module named 'liteeth'`，尚未执行 Verilator。

原生环境中 Clang 15.0.4、Make 4.4.1、Ninja 1.13.2、CMake 4.4.3 的版本命令可运行；Meson、Verilator 和探测的三个 RISC-V GCC 名称未在 PATH 发现。探测器的“未安装”标签来自 PATH 查询，仅能支持此可见性结论，不能证明设备上绝无安装或平台不支持。未移植或构建这些工具。

责任/下一步：1 号确认本阶段按 Python 核心/导出范围交付；若纳入完整仿真，由 2 号先提供原生工具链、固定兼容生态提交，再由 4 号执行约定最小用例。当前 CI 动态获取生态源码，一次 CI 成功不保证未来任意版本组合。

BIOS 编译、真实串口收发、FPGA 综合/烧录均未验证。CLI 帮助与串口枚举不等于硬件通信通过。

## 仍须团队决定

- Python 3.12.10（Windows）与 3.12.14（鸿蒙）的比较口径；Windows 管理运行时没有可下载的 3.12.14 构建，本次保留原版本并明确差异。
- 生成 Verilog 的 ASCII/Unicode 层级注释例外是否接受；机器比较保持 `DIFFERENT`。
- 1 号个人空目录复现、另一成员对收尾 PR 的复核、最终合并及提交入口。4 号实测不能代签这些事项。

完整命令、原始日志和版本见 [full-evidence.zip](full-evidence.zip)；结果摘要见 [summary.json](summary.json)。
