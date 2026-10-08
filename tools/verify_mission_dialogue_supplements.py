"""Validate mission affiliation, exact metadata pointers and unchanged local text."""
import argparse, hashlib, json, re, tarfile
from collections import defaultdict
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text('utf8'))
def sha(b):return hashlib.sha256(b).hexdigest()
def at(obj,pointer):
    for component in pointer.split('/')[1:]:obj=obj[int(component)] if isinstance(obj,list) else obj[component]
    return obj
def main(archive=None):
    p=SITE/'data/mission-dialogue-supplements.json'; out=read(p)
    assert p.read_bytes()==(SITE/'public/mission-dialogue-supplements.json').read_bytes()
    evidence=out['evidence']; index=read(SITE/'data/dialogue-index.json')
    assert out['schema']=='starrail-mission-dialogue-supplements.v1'
    assert re.fullmatch(r'[a-f0-9]{64}',evidence['archiveSha256'])
    assert re.fullmatch(r'[a-f0-9]{40}',evidence['commit'])
    assert evidence['repository']=='DimbreathBot/TurnBasedGameData'
    assert evidence['dialogueIndexSha256']==sha((SITE/'data/dialogue-index.json').read_bytes())
    assert evidence['preservedLocalSources']==index['evidence']['sources']
    assert all(re.fullmatch(r'[a-f0-9]{64}',s['sha256']) and s['size']>0 for s in evidence['preservedLocalSources'])
    assert all(re.fullmatch(r'[a-f0-9]{64}',h) for h in evidence['structureFiles'].values())
    local={r['talk_id']:r for p in (SITE/'data/dialogues').glob('*.json') for r in read(p)['section']['rows']}
    local_pages={r['talk_id']:p.stem for p in (SITE/'data/dialogues').glob('*.json') for r in read(p)['section']['rows']}
    assert len(local)==240078
    scenes=defaultdict(list)
    for mid,ss in out['missions'].items():
        for s in ss:scenes[s['source']].append((mid,s))
    scene_count=sum(len(ss) for ss in out['missions'].values())
    verified=set(); unique=set(); row_count=0
    for mid,ss in out['missions'].items():
        doc=read(SITE/'data/documents'/(mid+'.json'))
        assert doc['id']==mid
        assert len({s['anchor'] for s in ss})==len(ss)
        for s in ss:
            chain=s['ownership'];assert chain and chain==out['coverage'][mid]['sourceOwnership'][s['source']]
            assert chain[0]['kind'] in ('MISSION_DIRECTORY_CONVENTION','EXPLICIT_MAIN_MISSION_ID')
            if chain[0]['kind']=='MISSION_DIRECTORY_CONVENTION':
                match=re.match(r'(?:Story/(?:Discussion/)?Mission|Config/Level/Mission)/(\d+)(?:/|\.)',chain[0]['source'])
                assert match and chain[0]['missionId']==int(match[1])
            current=chain[0]['source']
            for i,edge in enumerate(chain):
                assert edge['source']==current
                assert edge['sourceSha256']==evidence['structureFiles'][edge['source']]
                if i:
                    assert edge['kind'] in ('EXPLICIT_JSON_PATH','EXPLICIT_PERFORMANCE_LOOKUP','EXACT_UNIQUE_EVENT_CHANNEL')
                    assert edge['pointer'].startswith('/')
                    if edge['kind']=='EXPLICIT_PERFORMANCE_LOOKUP':
                        assert edge['tableSha256']==evidence['structureFiles'][edge['tableSource']]
                        assert edge['lookupScope'] in ('TYPED_PRIMARY_TABLE','TYPED_VARIANT_TABLE')
                    if edge['kind']=='EXACT_UNIQUE_EVENT_CHANNEL':
                        assert re.fullmatch(r'Talk_\d+',edge['event'])
                        assert edge['producerCount']==edge['consumerCount']==1
                    current=edge['target']
            assert current==s['source']
            assert s['sourceSha256']==evidence['structureFiles'][s['source']]
            assert s['sourceUrl']==f"https://github.com/{evidence['repository']}/blob/{evidence['commit']}/{s['source']}"
            assert s['mapping']=='EXACT_PUBLIC_STRUCTURE_REFERENCE_TO_PRESERVED_LOCAL_TALK'
            old={r.get('talk_id') for sec in doc['sections'] if sec.get('source')==s['source'] for r in sec['rows']}
            assert not old.intersection(r['talk_id'] for r in s['rows'])
            assert len({r['talk_id'] for r in s['rows']})==len(s['rows'])
            for r in s['rows']:
                orig=local[r['talk_id']]
                for k,v in orig.items(): assert r[k]==v,(s['source'],r['talk_id'],k)
                assert r['anchor']=='talk-'+str(r['talk_id'])
                assert r['pageId']==local_pages[r['talk_id']]
                assert r['url']=='대사/'+r['pageId']+'.html#'+r['anchor']
                assert (SITE/'data/dialogues'/(r['pageId']+'.json')).exists()
                assert r['references']
                assert r['displayKind'] in ('선택지','대사')
                assert r['classification']==('EXPLICIT_OPTION_TASK' if r['displayKind']=='선택지' else 'PRESERVED_TALK_ROW')
                for ref in r['references']:
                    assert ref['pointer'].startswith('/')
                    assert ref['kind'] in ('TalkSentenceID','TalkSentenceIDList','TalkSentence event reference')
                unique.add(r['talk_id']); row_count+=1
    assert out['counts']['rows']==row_count
    assert out['counts']['missions']==len(out['missions'])
    assert out['counts']['scenes']==scene_count
    assert out['counts']['structureFiles']==len(evidence['structureFiles'])
    assert out['counts']['localKoreanRows']==len(local)
    assert out['counts']['missingStructurePaths']==len(out['missingExistingStructurePaths'])
    assert out['counts']['unresolvedReferences']==len(out['unresolvedReferences'])
    quest_ids={p.stem for p in (SITE/'data/documents').glob('quest-*.json')}
    assert set(out['coverage'])==quest_ids and out['counts']['coverageMissions']==len(quest_ids)
    for mid,c in out['coverage'].items():
        doc_path=SITE/'data/documents'/(mid+'.json');doc=read(doc_path)
        assert len(c['sourceOwnership'])==c['structureFilesReached']
        for source,chain in c['sourceOwnership'].items():
            assert chain and chain[0]['kind'] in ('EXPLICIT_MAIN_MISSION_ID','MISSION_DIRECTORY_CONVENTION')
            first=chain[0]
            assert first['canonicalMissionId']==int(mid.split('-')[1])
            assert first['membershipSource']=='data/documents/'+mid+'.json'
            assert first['membershipSha256']==sha(doc_path.read_bytes())
            assert first['membershipPointer']=='/id' or re.fullmatch(r'/(missionParts|aliases)/\d+',first['membershipPointer'])
            assert at(doc,first['membershipPointer'])=='quest-'+str(first['missionId'])
            if first['kind']=='EXPLICIT_MAIN_MISSION_ID':
                mission_info=Path(first['source']).name.startswith('MissionInfo_') and first['source'].startswith('Config/Level/Mission/')
                runtime_group=first['source'].startswith(('Config/LevelOutput/RuntimeGroup/','Config/LevelOutput/SharedRuntimeGroup/'))
                assert mission_info and (first['pointer']=='/MainMissionID' or re.fullmatch(r'/SubMissionList/\d+/MainMissionID',first['pointer'])) or runtime_group and first['pointer']=='/OwnerMainMissionID'
            else:
                match=re.match(r'(?:Story/(?:Discussion/)?Mission|Config/Level/Mission)/(\d+)(?:/|\.)',first['source'])
                assert match and int(match[1])==first['missionId']
            current=first['source']
            for i,edge in enumerate(chain):
                assert edge['source']==current and edge['sourceSha256']==evidence['structureFiles'][current]
                if i:
                    assert edge['kind'] in ('EXPLICIT_JSON_PATH','EXPLICIT_PERFORMANCE_LOOKUP','EXACT_UNIQUE_EVENT_CHANNEL')
                    assert edge['pointer'].startswith('/')
                    if edge.get('tableSource'):assert edge['tableSha256']==evidence['structureFiles'][edge['tableSource']]
                    current=edge['target']
            assert current==source and source in evidence['structureFiles']
        assert c['supplementRows']==sum(len(s['rows']) for s in out['missions'].get(mid,[]))
        assert c['supplementChoices']==sum(r['displayKind']=='선택지' for s in out['missions'].get(mid,[]) for r in s['rows'])
        assert c['originalRows']==c['originalDialogue']+c['originalChoices']
        assert c['supplementRows']==c['supplementDialogue']+c['supplementChoices']
        if 'primaryRows' in c:
            primary_added=sum(len(s['rows']) for s in out['missions'].get(mid,[]) if s['ownership'][0]['kind']=='EXPLICIT_MAIN_MISSION_ID')
            primary_old=sum(bool(r.get('talk_id') and r.get('hash') and r.get('text')) for s in doc['sections'] if c['sourceOwnership'].get(s.get('source'),[{}])[0].get('kind')=='EXPLICIT_MAIN_MISSION_ID' for r in s['rows'])
            assert c['primarySupplementRows']==primary_added and c['primaryOriginalRows']==primary_old
            assert c['primaryRows']==primary_added+primary_old
            assert c['referenceRows']==c['originalRows']+c['supplementRows']-c['primaryRows']
            assert c['primaryReason']==('LINKED' if c['primaryRows'] else 'NO_CONFIRMED_PRIMARY_ROWS')
        assert c['reason'] in ('LINKED','STRUCTURE_UNAVAILABLE','NO_LOCAL_KOREAN_FOR_EXACT_REFERENCES','TIMELINE_IDS_NOT_EXPOSED','NO_EXACT_DIALOGUE_REFERENCE')
        if 'unavailablePathReferences' in c:
            assert len(c['unavailablePathReferences'])==c.get('unavailableReferencedPaths',0)
            for ref in c['unavailablePathReferences']:
                assert ref['sourceSha256']==evidence['structureFiles'][ref['source']]
                assert ref['ownershipSeed']=={k:v for k,v in c['sourceOwnership'][ref['source']][0].items() if k not in ('sourceSha256','tableSha256')}
                if ref.get('tableSource'):assert ref['tableSha256']==evidence['structureFiles'][ref['tableSource']]
            if 'primaryCompleteness' in c:
                primary_missing=[ref for ref in c['unavailablePathReferences'] if ref['target'].startswith('Story/') and ref['ownershipSeed']['kind']=='EXPLICIT_MAIN_MISSION_ID']
                reference_missing=[ref for ref in c['unavailablePathReferences'] if ref['target'].startswith('Story/') and ref['ownershipSeed']['kind']=='MISSION_DIRECTORY_CONVENTION']
                assert c['missingPrimaryStoryReferences']==primary_missing
                assert c['missingReferenceStoryReferences']==reference_missing
                assert c['primaryCompleteness']==('PARTIAL_MISSING_REFERENCED_STRUCTURE' if primary_missing else 'NO_MISSING_REFERENCED_STORY_STRUCTURE')
        for ref in c['relatedDocuments']:
            document_path=SITE/'data/documents'/(ref['id']+'.json');document=read(document_path)
            assert sha(document_path.read_bytes())==ref['sha256']
            assert ref['id']=='message-'+str(ref['messageSectionId'])
            assert ref['docId']==ref['sourceId']==ref['id']
            assert ref['originalTableSource']==document['source']
            assert ref['sectionIds']==[s['anchor'] for s in document['sections']]
            assert ref['sectionId']==(ref['sectionIds'][0] if ref['sectionIds'] else None)
            assert document['source']=='MessageSectionConfig:'+str(ref['messageSectionId'])
            assert document['url']==ref['url'] and document['count']==ref['count'] and document['title']==ref['title']
            assert ref['referenceSourceSha256']==evidence['structureFiles'][ref['referenceSource']]
            assert ref['ownership']==c['sourceOwnership'][ref['referenceSource']]
    if archive:
      assert evidence['archiveSha256']==sha(archive.read_bytes())
      metadata={};event_objects={}
      with tarfile.open(archive,'r:gz') as tf:
        for m in tf:
            name=m.name.split('/',1)[-1]
            included=name in evidence['structureFiles']
            structure=name.endswith('.json') and name.startswith(('Config/Level/','Story/','Config/LevelOutput/RuntimeGroup/','Config/LevelOutput/SharedRuntimeGroup/'))
            if not included and not structure:continue
            raw=tf.extractfile(m).read()
            if included:
                assert sha(raw)==evidence['structureFiles'][name]
                metadata[name]=json.loads(raw)
            if structure and b'Talk_' in raw and (b'WaitCustomString' in raw or b'TriggerCustomString' in raw):
                event_objects[name]=metadata.get(name) or json.loads(raw)
      assert set(metadata)==set(evidence['structureFiles'])
      from build_mission_dialogue_supplements import event_refs
      producers,consumers=event_refs(event_objects)
      for conflict in out.get('runtimeGroupOwnershipConflicts',[]):
          origin=metadata[conflict['source']];graph=metadata[conflict['target']]
          assert origin['$type']=='RPG.GameCore.RtLevelGroupInfo'
          assert at(origin,conflict['ownerPointer'])==conflict['missionId']
          assert at(origin,conflict['graphPointer'])==conflict['target']
          assert conflict['sourceSha256']==evidence['structureFiles'][conflict['source']]
          assert conflict['targetSha256']==evidence['structureFiles'][conflict['target']]
          for finish in conflict['conflictingFinishReferences']:
              assert at(graph,finish['pointer'])==finish['submissionId'] and conflict['missionId'] not in finish['mainMissionIds']
              assert finish['mainMissionIds']==sorted({proof['missionId'] for proof in finish['ownerProofs']})
              for proof in finish['ownerProofs']:
                  assert proof['sourceSha256']==evidence['structureFiles'][proof['source']]
                  assert at(metadata[proof['source']],proof['idPointer'])==finish['submissionId']
                  assert at(metadata[proof['source']],proof['ownerPointer'])==proof['missionId']
      for mid,c in out['coverage'].items():
          for ref in c.get('unavailablePathReferences',[]):
              origin=metadata[ref['source']]
              if ref['kind']=='EXPLICIT_JSON_PATH':assert at(origin,ref['pointer'])==ref['target']
              elif ref['kind']=='EXPLICIT_PERFORMANCE_LOOKUP':
                  assert at(origin,ref['pointer'])==ref['performanceId']
                  assert at(origin,ref['pointer'].rsplit('/',1)[0])['PerformanceType']==ref['performanceType']
                  assert at(metadata[ref['tableSource']],ref['idPointer'])==ref['performanceId']
                  assert at(metadata[ref['tableSource']],ref['pathPointer'])==ref['target']
              elif ref['kind']=='EXACT_UNIQUE_EVENT_CHANNEL':raise AssertionError('event producer must exist in metadata')
          for source,chain in c['sourceOwnership'].items():
              for edge in chain:
                  origin=metadata[edge['source']]
                  if edge['kind']=='EXPLICIT_MAIN_MISSION_ID':
                      assert at(origin,edge['pointer'])==edge['missionId']
                      if edge['pointer']=='/OwnerMainMissionID':assert origin['$type']=='RPG.GameCore.RtLevelGroupInfo' and origin.get('LevelGraph')
                  elif edge['kind']=='EXPLICIT_JSON_PATH':assert at(origin,edge['pointer'])==edge['target']
                  elif edge['kind']=='EXPLICIT_PERFORMANCE_LOOKUP':
                      assert at(origin,edge['pointer'])==edge['performanceId']
                      assert at(origin,edge['pointer'].rsplit('/',1)[0])['PerformanceType']==edge['performanceType']
                      assert at(metadata[edge['tableSource']],edge['idPointer'])==edge['performanceId']
                      assert at(metadata[edge['tableSource']],edge['pathPointer'])==edge['target']
                  elif edge['kind']=='EXACT_UNIQUE_EVENT_CHANNEL':
                      assert at(origin,edge['pointer'])==edge['event']
                      assert at(metadata[edge['target']],edge['producerPointer'])==edge['event']
                      assert producers[edge['event']]==[{'source':edge['target'],'pointer':edge['producerPointer']}]
                      assert consumers[edge['event']]==[{'source':edge['source'],'pointer':edge['pointer']}]
          for ref in c['relatedDocuments']:
              assert at(metadata[ref['referenceSource']],ref['pointer'])==ref['messageSectionId']
              current=ref['ownership'][0]['source']
              for edge in ref['ownership']:
                  assert edge['source']==current and edge['sourceSha256']==evidence['structureFiles'][current]
                  origin=metadata[current]
                  if edge['kind']=='EXPLICIT_MAIN_MISSION_ID':assert at(origin,edge['pointer'])==edge['missionId']
                  elif edge['kind']=='EXPLICIT_JSON_PATH':assert at(origin,edge['pointer'])==edge['target']
                  elif edge['kind']=='EXPLICIT_PERFORMANCE_LOOKUP':
                      assert at(origin,edge['pointer'])==edge['performanceId']
                      assert at(origin,edge['pointer'].rsplit('/',1)[0])['PerformanceType']==edge['performanceType']
                      assert at(metadata[edge['tableSource']],edge['idPointer'])==edge['performanceId']
                      assert at(metadata[edge['tableSource']],edge['pathPointer'])==edge['target']
                  elif edge['kind']=='EXACT_UNIQUE_EVENT_CHANNEL':
                      assert at(origin,edge['pointer'])==edge['event']
                      assert at(metadata[edge['target']],edge['producerPointer'])==edge['event']
                      assert len(producers[edge['event']])==len(consumers[edge['event']])==1
                  current=edge.get('target',current)
              assert current==ref['referenceSource']
      for name,entries in scenes.items():
          obj=metadata[name]
          for mid,s in entries:
            for edge in s['ownership']:
                origin=metadata[edge['source']]
                if edge['kind']=='EXPLICIT_MAIN_MISSION_ID':assert at(origin,edge['pointer'])==edge['missionId']
                elif edge['kind']=='EXPLICIT_JSON_PATH':assert at(origin,edge['pointer'])==edge['target']
                elif edge['kind']=='EXPLICIT_PERFORMANCE_LOOKUP':
                    assert at(origin,edge['pointer'])==edge['performanceId']
                    assert at(origin,edge['pointer'].rsplit('/',1)[0])['PerformanceType']==edge['performanceType']
                    assert at(metadata[edge['tableSource']],edge['idPointer'])==edge['performanceId']
                    assert at(metadata[edge['tableSource']],edge['pathPointer'])==edge['target']
                elif edge['kind']=='EXACT_UNIQUE_EVENT_CHANNEL':
                    assert at(origin,edge['pointer'])==edge['event']
                    assert at(metadata[edge['target']],edge['producerPointer'])==edge['event']
                    assert len(producers[edge['event']])==len(consumers[edge['event']])==1
                    assert producers[edge['event']][0]=={'source':edge['target'],'pointer':edge['producerPointer']}
                    assert consumers[edge['event']][0]=={'source':edge['source'],'pointer':edge['pointer']}
            for r in s['rows']:
                for ref in r['references']:
                    x=at(obj,ref['pointer'])
                    assert x==r['talk_id'] or x=='TalkSentence_'+str(r['talk_id'])
                if r['displayKind']=='선택지':
                    assert any(ref['pointer'].endswith('/TalkSentenceID') and at(obj,ref['pointer'].rsplit('/',1)[0]).get('$type','').endswith('.OptionTalkInfo') for ref in r['references'])
            verified.add(name)
      assert set(scenes)==verified
    canary=out['coverage']['quest-1000400']['sourceOwnership']
    assert canary['Config/Level/Mission/1000401/Act/Act100040101.json'][0]['kind']=='MISSION_DIRECTORY_CONVENTION'
    exact=canary['Config/Level/Mission/1000401/Mission_100040121.json']
    assert exact[0]['kind']=='EXPLICIT_MAIN_MISSION_ID' and exact[0]['missionId']==1000401
    assert exact[0]['membershipPointer']=='/missionParts/1' and exact[-1]['kind']=='EXPLICIT_JSON_PATH'
    assert any(r['talk_id']==803130057 for s in out['missions']['quest-8031301'] for r in s['rows'])
    assert any(r['talk_id']==845000106 for s in out['missions']['quest-8041500'] for r in s['rows'])
    assert any(r['talk_id']==101011305 for s in out['missions']['quest-1010203'] for r in s['rows'])
    runtime_canary=out['coverage']['quest-1054411']
    group='Config/LevelOutput/SharedRuntimeGroup/Groups_P20541_F20541001/LevelGroup_P20541_F20541001_G72.json'
    graph='Config/Level/GroupGraph/F20541001/Group_F20541001_G72.json'
    chain=runtime_canary['sourceOwnership'][graph]
    assert chain[0]['source']==group and chain[0]['pointer']=='/OwnerMainMissionID' and chain[0]['missionId']==1054411
    assert chain[0]['kind']=='EXPLICIT_MAIN_MISSION_ID' and chain[1]['pointer']=='/LevelGraph' and chain[1]['target']==graph
    runtime_rows={r['talk_id'] for s in out['missions']['quest-1054411'] if s['source']==graph for r in s['rows']}
    assert {154112240,154112241,154112242}<=runtime_rows
    if 'primaryCompleteness' in runtime_canary:
        assert runtime_canary['primaryCompleteness']=='PARTIAL_MISSING_REFERENCED_STRUCTURE'
        assert any(ref['target']=='Story/Mission/1054411/Story105441100.json' for ref in runtime_canary['missingPrimaryStoryReferences'])
        assert any(ref['target']=='Story/Discussion/Mission/1054411/DS105441108.json' for ref in runtime_canary['missingPrimaryStoryReferences'])
    print(json.dumps({'status':'PASS','scope':'local-original-preservation-and-provenance-plus-archive-pointers' if archive else 'local-original-preservation-and-provenance','archivePointersVerified':bool(archive),'archiveSourcesVerified':len(verified),'missions':len(out['missions']),'scenes':scene_count,'supplementRows':row_count,'uniqueTalkIds':len(unique),'unchangedLocalKoreanRows':len(local),'coverageMissions':len(quest_ids),'sourceOwnershipChains':sum(len(c['sourceOwnership']) for c in out['coverage'].values()),'requiredExamples':[803130057,845000106]}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);main(p.parse_args().archive)
