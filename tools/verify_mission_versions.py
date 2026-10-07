"""Check metadata boundaries and the early-version browse contract.

Snapshot bytes are verified separately by map_versions.py against the fixed commits.
"""
import json,re
from pathlib import Path

root=Path(__file__).resolve().parents[1]
meta=json.loads((root/'editorial/mission-versions.json').read_text('utf8'))
catalog=json.loads((root/'data/catalog.json').read_text('utf8'))
byid={d['id']:d for d in catalog}
snapshots=meta['snapshots'];observed=meta['firstObservedVersions'];releases=meta['releaseEvidence']
assert len({s['version'] for s in snapshots})==len(snapshots)
assert all(re.fullmatch(r'[a-f0-9]{40}',s['commit']) and re.fullmatch(r'[a-f0-9]{64}',s['sha256']) for s in snapshots)
assert {f'1.{n}' for n in range(7)}|{f'2.{n}' for n in range(7)} <= {s['version'] for s in snapshots}
assert all(v in {s['version'] for s in snapshots} for v in observed.values())
assert meta['missions']=={**observed,**{id:e['version'] for id,e in releases.items()}}
for id,e in releases.items():
    assert id in byid and e['title']==byid[id]['title']
    assert e['sources'] and all(s['url'].startswith('https://') for s in e['sources'])
# A production table can contain a future mission. Observation must remain
# independent of the set of missions whose availability was researched.
assert observed['quest-2020309']=='1.1' and 'quest-2020309' not in releases
assert releases['quest-2000701']['version']=='1.1'
versions=json.loads((root/'dist/versions-data.json').read_text('utf8'))
quests={d['id'] for d in catalog if d['category']=='퀘스트'}
assert set(versions)==quests
assert all('unknown' not in v for v in versions.values())
assert '1.0' in versions['quest-1000101'] and 'early' in versions['quest-1000101']
assert '1.1' in versions['quest-2000701']
for v in {v for values in versions.values() for v in values}:
    assert (root/'dist/versions'/f'{v}.html').exists()
print(json.dumps({'status':'PASS','snapshots':len(snapshots),'metadataMissionIds':len(observed),'localMissions':len(quests),'releaseConfirmedEntries':len(releases),'boundary':'first observation and confirmed release remain separate'}))
