# Block writes to Ww / 123 / random Desktop siblings.
# Allow this repo and Claude Code's own ~/.claude/plans.
$ErrorActionPreference = "SilentlyContinue"
$raw = [Console]::In.ReadToEnd()
$root = $env:CLAUDE_PROJECT_DIR
if (-not $root) { exit 0 }
try { $obj = $raw | ConvertFrom-Json } catch { exit 0 }

$path = ""
if ($obj.tool_input.file_path) { $path = [string]$obj.tool_input.file_path }
elseif ($obj.tool_input.path) { $path = [string]$obj.tool_input.path }
elseif ($obj.tool_input.command) {
  $cmd = [string]$obj.tool_input.command
  if ($cmd -match '(^|[\s\\/])Ww([\\/]|$)' -or $cmd -match '(^|[\s\\/])123([\\/]|$)' -or $cmd -match 'z2wgv7dc4h-alt\\Ww') {
    [Console]::Error.WriteLine("Blocked: command touches Ww or 123")
    exit 2
  }
  exit 0
}
if (-not $path) { exit 0 }

$full = [System.IO.Path]::GetFullPath($path)
$rootFull = [System.IO.Path]::GetFullPath($root)
$plans = Join-Path $env:USERPROFILE ".claude\plans"
$claudeHome = Join-Path $env:USERPROFILE ".claude"

if ($full.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) { exit 0 }
if ($full.StartsWith($plans, [StringComparison]::OrdinalIgnoreCase)) { exit 0 }
if ($full.StartsWith($claudeHome, [StringComparison]::OrdinalIgnoreCase) -and $full -match '\\plans\\') { exit 0 }
if ($full -match '\\Ww\\' -or $full -match '\\123\\') {
  [Console]::Error.WriteLine("Blocked: Ww/123 path")
  exit 2
}
exit 0