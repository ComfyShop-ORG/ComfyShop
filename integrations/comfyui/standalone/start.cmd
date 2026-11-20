@echo off
rem Windows x64 worker launcher. Run from the extracted folder.
setlocal
chcp 65001 >nul
pushd "%~dp0" || exit /b 1
rem worker.json 里没有密钥时，工作机启动后会在浏览器里申请接入账号。
if /i not "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    echo 此启动文件适用于 Windows x64。其他系统请参照工作机接入文档。
    goto :failed
)

set "UV_VERSION=0.13.7"
set "UV_DIR=.uv-%UV_VERSION%"
set "UV=%UV_DIR%\uv.exe"
if exist "%UV%" goto :run
where uv.exe >nul 2>&1
if not errorlevel 1 (
    set "UV=uv.exe"
    goto :run
)
echo 正在下载 uv，需要联网。
powershell.exe -NoProfile -NonInteractive -Command ^
  "$ErrorActionPreference = 'Stop';" ^
  "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
  "$scratch = (New-Item -ItemType Directory (Join-Path $env:TEMP ([guid]::NewGuid().ToString()))).FullName;" ^
  "try { $zip = Join-Path $scratch 'uv.zip';" ^
  "Invoke-WebRequest -UseBasicParsing 'https://releases.astral.sh/github/uv/releases/download/%UV_VERSION%/uv-x86_64-pc-windows-msvc.zip' -TimeoutSec 180 -OutFile $zip;" ^
  "if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne '0cdc5b38fe5a8168ed6a25814f5ba43c21d313dd3187314fccb37b7cec46e021') { throw 'uv download checksum mismatch' };" ^
  "Expand-Archive -LiteralPath $zip -DestinationPath $scratch;" ^
  "New-Item -ItemType Directory -Force $env:UV_DIR | Out-Null;" ^
  "Move-Item -LiteralPath (Join-Path $scratch 'uv.exe') -Destination $env:UV_DIR -Force" ^
  "} finally { Remove-Item -LiteralPath $scratch -Recurse -Force }"
if errorlevel 1 goto :failed

:run
echo 正在检查 Python 3.12 和工作机依赖。
"%UV%" --no-config venv --allow-existing --python 3.12 .venv || goto :failed
"%UV%" --no-config pip sync --python .venv --require-hashes --only-binary :all: requirements.txt || goto :failed
set "COMFYSHOP_WORKER_CONFIG=%CD%\worker.json"
set "PYTHONUTF8=1"
.venv\Scripts\python.exe -m comfyshop_worker %*
if errorlevel 1 goto :failed
popd
pause
exit /b 0

:failed
popd
pause
exit /b 1
