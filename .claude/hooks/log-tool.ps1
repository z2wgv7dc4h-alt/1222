# Append one JSON line per tool call. Fast. Never print secrets.
$ErrorActionPreference = "SilentlyContinue"
$root = $env:CLAUDE_PROJECT_DIR
if (-not $root) { $root = (Get-Location).Path }
$logDir = Join-Path $root ".claude\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$day = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "tools-$day.jsonl"

$raw = [Console]::In.ReadToEnd()
$tool = "unknown"
$detail = ""
$session = ""
try {
  $obj = $raw | ConvertFrom-Json
  $tool = [string]$obj.tool_name
  $session = [string]$obj.session_id
  $ti = $obj.tool_input
  if ($ti.file_path) { $detail = [string]$ti.file_path }
  elseif ($ti.command) { $detail = ([string]$ti.command).Substring(0, [Math]::Min(200, ([string]$ti.command).Length)) }
  elseif ($ti.pattern) { $detail = [string]$ti.pattern }
} catch {}

$line = @{
  ts = (Get-Date).ToString("o")
  session = $session
  tool = $tool
  detail = $detail
} | ConvertTo-Json -Compress
Add-Content -Path $log -Value $line
exit 0
