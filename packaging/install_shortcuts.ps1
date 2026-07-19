# Creates Desktop and Start Menu shortcuts to the built WinDictoo.exe.
# Run after building: uv run pyinstaller packaging/WinDictoo.spec --noconfirm --distpath ..\dist --workpath ..\build
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root "dist\WinDictoo\WinDictoo.exe"
$icon = Join-Path $root "assets\windictoo.ico"
$workdir = Join-Path $root "dist\WinDictoo"

if (-not (Test-Path $exe)) {
    Write-Error "WinDictoo.exe not found at $exe - build it first (pyinstaller packaging/WinDictoo.spec)."
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$targets = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "WinDictoo.lnk"),
    (Join-Path (Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs") "WinDictoo.lnk")
)
foreach ($t in $targets) {
    $lnk = $shell.CreateShortcut($t)
    $lnk.TargetPath = $exe
    $lnk.WorkingDirectory = $workdir
    $lnk.IconLocation = $icon
    $lnk.Description = "WinDictoo - локальный голосовой ввод"
    $lnk.Save()
    Write-Output "created: $t"
}
Write-Output "Done. WinDictoo is now launchable from the Desktop and Start Menu."
