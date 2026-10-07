#requires -Version 7.0
param([string]$Root=(Split-Path $PSScriptRoot -Parent),[int]$MaxTotalSeconds=600,[int]$ChildTimeoutSeconds=90)
$ErrorActionPreference='Stop'
Push-Location $Root
try {
  & npm.cmd run build
  if($LASTEXITCODE -ne 0){throw 'Reading build failed'}
  & npm.cmd run qa:reading
  if($LASTEXITCODE -ne 0){throw 'Reading data QA failed'}
  & python tools/verify_complete_data.py
  if($LASTEXITCODE -ne 0){throw 'Complete source QA failed'}
  & python tools/verify_site.py --root dist --base /starrail-quests
  if($LASTEXITCODE -ne 0){throw 'Source and link QA failed'}
  Write-Output 'RESULT: PASS'
} finally {Pop-Location}
