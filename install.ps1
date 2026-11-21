# 微風語音輸入 安裝程式
# 用法：在此資料夾按右鍵「在終端機中開啟」，執行：
#   powershell -ExecutionPolicy Bypass -File .\install.ps1            # 安裝＋建立桌面捷徑
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Startup   # 另外設定開機自動啟動
param([switch]$Startup)
$ErrorActionPreference = 'Stop'
$App = $PSScriptRoot
Set-Location $App

Write-Host "== 微風語音輸入 安裝 ==" -ForegroundColor Cyan

# 1. 檢查 NVIDIA 顯示卡
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    Write-Warning "找不到 NVIDIA 顯示卡驅動（nvidia-smi）。本工具需要 NVIDIA 顯示卡（建議 8GB 以上顯示記憶體）。"
    exit 1
}
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# 2. 找 Python 3.10～3.12
$py = $null
foreach ($v in '3.12', '3.11', '3.10') {
    try { & py "-$v" -c "import sys" 2>$null; if ($LASTEXITCODE -eq 0) { $py = @('py', "-$v"); break } } catch {}
}
if (-not $py) {
    Write-Warning "找不到 Python 3.10～3.12。請先到 https://www.python.org/downloads/ 安裝 Python 3.12。"
    exit 1
}
Write-Host "使用 Python：$($py -join ' ')"

# 3. 建立虛擬環境並安裝套件
if (-not (Test-Path "$App\.venv\Scripts\python.exe")) {
    & $py[0] $py[1] -m venv "$App\.venv"
}
$vpy = "$App\.venv\Scripts\python.exe"
& $vpy -m pip install --upgrade pip
& $vpy -m pip install torch==2.11.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu128
& $vpy -m pip install -r "$App\requirements.txt"
& $vpy -c "import torch; assert torch.cuda.is_available(), 'CUDA 無法使用'; print('GPU OK:', torch.cuda.get_device_name(0))"

# 4. 建立捷徑
$sh = New-Object -ComObject WScript.Shell
function New-Shortcut($path, $hidden) {
    $s = $sh.CreateShortcut($path)
    $s.TargetPath = "$App\.venv\Scripts\pythonw.exe"
    $s.Arguments = "-W ignore `"$App\src\voice_app.py`"" + $(if ($hidden) { ' --hidden' } else { '' })
    $s.WorkingDirectory = $App
    $s.IconLocation = "$App\assets\icon.ico"
    $s.Description = '微風語音輸入'
    $s.Save()
}
New-Shortcut "$([Environment]::GetFolderPath('Desktop'))\微風語音輸入.lnk" $false
Write-Host "已建立桌面捷徑「微風語音輸入」"
if ($Startup) {
    New-Shortcut "$([Environment]::GetFolderPath('Startup'))\微風語音輸入.lnk" $true
    Write-Host "已設定開機自動啟動（只出現在工作列）"
}

Write-Host "`n安裝完成！雙擊桌面「微風語音輸入」開始使用。第一次啟動會自動下載辨識模型（約 3GB）。" -ForegroundColor Green
