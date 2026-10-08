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
  & python tools/verify_mission_versions.py
  if($LASTEXITCODE -ne 0){throw 'Mission version boundary QA failed'}
  & python tools/verify_universe_catalog.py
  if($LASTEXITCODE -ne 0){throw 'Universe source catalogue QA failed'}
  & python tools/verify_universe_site.py
  if($LASTEXITCODE -ne 0){throw 'Universe source rendering QA failed'}
  & python -B tools/verify_universe_reading_clusters.py
  if($LASTEXITCODE -ne 0){throw 'Universe editorial citation QA failed'}
  & python -B tools/verify_universe_source_site.py
  if($LASTEXITCODE -ne 0){throw 'Universe exact record and source link HTML QA failed'}
  & python -B -X utf8 tools/verify_official_universe_texts.py
  if($LASTEXITCODE -ne 0){throw 'Official Korean universe text binding QA failed'}
  & python -B -X utf8 tools/verify_official_universe_site.py
  if($LASTEXITCODE -ne 0){throw 'Official Korean universe source HTML QA failed'}
  & python tools/verify_mission_dialogue_supplements.py
  if($LASTEXITCODE -ne 0){throw 'Mission dialogue source QA failed'}
  & python -B tools/test_started_event_branches.py
  if($LASTEXITCODE -ne 0){throw 'Mission conditional ownership regression QA failed'}
  & python tools/verify_mission_readers.py
  if($LASTEXITCODE -ne 0){throw 'Primary reader source and classification QA failed'}
  & node --test tools/reading_return.test.mjs
  if($LASTEXITCODE -ne 0){throw 'Reading return context QA failed'}
  Write-Output 'RESULT: PASS'
} finally {Pop-Location}
