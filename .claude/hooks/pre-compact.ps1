# Copy the live transcript into the project before Claude squashes the chat.
$ErrorActionPreference = "SilentlyContinue"
$root = $env:CLAUDE_PROJECT_DIR
if (-not $root) { $root = (Get-Location).Path }
$destDir = Join-Path $root ".claude\logs\transcripts"
New-Item -ItemType Directory -Force -Path $destDir | Out-Null

$raw = [Console]::In.ReadToEnd()
$src = $env:CLAUDE_TRANSCRIPT_PATH
try {
  $obj = $raw | ConvertFrom-Json
  if ($obj.transcript_path) { $src = [string]$obj.transcript_path }
} catch {}

if ($src -and (Test-Path $src)) {
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  Copy-Item $src (Join-Path $destDir "precompact-$stamp.jsonl") -Force
}
exit 0
