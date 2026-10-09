#!/bin/sh
# =============================================================================
# LiteX @ HarmonyOS PC —— 环境与依赖安装脚本（2 号交付物，POSIX / 鸿蒙真机用）
# =============================================================================
# 用法（在 LiteX 仓库根目录或其内任意位置执行）：
#   sh scripts/setup_harmonyos.sh                  # 手动最小安装（默认，路径最稳）
#   sh scripts/setup_harmonyos.sh --with-litex-setup
#       # 走上游 ./litex_setup.py --init --install --config=minimal
#       # 需要 raw.githubusercontent.com + github.com 可达
#
# 可选环境变量：
#   LITEX_VENV_DIR   虚拟环境目录（默认 <仓库根>/.venv-litex）
#   LITEX_MIGEN_URL  Migen 仓库（默认 https://git.m-labs.hk/M-Labs/migen.git）
#   LITEX_PIP_INDEX  pip 镜像（默认为空 = 官方 PyPI）
#
# 前置：鸿蒙 PC 原生 python3(>=3.7) + pip + git 可用。
# 若任一前置不可用，本脚本会中止——请按 docs/harmonyos-environment-setup.md
# 的阻塞报告模板提交证据，不要改用虚拟机/容器/兼容层（分工文档 2 号任务要求）。
# =============================================================================
set -eu

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
VENV_DIR="${LITEX_VENV_DIR:-${REPO_ROOT}/.venv-litex}"
MIGEN_URL="${LITEX_MIGEN_URL:-https://git.m-labs.hk/M-Labs/migen.git}"
# 与基线 litex_repos.py:23-28 的固定 SHA1 一致。
MIGEN_SHA1="4c2ae8dfeea37f235b52acb8166f12acaaae4f7c"
MIGEN_DIR="$(cd "${REPO_ROOT}/.." && pwd)/migen"
MODE="manual"
[ "${1:-}" = "--with-litex-setup" ] && MODE="litex_setup"

log()  { echo "[setup] $*"; }
die()  { echo "[setup][FATAL] $*" >&2; exit 1; }

# --- 1. 前置能力检查（核心必达项） ---------------------------------------------
command -v python3 >/dev/null 2>&1 || die "未找到原生 python3：属 C 类阻塞，停止安装并提交阻塞报告（勿用虚拟机/容器替代）。"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)' \
    || die "Python 版本低于 3.7（setup.py python_requires ~=3.7）。"
python3 -m pip --version >/dev/null 2>&1 \
    || die "pip 不可用（python3 -m pip --version 失败）：提交阻塞报告，附完整输出。"
command -v git >/dev/null 2>&1 || die "git 不可用：--init 与 Migen 源码安装均依赖它。"

log "运行环境检测（完整报告见 logs/，供依赖矩阵与阻塞报告引用）..."
mkdir -p "${REPO_ROOT}/logs"
if ! python3 "${SCRIPT_DIR}/check_environment.py" --full \
        --json "${REPO_ROOT}/logs/check-environment-$(date +%Y%m%d-%H%M%S).json"; then
    log "环境检测存在 FAIL 项（上方报告已列出）。核心必达项受阻时请停止并提交阻塞报告；"
    log "仅扩展项（工具链/串口）受阻可按 B 类结论继续核心安装。"
fi

# --- 2. 虚拟环境 ---------------------------------------------------------------
if [ "${MODE}" = "litex_setup" ]; then
    log "模式：litex_setup.py minimal（上游安装流程）"
    cd "${REPO_ROOT}"
    exec python3 ./litex_setup.py --init --install --config=minimal
fi

log "模式：手动最小安装（venv + PyPI 依赖 + Migen 源码 + 本仓库可编辑安装）"
[ -d "${VENV_DIR}" ] || {
    python3 -m venv "${VENV_DIR}" || die "venv 创建失败：核心必达项，提交阻塞报告并附报错。"
}
VENV_PY="${VENV_DIR}/bin/python"
[ -x "${VENV_PY}" ] || VENV_PY="${VENV_DIR}/Scripts/python.exe"
PIP_INDEX_OPT=""
[ -n "${LITEX_PIP_INDEX:-}" ] && PIP_INDEX_OPT="--index-url ${LITEX_PIP_INDEX}"

log "升级 pip 并安装构建/运行依赖（requirements-harmonyos.txt）..."
"${VENV_PY}" -m pip install --upgrade ${PIP_INDEX_OPT} pip
"${VENV_PY}" -m pip install ${PIP_INDEX_OPT} -r "${REPO_ROOT}/requirements-harmonyos.txt" \
    || die "PyPI 依赖安装失败：检查 pypi.org / files.pythonhosted.org 连通性（见检测报告），或设置 LITEX_PIP_INDEX 镜像后重试。"

# --- 3. Migen（主路径：源码 + 固定 SHA1，可审计；备用：pip install migen==0.9.2，见矩阵 §2/§7） ---
log "获取 Migen 源码（${MIGEN_URL} @ ${MIGEN_SHA1}）..."
if [ ! -d "${MIGEN_DIR}/.git" ]; then
    git clone --recursive "${MIGEN_URL}" "${MIGEN_DIR}" \
        || die "Migen 克隆失败：检查 git.m-labs.hk 连通性后重试；勿改用来源不明的镜像。"
fi
( cd "${MIGEN_DIR}" && git checkout "${MIGEN_SHA1}" ) \
    || log "警告：固定 SHA1 checkout 失败（对象不存在时先 git fetch origin），请人工核对版本。"
"${VENV_PY}" -m pip install --no-build-isolation "${MIGEN_DIR}" \
    || die "Migen 安装失败：先确认 setuptools/wheel 已就绪，再附完整报错提交问题。"

# --- 4. LiteX 本体（本仓库，可编辑安装） ------------------------------------------
log "安装 LiteX（可编辑模式，源码即 ${REPO_ROOT}）..."
"${VENV_PY}" -m pip install --no-build-isolation -e "${REPO_ROOT}" \
    || die "LiteX 安装失败：将完整报错与上方环境检测报告一并提交。"

# --- 5. 导入与命令行验证 ----------------------------------------------------------
log "验证导入（对应验收核心标准 2）..."
"${VENV_PY}" -c 'import migen, migen.fhdl, litex, litex.soc, litex.build; print("import OK: migen + litex")' \
    || die "导入验证失败：转 3 号定位（重点看 litex 导入链中的平台相关代码）。"
VENV_BIN="$(dirname "${VENV_PY}")"
log "验证命令行工具（对应验收核心标准 3，失败不阻塞安装，记录到问题清单）..."
for tool in litex_sim litex_soc_gen litex_periph_gen; do
    if "${VENV_BIN}/${tool}" --help >/dev/null 2>&1; then
        log "  ${tool} --help : OK"
    else
        log "  ${tool} --help : 失败（记录完整输出，转 3 号定位）"
    fi
done

log "完成。后续步骤："
log "  1) source ${VENV_DIR}/bin/activate        # Windows 为 ${VENV_DIR}\\Scripts\\activate"
log "  2) python3 scripts/check_environment.py   # 依赖安装后复跑，Python 依赖各项应变为 OK"
log "  3) 向 1 号同步：依赖矩阵实测列 + 本日志；向 3/4 号同步可用的 venv 路径与激活命令"
