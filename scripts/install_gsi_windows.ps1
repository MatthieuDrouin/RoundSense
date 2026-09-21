$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$source = Join-Path $repoRoot "config\gamestate_integration_roundsense.cfg"
$candidates = @(
    "C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\cfg",
    "C:\Program Files\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\cfg"
)
$target = $null
foreach ($path in $candidates) {
    if (Test-Path $path) { $target = $path; break }
}
if (-not $target) {
    Write-Host "Could not find the default CS2 cfg folder."
    $target = Read-Host "Paste your ...\Counter-Strike Global Offensive\game\csgo\cfg path"
}
if (-not (Test-Path $target)) { throw "Folder does not exist: $target" }
Copy-Item $source (Join-Path $target "gamestate_integration_roundsense.cfg") -Force
Write-Host "Installed RoundSense GSI config to: $target"
Write-Host "Restart CS2 after the backend is running."
