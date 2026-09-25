# 鸿蒙 PC 环境搭建说明（2 号交付物）

对应分工文档 2 号任务：调查鸿蒙 PC 原生 Python 与构建环境，验证 LiteX/Migen 及工具链依赖，
产出环境检测脚本、依赖清单、安装脚本、依赖矩阵与本文档。所有结论以**真机实测证据**为准。

## 0. 安全边界（分工文档原文约束）

- 验证环境必须是**鸿蒙 PC 原生环境**：原生 CPython、原生终端、原生文件系统。
- **不得**改用虚拟机、容器、WSL 或任何兼容层来达成验证结论（分工文档 2 号第一周任务与第九节）。
- 原生 CPython 或 pip 不可用 → **立即**按第 4 节模板提交阻塞报告，等待组长与平台方确认，不自行调整目标。

## 1. 交付物一览

| 文件 | 说明 |
|---|---|
| `scripts/check_environment.py` | 环境检测脚本（纯标准库、单文件、可整体拷走） |
| `requirements-harmonyos.txt` | 核心 pip 依赖清单（Migen 不在其中，见矩阵 §2） |
| `scripts/setup_harmonyos.sh` | POSIX/鸿蒙真机安装脚本（默认手动最小安装，可选上游 litex_setup 模式） |
| `scripts/setup_harmonyos.ps1` | Windows 参考环境等价脚本（保证两端流程一致、可对比） |
| `docs/dependency-matrix.md` | 依赖兼容矩阵（分级结论 + 真机回填列） |
| `logs/` | 检测与安装日志归档目录（**仅真机日志为交付物**；参考环境本地输出不入库，见 §6） |

## 2. 真机执行手册（建议第 3–4 天，一次性验证命令已按分工要求收敛为三条）

前置：将本仓库（分支 `port/harmonyos-pc`，基线 commit 见矩阵页首）以任意可审计方式放到真机，
例如参考环境 `git bundle` 打包后经设备传输通道导入（传输通道本身也是待记录的环境特征）。

```sh
# ① 快速检测（约 5 秒，无网络访问）：确认解释器存在、拿到全量环境特征
python3 scripts/check_environment.py 2>&1 | tee logs/check-harmonyos-fast.txt

# ② 全量检测（含网络/Git 远端/venv 实测/工具版本）：形成依赖矩阵与分级依据
python3 scripts/check_environment.py --full 2>&1 | tee logs/check-harmonyos-full.txt

# ③ 核心安装（自动先复跑检测，再 venv → PyPI 依赖 → Migen 源码 → LiteX → 导入验证）
sh scripts/setup_harmonyos.sh 2>&1 | tee logs/setup-harmonyos.txt
```

要求：三条命令的完整输出（含终端类型、提示符回显）都保留为日志；任何一步失败不要清屏重跑掩盖，
保留原始终端记录并按第 4 节整理。

若希望走完整上游流程（standard 配置，需 github.com 可达）：`sh scripts/setup_harmonyos.sh --with-litex-setup`。

## 3. 判读规则（对齐分工文档第 5 天三类结论）

| 观察点（报告行） | 结果 | 分类 |
|---|---|---|
| `Python/解释器版本`、`Python/pip 可用性` 任一 FAIL | 原生 Python/pip 不可用 | **C 类**：停止，提交阻塞报告 |
| ①②③ 全 OK 且 setup 第 5 步 `import OK`，网络/venv/Git 均 OK | 核心可用 | **A 类**：继续代码生成与测试 |
| 核心 OK，但外部工具（verilator/riscv/meson/ninja/编译器）缺失或串口枚举异常 | 外部工具链不可用 | **B 类**：核心继续，仿真降为扩展验收，工具链缺口记矩阵 ④ |

补充判读：
- `setuptools` 安装过程出现 "Building wheel for … "（矩阵 §3 风险）→ 记录是否成功；失败按 C 类评估或走矩阵 §7 离线 wheel 兜底。
- `符号链接` FAIL/WARN 不阻塞（核心安装不使用；仅 libxil 扩展路径）。
- `litex_sim --help` 失败 ≠ Verilator 阻塞：前者是 Python 导入层，后者是外部工具层，报告中分属不同行，勿混淆层级。

## 4. 阻塞报告模板（按分工文档第六节：必须附命令、完整日志、环境版本、复现步骤）

```markdown
# 阻塞报告：<一句话标题，如 "鸿蒙PC原生pip不可用（C类）">
- 提交人 / 日期 / 严重级别（A-B-C / 核心必达或扩展）
- 设备信息（来自 check_environment.py 报告"系统"节，整段粘贴）：
  - 系统版本与架构：
  - 终端类型（TERM/SHELL/TERM_PROGRAM/isatty）：
- 环境版本（来自报告 Python/Git 节）：
- 受阻步骤（①/②/③ 哪条命令、脚本哪个阶段）：
- 完整命令与完整输出（终端原文，勿摘录）：
  ```text
  ```
- 复现步骤（1./2./3.，含工作目录与环境变量）：
- 已尝试的排除手段与结果：
- 影响的验收条款（核心必达第 N 条 / 扩展第 N 条）：
- 需要组长协调的事项（真机预约、平台方运行时支持、镜像源等）：
```

## 5. 协作接口（分工文档第六节）

- **提供→3 号**：环境特征全表（编码/路径分隔符/大小写/可执行位/POSIX 模块/子进程行为），安装日志；
  3 号定位 `subprocess`、路径、串口类问题时优先共享同一份 `--full` 报告，避免重复占用真机。
- **提供→4 号**：`logs/` 全部文件、已固定版本清单（矩阵 §8 与真机回填后快照）、venv 路径与激活命令。
- **接收←1 号**：基线 commit 变更时同步（影响矩阵页首与 setup 脚本内 Migen SHA1 常量，两处需手改一致）。
- 与 4 号共同在全新环境复测安装：清空 venv 与 `../migen`，重跑第 2 节命令，结果应可复现。

## 6. 参考环境复现（仅用于调试，结果不入库）

按组内决定（2026-09-25）：**Windows 探测报告不作为交付物**——它不代表鸿蒙环境，
验收证据一律来自真机三条命令的输出。以下流程仅用于本机验证脚本本身可运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_harmonyos.ps1
```

- 参考环境本机输出留在 `logs/` 的探测文件不随 PR 提交（已在 `.gitignore` 排除），可随时删除重跑。
- 注意：本机 `python` 命令可能是 WindowsApps 存根，脚本会自动回退 `py -3` 并在日志首行记录实际解释器路径；
  真机报告同样首行输出 `sys.executable`，两端对比时以该行为准。
- Linux 参考环境直接复用 `.sh` 脚本即可，无参数差异。
