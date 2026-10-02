# Установщик «Кедр» для Windows 10/11.
# powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1
$ErrorActionPreference = "Stop"
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
  $PSNativeCommandUseErrorActionPreference = $false
}

if ($env:OS -ne "Windows_NT") {
  Write-Error "Это установщик для Windows. На Mac: scripts/install-macos.sh"
  exit 1
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not (Test-Path (Join-Path $Root "package.json"))) {
  Write-Error "Запустите скрипт из папки Кедра: scripts\install-windows.ps1"
  exit 1
}

function Test-WingetCode([int]$Code) {
  # 0 — поставлено. -1978335189 — уже стоит, обновлять нечего.
  return @(0, -1978335189, 2316632107) -contains $Code
}

function Install-FirstPython {
  $last = 0
  foreach ($id in @("Python.Python.3.12", "Python.Python.3.13")) {
    Write-Host "winget: $id"
    & winget install --id $id -e --accept-package-agreements --accept-source-agreements --disable-interactivity
    $last = $LASTEXITCODE
    if (Test-WingetCode $last) { return }
  }
  throw "Не удалось поставить Python 3.12 или 3.13 (код $last)."
}

function Install-WingetPackage([string]$Id) {
  Write-Host "winget: $Id"
  & winget install --id $Id -e --accept-package-agreements --accept-source-agreements --disable-interactivity
  if (Test-WingetCode $LASTEXITCODE) { return }
  throw "Не удалось поставить $Id (код $LASTEXITCODE)."
}

function Update-SessionPath {
  $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $user = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = (($machine, $user) | Where-Object { $_ }) -join ";"
}

function Find-MsysBash {
  $candidates = @(
    "C:\msys64\usr\bin\bash.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\MSYS2\usr\bin\bash.exe")
  )
  foreach ($path in $candidates) {
    if (Test-Path $path) { return $path }
  }
  $fromPath = Get-Command bash.exe -ErrorAction SilentlyContinue
  if ($fromPath -and $fromPath.Source -match "msys64|MSYS2") {
    return $fromPath.Source
  }
  return $null
}

function Convert-ToMsys([string]$Path) {
  $full = [System.IO.Path]::GetFullPath($Path)
  if ($full -notmatch '^([A-Za-z]):\\(.*)$') {
    throw "Непонятный путь: $full"
  }
  $rest = ($Matches[2] -replace '\\', '/') -replace "'", "'\''"
  return "/" + $Matches[1].ToLower() + "/" + $rest
}

function Invoke-Msys([string]$Command, [switch]$AllowFailure) {
  $env:MSYSTEM = "UCRT64"
  $env:CHERE_INVOKING = "1"
  & $script:Bash -lc $Command
  if (-not $AllowFailure -and $LASTEXITCODE -ne 0) {
    throw "MSYS2 завершилась с кодом ${LASTEXITCODE}: $Command"
  }
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  throw "Нужен winget. Поставьте «Установщик приложений» из Microsoft Store и запустите скрипт снова."
}

Install-WingetPackage "MSYS2.MSYS2"
Install-FirstPython
Install-WingetPackage "OpenJS.NodeJS.LTS"
Install-WingetPackage "Gyan.FFmpeg"
Update-SessionPath

$script:Bash = Find-MsysBash
if (-not $script:Bash) {
  throw "Не найден MSYS2 (ожидался C:\msys64\usr\bin\bash.exe). Поставьте его от администратора и запустите скрипт снова."
}

Write-Host "Обновляю MSYS2…"
Invoke-Msys "pacman -Syu --noconfirm" -AllowFailure
Invoke-Msys "pacman -Syu --noconfirm"
Invoke-Msys "pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-libxml2 mingw-w64-ucrt-x86_64-pkgconf make git"

$msysRoot = Convert-ToMsys $Root
Invoke-Msys "cd '$msysRoot' && ./scripts/build-sacd-extract.sh"

$pythonCmd = $null
$pythonPrefix = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
  if ($LASTEXITCODE -eq 0) {
    $pythonCmd = "py"
    $pythonPrefix = @("-3")
  }
}
if (-not $pythonCmd) {
  foreach ($name in @("python", "python3")) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { continue }
    & $name -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
    if ($LASTEXITCODE -eq 0) {
      $pythonCmd = $name
      break
    }
  }
}
if (-not $pythonCmd) {
  throw "Нужен Python 3.9 или новее. Если установщик его только что поставил, закройте окно и запустите скрипт ещё раз."
}

& $pythonCmd @pythonPrefix (Join-Path $Root "scripts\make_icon.py")
if ($LASTEXITCODE -ne 0) { throw "Не удалось собрать значок." }

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "Не найден npm. Если Node только что поставлен, закройте окно и запустите скрипт ещё раз."
}
Push-Location $Root
try {
  & npm install
  if ($LASTEXITCODE -ne 0) { throw "npm install завершился с кодом $LASTEXITCODE." }
} finally {
  Pop-Location
}

$electron = Join-Path $Root "node_modules\electron\dist\electron.exe"
if (-not (Test-Path $electron)) {
  throw "Не найден Electron: $electron"
}

$dist = Join-Path $Root "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null
$cmdPath = Join-Path $dist "Kedr.cmd"
@(
  "@echo off"
  "setlocal"
  "set `"PYTHONUTF8=1`""
  "set `"PYTHONIOENCODING=utf-8`""
  "set `"PYTHONPATH=$Root`""
  "set `"KEDR_SACD_EXTRACT=$Root\bin\sacd_extract.exe`""
  "cd /d `"$Root`""
  "if not exist `"$electron`" ("
  "  echo Electron was not found. In the project folder run: npm install"
  "  exit /b 1"
  ")"
  "start `"`" `"$electron`" `"$Root`""
) | Set-Content -Path $cmdPath -Encoding Unicode

$desktop = [Environment]::GetFolderPath("Desktop")
if ($desktop) {
  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut((Join-Path $desktop "Kedr.lnk"))
  $shortcut.TargetPath = $cmdPath
  $shortcut.WorkingDirectory = $Root
  $shortcut.Description = "Кедр"
  $shortcut.WindowStyle = 7
  $shortcut.Save()
}

Write-Host "Готово. Ярлык «Кедр» на рабочем столе, либо запустите $cmdPath"
Write-Host "Папку проекта после установки не переносите: ярлык указывает на неё."
