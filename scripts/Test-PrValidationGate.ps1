#requires -Version 7.0
param([string]$Root=(Split-Path $PSScriptRoot -Parent),[int]$MaxTotalSeconds=600,[int]$ChildTimeoutSeconds=90)
$ErrorActionPreference='Stop'
Push-Location $Root
try {
  & python -B -X utf8 tools/test_multivoice_configuration_refs.py
  if($LASTEXITCODE -ne 0){throw 'MultiVoice Talk and Voice domain regression QA failed'}
  & python -B -X utf8 tools/verify_native_choice_delta.py --self-test
  if($LASTEXITCODE -ne 0){throw 'Native choice source and domain QA failed'}
  & python -B -X utf8 tools/verify_lua_timeline_dialogue.py --self-test
  if($LASTEXITCODE -ne 0){throw 'Native source consumer and independent negative QA failed'}
  & python -B -X utf8 tools/verify_fresh_native_timeline.py --self-test
  if($LASTEXITCODE -ne 0){throw 'Fresh native Timeline exact source QA failed'}
  & python -B -X utf8 tools/verify_public_snapshot_timeline.py --self-test
  if($LASTEXITCODE -ne 0){throw 'Public snapshot Timeline source distinction QA failed'}
  & python -B -X utf8 tools/verify_timeline_owner_bridges.py --self-test
  if($LASTEXITCODE -ne 0){throw 'Auxiliary Timeline owner bridge QA failed'}
  & python -B -X utf8 tools/verify_dialogue_contexts.py
  if($LASTEXITCODE -ne 0){throw 'Whole dialogue attribution and preserved corpus QA failed'}
  & python -B -X utf8 tools/verify_deep_timeline_dialogue.py
  if($LASTEXITCODE -ne 0){throw 'Deep Timeline original source and inverse links QA failed'}
  & python -B -X utf8 tools/verify_sdf_timeline_text.py --self-test
  if($LASTEXITCODE -ne 0){throw 'SDF independent identity and Korean original QA failed'}
  $taskPublicationOld=$env:STARRAIL_VALIDATE_UNOPTIMIZED
  try {
    $env:STARRAIL_VALIDATE_UNOPTIMIZED='1'
    & npm.cmd run build
  } finally {
    if($null -eq $taskPublicationOld){Remove-Item Env:STARRAIL_VALIDATE_UNOPTIMIZED -ErrorAction SilentlyContinue}
    else {$env:STARRAIL_VALIDATE_UNOPTIMIZED=$taskPublicationOld}
  }
  if($LASTEXITCODE -ne 0){throw 'Reading build failed'}
  & python -B -X utf8 tools/verify_native_choice_delta.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Native choice originals and exact source metadata QA failed'}
  & python -B -X utf8 tools/verify_lua_timeline_dialogue.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Native consumer evidence and preserved static original QA failed'}
  & python -B -X utf8 tools/verify_fresh_native_timeline.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Fresh native Timeline static original QA failed'}
  & python -B -X utf8 tools/verify_public_snapshot_timeline.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Public snapshot Timeline static original QA failed'}
  & python -B -X utf8 tools/verify_dialogue_contexts.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Whole dialogue context original HTML and return links QA failed'}
  & python -B -X utf8 tools/verify_deep_timeline_dialogue.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Deep Timeline static original HTML and return links QA failed'}
  & python -B -X utf8 tools/verify_sdf_timeline_text.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'SDF static original HTML and identity QA failed'}
  & python -B -X utf8 tools/verify_handbook_originals.py --artifact-only --verify-only --self-test
  if($LASTEXITCODE -ne 0){throw 'Handbook original preservation and binding QA failed'}
  & python -B -X utf8 tools/verify_handbook_site.py --root dist
  if($LASTEXITCODE -ne 0){throw 'Handbook whole original HTML and navigation QA failed'}
  & node --test src/lib/handbook-originals.test.mjs src/lib/source-strikes.test.mjs
  if($LASTEXITCODE -ne 0){throw 'Handbook overlay and source projection QA failed'}
  & npm.cmd run qa:seo
  if($LASTEXITCODE -ne 0){throw 'Canonical sitemap and whole page metadata QA failed'}
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
  & python -B -X utf8 tools/verify_relic_backgrounds.py
  if($LASTEXITCODE -ne 0){throw 'Whole relic background original and source binding QA failed'}
  & python -B -X utf8 tools/verify_discovery.py --self-test
  if($LASTEXITCODE -ne 0){throw 'Whole discovery membership, source classification and SSR QA failed'}
  & python tools/verify_mission_dialogue_supplements.py
  if($LASTEXITCODE -ne 0){throw 'Mission dialogue source QA failed'}
  & python -B -X utf8 tools/verify_official_mission_talks.py
  if($LASTEXITCODE -ne 0){throw 'Official mission Korean source QA failed'}
  & python -B -X utf8 tools/verify_official_mission_site.py
  if($LASTEXITCODE -ne 0){throw 'Official mission source disclosure HTML QA failed'}
  & python -B -X utf8 tools/verify_timeline_mission_dialogue.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Typed Timeline original dialogue and mission reader QA failed'}
  & python -B -X utf8 tools/verify_native_timeline_mission_dialogue.py --dist dist --self-test
  if($LASTEXITCODE -ne 0){throw 'Native Timeline owner, original choices and reader QA failed'}
  & python -B -X utf8 tools/verify_official_video_captions.py --artifact-only --self-test
  if($LASTEXITCODE -ne 0){throw 'Official video caption artifact and ownership QA failed'}
  & python -B -X utf8 tools/verify_official_caption_site.py
  if($LASTEXITCODE -ne 0){throw 'Official video caption original HTML QA failed'}
  & python -B -X utf8 tools/verify_native_video_captions.py --dist dist --self-test
  if($LASTEXITCODE -ne 0){throw 'Native video source and Korean caption reader QA failed'}
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
  & python -B -X utf8 -m unittest tools/test_optimize_publication.py tools/test_publication_attributes.py
  if($LASTEXITCODE -ne 0){throw 'Publication proof compression boundary and exact inverse QA failed'}
  & python -B -X utf8 tools/optimize_publication.py
  if($LASTEXITCODE -ne 0){throw 'Publication size or exact shared UI reconstruction failed'}
  & python -B -X utf8 tools/verify_native_choice_delta.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Native choice originals and exact source metadata QA failed'}
  & python -B -X utf8 tools/verify_lua_timeline_dialogue.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Optimized Lua screen original and source consumer QA failed'}
  & python -B -X utf8 tools/verify_fresh_native_timeline.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Fresh native Timeline static original QA failed'}
  & python -B -X utf8 tools/verify_public_snapshot_timeline.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Public snapshot Timeline static original QA failed'}
  & python -B -X utf8 tools/verify_dialogue_contexts.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Optimized whole context static original HTML QA failed'}
  & python -B -X utf8 tools/verify_deep_timeline_dialogue.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Optimized deep Timeline static original QA failed'}
  & python -B -X utf8 tools/verify_sdf_timeline_text.py --dist dist
  if($LASTEXITCODE -ne 0){throw 'Optimized SDF static original QA failed'}
  & python -B -X utf8 tools/verify_site.py --root dist --base /starrail-quests
  if($LASTEXITCODE -ne 0){throw 'Optimized whole preserved static original HTML and links QA failed'}
  Write-Output 'RESULT: PASS'
} finally {Pop-Location}
