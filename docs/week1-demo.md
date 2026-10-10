# 集成版本演示与交接（2026-10-08）

本流程用于展示已完成的核心生成验收，约 5 分钟。安装复现的状态以 [移植报告](../PORTING_REPORT.md) 为准；固件编译和 Verilator 完整仿真尚未执行。

## 演示流程

| 时间 | 展示内容 | 可核对的证据 |
| --- | --- | --- |
| 0:00–0:40 | 原生 HiShell、Python 版本、固定 LiteX/Migen 提交；说明 MinimalSoC 为 CPU=None、1 MHz | 原始 `environment.json`、报告中的版本表 |
| 0:40–1:30 | 现场生成最小 SoC，打开 Verilog、CSR JSON 和头文件 | 下方生成命令与新的 `baseline-summary.json` |
| 1:30–2:30 | 展示已保存的必达验收和核心测试日志 | `acceptance-report.json`：5/5；`logs/portable-core-tests.log`：24/24 |
| 2:30–3:30 | 展示两端产物比较，解释唯一层级注释字符差异 | `docs/evidence/2026-10-08/comparison.json`，保留 `DIFFERENT` |
| 3:30–4:15 | 展示 PR 的 CI 结果，说明其运行平台为 Ubuntu | 受测提交 ed0c556c3 的四组 Checks；不能替代鸿蒙真机证据 |
| 4:15–5:00 | 展示安装复现状态、可选依赖限制及团队待确认项 | 移植报告与下方交接清单 |

鸿蒙现场生成命令（使用本次独立在线安装环境；每次创建新的演示输出目录）：

```sh
source ~/.zshrc
cd ~/projects/litex/qa-final-20261008-online-r2/litex
source .venv-litex/bin/activate
git rev-parse HEAD
python --version
DEMO_DIR="$HOME/projects/litex/demo-$(date +%Y%m%d-%H%M%S)"
if test -e "$DEMO_DIR"; then
    echo "输出目录已存在，请换一个目录后运行"
else
    PYTHONUTF8=1 python examples/minimal_soc_baseline.py --output-dir "$DEMO_DIR"
fi
```

预期 LiteX 提交为 `ed0c556c32c0f52a82730dfabd40aea08a192a19`、Python 为 3.12.14。现场命令是待执行的演示流程；已有验证日志不应标作现场新运行。截图应保留命令、版本和结束状态，避免只截取绿色结果。若不便现场运行，可展示原始日志并明确其日期。

本次独立环境中的第二次生成兼作流程演练，输出到 `results/重复生成 空格/`，保留生成日志与重复比较报告。截图只展示有日期标签的保存结果，不能标为重新执行整套测试。每次正式现场演示仍应使用上面的新输出目录。现有要求允许截图和日志；只有老师要求视频时再录制。

## 交给 1 号的材料

- [移植报告](../PORTING_REPORT.md)、[复现说明](harmonyos-pc.md) 和本演示流程。
- [本次证据目录](evidence/2026-10-08/)：摘要、比较明细、原生探测和阻塞记录。
- [完整证据包](evidence/2026-10-08/full-evidence.zip)与[包校验值](evidence/2026-10-08/full-evidence.sha256)：包含原始日志、产物、两张原生截图、约束和实际执行器，可从收尾 PR 下载。包内 `SHA256SUMS.txt` 用于逐文件核验；不包含源码 bundle/wheel 二进制，来源及传输哈希另存。
- 受测源码为 `ed0c556c3`；本次收尾 PR 只更新文档和证据，未修改运行代码。PR #1/#3/#4 已合并，不再列为待合并项。

## 仍需向 1 号取得的确认和物件

| 项目 | 请 1 号提供 | 作用 |
| --- | --- | --- |
| 比较口径 | 对 Windows Python 3.12.10 与鸿蒙 3.12.14 的书面确认，或要求统一的具体版本 | 避免把补丁版本差异默认为已获认可 |
| 注释差异 | 对 Verilog 层级注释 ASCII/Unicode 字符差异的交叉复核结论 | 机器比较仍为 `DIFFERENT`，是否接受由团队确认 |
| 成员复核 | 指定另一位成员，并提供复核记录或 PR 审阅 | 满足环境脚本、测试和文档需交叉验证的约定 |
| 最终集成 | 审核收尾 PR，确认最终提交并亲自完成空目录复现 | 四号对集成源码的实测不能代替一号个人复现或团队签收 |
| 演示与提交 | 老师要求的提交入口、截止时间、演示形式及真机安排 | 确定最终交付和录制方式 |
| 扩展范围 | 是否继续 LiteEth / Verilator / 固件工具链验证的优先级 | 当前缺 LiteEth，原生 PATH 未发现 Meson/Verilator；下一步先确认可用工具链及兼容生态版本 |

已取得的仓库权限、固定源码/Migen 提交、最小用例和验收入口无需再次索要。按分工约定，由 1 号最终审核和合并。
