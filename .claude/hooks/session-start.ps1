$ErrorActionPreference = "SilentlyContinue"
$root = $env:CLAUDE_PROJECT_DIR
if (-not $root) { $root = (Get-Location).Path }
$logDir = Join-Path $root ".claude\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Add-Content (Join-Path $logDir "sessions.jsonl") ((@{
  ts = (Get-Date).ToString("o")
  event = "SessionStart"
} | ConvertTo-Json -Compress))

Write-Output "Repo: $root"
Write-Output "One task. P1+ read SCOPE-INDEX.md then one heading. Do not touch Ww or 123."
$idx = Join-Path $root "SCOPE-INDEX.md"
if (Test-Path $idx) { Write-Output "SCOPE-INDEX.md present." }
else { Write-Output "WARN: SCOPE-INDEX.md missing." }
$sc = Join-Path $root "god-tier-metal-scope.md"
if (Test-Path $sc) { Write-Output "god-tier-metal-scope.md present." }
else { Write-Output "WARN: god-tier-metal-scope.md missing (required from P1)." }
$cur = Join-Path $root "docs\CURRENT.md"
if (Test-Path $cur) {
  Write-Output ""
  Write-Output "===== docs/CURRENT.md ====="
  Get-Content $cur
}
$tasks = Join-Path $root "TASKS.md"
if (Test-Path $tasks) {
  Write-Output ""
  Write-Output "===== TASKS ## Next (head) ====="
  $on = $false
  $n = 0
  foreach ($l in (Get-Content $tasks)) {
    if ($l -match '^## Next') { $on = $true }
    elseif ($on -and $l -match '^## ') { break }
    if ($on) {
      Write-Output $l
      $n++
      if ($n -ge 16) { break }
    }
  }
}
