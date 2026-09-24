# =============================================================================
# LiteX @ HarmonyOS PC —— 环境与依赖安装脚本（2 号交付物，Windows 参考环境用）
# =============================================================================
# 用法（在 LiteX 仓库根目录）：
#   powershell -ExecutionPolicy Bypass -File scripts\setup_harmonyos.ps1
# 与 setup_harmonyos.sh 的手动最小安装模式流程一致，用于建立可对比的参考环境。
# =============================================================================

$ErrorActionPreference = "Stop"
$RepoRoot  = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$VenvDir   = if ($env:LITEX_VENV_DIR) { $env:LITEX_VENV_DIR } else { Join-Path $RepoRoot ".venv-litex" }
$MigenUrl  = if ($env:LITEX_MIGEN_URL) { $env:LITEX_MIGEN_URL } else { "https://git.m-labs.hk/M-Labs/migen.git" }
$MigenSha1 = "4c2ae8dfeea37f235b52acb8166f12acaaae4f7c"   # litex_repos.py 基线
$MigenDir  = Join-Path (Split-Path -Parent $RepoRoot) "migen"

function Log($m) { Write-Host "[setup] $m" }
function Die($m) { Write-Host "[setup][FATAL] $m" -ForegroundColor Red; exit 1 }

# --- 1. 前置检查：优先 python，回退 py -3 启动器 ---------------------------------
function Get-ExePath($cmd, $args) {
    try {
        $out = & $cmd @args -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return $out.Trim() }
    } catch { }
    return $null
}
$PyExe = Get-ExePath "python" @()
if (-not $PyExe) { $PyExe = Get-ExePath "py" @("-3") }
if (-not $PyExe) { Die "未找到原生 Python：C 类阻塞，请提交阻塞报告（勿用虚拟机/容器/WSL 替代验证目标）。" }
Log "使用解释器: $PyExe"

& $PyExe -m pip --version | Out-Null
if ($LASTEXITCODE -ne 0) { Die "pip 不可用（python -m pip --version 失败）：提交阻塞报告。" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "git 不可用。" }

# --- 2. 环境检测 ----------------------------------------------------------------
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "logs") | Out-Null
& $PyExe (Join-Path $RepoRoot "scripts\check_environment.py") --full `
    --json (Join-Path $RepoRoot ("logs\check-environment-{0}.json" -f (Get-Date -Format "yyyyMMdd-HHmmss")))

# --- 3. venv ---------------------------------------------------------------------
if (-not (Test-Path $VenvDir)) {
    Log "创建虚拟环境: $VenvDir"
    & $PyExe -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Die "venv 创建失败：提交阻塞报告并附报错。" }
}
$VPy = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VPy)) { Die "venv 内解释器缺失: $VPy" }

# --- 4. 依赖 -----------------------------------------------------------------------
Log "安装构建/运行依赖 (requirements-harmonyos.txt)"
& $VPy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Die "pip 自升级失败：检查 pypi.org / files.pythonhosted.org 连通性。" }
& $VPy -m pip install -r (Join-Path $RepoRoot "requirements-harmonyos.txt")
if ($LASTEXITCODE -ne 0) { Die "PyPI 依赖安装失败：附完整报错提交。" }

if (-not (Test-Path (Join-Path $MigenDir ".git"))) {
    Log "克隆 Migen: $MigenUrl"
    & git clone --recursive $MigenUrl $MigenDir
    if ($LASTEXITCODE -ne 0) { Die "Migen 克隆失败：检查 git.m-labs.hk 连通性。" }
}
Push-Location $MigenDir
& git checkout $MigenSha1
if ($LASTEXITCODE -ne 0) { Log "警告：固定 SHA1 checkout 失败，请先 git fetch origin 后人工核对版本。" }
Pop-Location
& $VPy -m pip install --no-build-isolation $MigenDir
if ($LASTEXITCODE -ne 0) { Die "Migen 安装失败：先确认 setuptools/wheel 已就绪，再附完整报错提交。" }

Log "安装 LiteX（可编辑模式）"
& $VPy -m pip install --no-build-isolation -e $RepoRoot
if ($LASTEXITCODE -ne 0) { Die "LiteX 安装失败：附完整报错与上方检测报告提交。" }

# --- 5. 验证 ------------------------------------------------------------------------
& $VPy -c "import migen, migen.fhdl, litex, litex.soc, litex.build; print('import OK: migen + litex')"
if ($LASTEXITCODE -ne 0) { Die "导入验证失败：转 3 号定位（重点看导入链中的平台相关代码）。" }
foreach ($tool in @("litex_sim", "litex_soc_gen", "litex_periph_gen")) {
    $exe = Join-Path $VenvDir "Scripts\$tool.exe"
    if (Test-Path $exe) {
        & $exe --help | Out-Null
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq $null) {
            Log "  $tool --help : OK"
        } else {
            Log "  $tool --help : 退出码 $LASTEXITCODE（记录完整输出，转 3 号定位）"
        }
    } else {
        Log "  $tool : 未找到可执行文件（转 3 号定位）"
    }
}
Log "完成。激活: . `"$VenvDir\Scripts\Activate.ps1`" ；复跑 check_environment.py 确认 Python 依赖各项转为 OK。"
