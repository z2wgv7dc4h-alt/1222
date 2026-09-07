# Log the stop. Nudge CURRENT.md if engine files are newer than CURRENT.
$ErrorActionPreference = "SilentlyContinue"
$root = $env:CLAUDE_PROJECT_DIR
if (-not $root) { $root = (Get-Location).Path }
$logDir = Join-Path $root ".claude\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$raw = [Console]::In.ReadToEnd()
$session = ""
$transcript = $env:CLAUDE_TRANSCRIPT_PATH
try {
  $obj = $raw | ConvertFrom-Json
  $session = [string]$obj.session_id
  if ($obj.transcript_path) { $transcript = [string]$obj.transcript_path }
} catch {}

Add-Content (Join-Path $logDir "stops.jsonl") ((@{
  ts = (Get-Date).ToString("o")
  session = $session
  transcript = $transcript
} | ConvertTo-Json -Compress))

$current = Join-Path $root "docs\CURRENT.md"
$engine = Join-Path $root "engine"
$stale = $false
if (Test-Path $engine) {
  $code = Get-ChildItem $engine -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -match '\.(py|json|toml)$' } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  $docTime = [datetime]"2000-01-01"
  if (Test-Path $current) { $docTime = (Get-Item $current).LastWriteTime }
  if ($code -and $code.LastWriteTime -gt $docTime.AddSeconds(5)) { $stale = $true }
}

if ($stale) {
  [Console]::Error.WriteLine("CURRENT.md is older than engine/. Update docs before stopping.")
}
exit 0
