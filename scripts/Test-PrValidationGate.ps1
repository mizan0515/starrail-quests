#requires -Version 7.0
param([string]$Root=(Split-Path $PSScriptRoot -Parent),[int]$MaxTotalSeconds=600,[int]$ChildTimeoutSeconds=90)
$ErrorActionPreference='Stop'
Push-Location $Root
try {
  & npm.cmd run build
  if($LASTEXITCODE -ne 0){throw 'Reading build failed'}
  & npm.cmd run qa:reading
  if($LASTEXITCODE -ne 0){throw 'Reading data QA failed'}
  & node --test tools/build_reading_graph.test.mjs
  if($LASTEXITCODE -ne 0){throw 'Reading graph direction QA failed'}
  & python -B -X utf8 tools/verify_context_relations.py --self-test
  if($LASTEXITCODE -ne 0){throw 'Whole context original and relation direction QA failed'}
  & python -B -X utf8 tools/verify_topic_relations.py --self-test
  if($LASTEXITCODE -ne 0){throw 'Whole topic original relationship QA failed'}
  & python -B -X utf8 tools/verify_cva_topics.py
  if($LASTEXITCODE -ne 0){throw 'Whole CVA topic and cluster HTML QA failed'}
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
  & python -B -X utf8 tools/verify_official_mission_talks.py
  if($LASTEXITCODE -ne 0){throw 'Official mission Korean source QA failed'}
  & python -B -X utf8 tools/verify_official_mission_site.py
  if($LASTEXITCODE -ne 0){throw 'Official mission source disclosure HTML QA failed'}
  & python -B -X utf8 tools/verify_official_video_captions.py --artifact-only --self-test
  if($LASTEXITCODE -ne 0){throw 'Official video caption artifact and ownership QA failed'}
  & python -B -X utf8 tools/verify_official_caption_site.py
  if($LASTEXITCODE -ne 0){throw 'Official video caption original HTML QA failed'}
  & python -B -X utf8 tools/verify_official_talk_library.py --artifact-only --self-test
  if($LASTEXITCODE -ne 0){throw 'Whole official Talk library source QA failed'}
  & python -B -X utf8 tools/verify_official_talk_library_site.py
  if($LASTEXITCODE -ne 0){throw 'Whole official Talk library HTML QA failed'}
  & python -B tools/test_started_event_branches.py
  if($LASTEXITCODE -ne 0){throw 'Mission conditional ownership regression QA failed'}
  & python tools/verify_mission_readers.py
  if($LASTEXITCODE -ne 0){throw 'Primary reader source and classification QA failed'}
  & node --test tools/reading_return.test.mjs
  if($LASTEXITCODE -ne 0){throw 'Reading return context QA failed'}
  Write-Output 'RESULT: PASS'
} finally {Pop-Location}
