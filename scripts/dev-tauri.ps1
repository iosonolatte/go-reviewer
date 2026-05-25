# 启动 Tauri dev (Windows MSVC 环境)
# 自动加载 VS Build Tools 的 vcvars64 环境, 然后跑 tauri dev

$ErrorActionPreference = "Stop"

# 1) 定位 vcvars64.bat
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
    throw "vswhere.exe not found. Please install Visual Studio Build Tools first."
}
$vsInstallPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsInstallPath) {
    throw "Visual C++ Tools workload not found. Please install 'Desktop development with C++' workload."
}
$vcvars = Join-Path $vsInstallPath "VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $vcvars)) {
    throw "vcvars64.bat not found at $vcvars"
}

Write-Host "Loading MSVC environment from: $vcvars" -ForegroundColor Cyan

# 2) 通过临时批处理捕获 vcvars64 设置后的环境变量
$tmpBat = [System.IO.Path]::GetTempFileName() + ".bat"
$tmpEnv = [System.IO.Path]::GetTempFileName() + ".env"
try {
    Set-Content -Path $tmpBat -Value "@echo off`r`ncall `"$vcvars`" >nul`r`nset > `"$tmpEnv`""
    & $env:ComSpec /c $tmpBat | Out-Null
    if (-not (Test-Path $tmpEnv)) {
        throw "Failed to capture vcvars environment"
    }
    Get-Content $tmpEnv | ForEach-Object {
        $idx = $_.IndexOf('=')
        if ($idx -gt 0) {
            $name = $_.Substring(0, $idx)
            $val = $_.Substring($idx + 1)
            [Environment]::SetEnvironmentVariable($name, $val, "Process")
        }
    }
} finally {
    Remove-Item $tmpBat, $tmpEnv -ErrorAction SilentlyContinue
}

# 3) 把 cargo 加到 PATH
$cargoBin = "$env:USERPROFILE\.cargo\bin"
if (Test-Path $cargoBin) {
    $env:Path = "$cargoBin;$env:Path"
}

# 4) 校验
$linkExe = Get-Command link.exe -ErrorAction SilentlyContinue
$cargoExe = Get-Command cargo -ErrorAction SilentlyContinue
Write-Host "  link.exe: $($linkExe.Source)" -ForegroundColor Green
Write-Host "  cargo:    $($cargoExe.Source)" -ForegroundColor Green
Write-Host ""

# 5) 启动 tauri dev
Write-Host "Starting Tauri dev..." -ForegroundColor Cyan
& npx tauri dev
