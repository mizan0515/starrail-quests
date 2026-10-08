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

def verify_branch(edge,evidence,metadata=None):
    assert edge['graphSha256']==evidence['structureFiles'][edge['graphSource']]
    assert edge['tableSha256']==evidence['structureFiles'][edge['tableSource']]
    assert re.fullmatch(r'/SubMissionList/\d+/ID',edge['pointer'])
    assert edge['ownerPointer']==edge['pointer'].rsplit('/',1)[0]+'/MainMissionID'
    assert edge['scopePointer']==edge['predicatePointer'].rsplit('/',1)[0]+'/SuccessTaskList'
    assert edge['finishPointer'].startswith(edge['scopePointer']+'/')
    assert edge['performancePointer'].startswith(edge['scopePointer']+'/')
    if metadata is None:return
    assert at(metadata[edge['source']],edge['pointer'])==edge['submissionId']
    assert at(metadata[edge['source']],edge['ownerPointer'])==edge['missionId']
    graph=metadata[edge['graphSource']];predicate=at(graph,edge['predicatePointer'])
    assert predicate['$type']=='RPG.GameCore.ByCompareSubMissionState'
    assert predicate['SubMissionID']==edge['submissionId'] and predicate['SubMissionState']=='Started'
    finish=at(graph,edge['finishPointer'].rsplit('/',1)[0])
    assert finish['$type']=='RPG.GameCore.ClientFinishMission' and finish['SubmissionID']==edge['submissionId']
    performance=at(graph,edge['performancePointer'].rsplit('/',1)[0])
    assert performance['$type']=='RPG.GameCore.TriggerPerformance'
    assert performance['PerformanceID']==edge['performanceId'] and performance['PerformanceType']==edge['performanceType']
    assert int(edge['performancePointer'].split('/')[-2])<int(edge['finishPointer'].split('/')[-2])
    assert at(metadata[edge['tableSource']],edge['idPointer'])==edge['performanceId']
    assert at(metadata[edge['tableSource']],edge['pathPointer'])==edge['target']
    from build_mission_dialogue_supplements import objects
    assert all(t.get('SubmissionID')==edge['submissionId'] for t,_ in objects(at(graph,edge['scopePointer'])) if t.get('$type','').endswith('.ClientFinishMission'))

def verify_started_menu(edge,evidence,metadata=None):
    assert edge['graphSha256']==evidence['structureFiles'][edge['graphSource']]
    assert re.fullmatch(r'/SubMissionList/\d+/ID',edge['pointer'])
    assert edge['ownerPointer']==edge['pointer'].rsplit('/',1)[0]+'/MainMissionID'
    assert edge['graphSource'].startswith(('Config/Level/NPCDialogue/','Config/Level/PropDialogue/'))
    assert re.fullmatch(re.escape(edge['predicatePointer'].rsplit('/',1)[0])+r'/SuccessTaskList/\d+',edge['menuPointer'])
    assert edge['dialoguePathPointer']==edge['menuPointer']+'/DialoguePath'
    if metadata is None:return
    assert at(metadata[edge['source']],edge['pointer'])==edge['submissionId']
    assert at(metadata[edge['source']],edge['ownerPointer'])==edge['missionId']
    graph=metadata[edge['graphSource']]
    branch=at(graph,edge['predicatePointer'].rsplit('/',1)[0])
    assert branch['$type']=='RPG.GameCore.PredicateTaskList'
    predicate=at(graph,edge['predicatePointer'])
    assert predicate['$type']=='RPG.GameCore.ByCompareSubMissionState'
    assert predicate['SubMissionID']==edge['submissionId'] and predicate['SubMissionState']=='Started'
    menu=at(graph,edge['menuPointer'])
    assert menu['$type']=='RPG.GameCore.AddMenuItem' and menu['MissionID']==edge['submissionId']
    assert at(graph,edge['dialoguePathPointer'])==edge['target']

def verify_finish_scope(edge,evidence,metadata=None):
    assert edge['scopeSourceSha256']==evidence['structureFiles'][edge['target']]
    assert isinstance(edge['allTalkReferencesInsideScope'],bool)
    assert edge['scopeTalkIds']==sorted(set(edge['scopeTalkIds']))
    assert re.fullmatch(r'/SubMissionList/\d+/ID',edge['pointer'])
    assert edge['ownerPointer']==edge['pointer'].rsplit('/',1)[0]+'/MainMissionID'
    assert edge['target'].startswith(('Config/Level/NPCDialogue/','Config/Level/PropDialogue/'))
    assert edge['finishPointer'].startswith(edge['scopePointer']+'/')
    assert edge['finishOwnershipProofs']
    for proof in edge['finishOwnershipProofs']:
        assert proof['missionId']==edge['missionId']
        assert proof['sourceSha256']==evidence['structureFiles'][proof['source']]
    if metadata is None:return
    assert at(metadata[edge['source']],edge['pointer'])==edge['submissionId']
    assert at(metadata[edge['source']],edge['ownerPointer'])==edge['missionId']
    target=metadata[edge['target']];finish=at(target,edge['finishPointer'].rsplit('/',1)[0])
    assert finish['$type']=='RPG.GameCore.ClientFinishMission' and finish['SubmissionID']==edge['submissionId']
    from build_mission_dialogue_supplements import objects,refs,path_refs
    refs_all=list(refs(target))
    scoped=at(target,edge['scopePointer'])
    assert edge['scopeTalkIds'] or list(path_refs(scoped)) or any(t.get('$type','').endswith('.TriggerPerformance') and isinstance(t.get('PerformanceID'),int) for t,_ in objects(scoped))
    assert edge['allTalkReferencesInsideScope']==all(pointer.startswith(edge['scopePointer']+'/') for _,pointer,_ in refs_all)
    assert edge['scopeTalkIds']==sorted({tid for tid,_,_ in refs(at(target,edge['scopePointer']))})
    actual={(ptr+'/SubmissionID',t['SubmissionID']) for t,ptr in objects(at(target,edge['scopePointer']),edge['scopePointer']) if t.get('$type','').endswith('.ClientFinishMission')}
    assert actual=={(p['finishPointer'],p['submissionId']) for p in edge['finishOwnershipProofs']}
    for proof in edge['finishOwnershipProofs']:
        assert at(metadata[proof['source']],proof['idPointer'])==proof['submissionId']
        assert at(metadata[proof['source']],proof['ownerPointer'])==edge['missionId']

def verify_finish_performance(edge,evidence,metadata=None):
    assert edge['lookupScope']=='UNIQUE_CROSS_TYPED_TABLE_TARGET'
    assert edge['tableSha256']==evidence['structureFiles'][edge['tableSource']]
    assert re.fullmatch(r'/SubMissionList/\d+/ParamIntList/\d+',edge['pointer'])
    assert edge['source'].startswith('Config/Level/Mission/') and Path(edge['source']).name.startswith('MissionInfo_')
    assert edge['lookupTables'] and all(t in evidence['structureFiles'] for t in edge['lookupTables'])
    if metadata is None:return
    origin=metadata[edge['source']]
    assert at(origin,edge['pointer'])==edge['performanceId']
    assert at(origin,edge['ownerPointer'])==edge['missionId']
    assert at(origin,edge['finishTypePointer'])=='FinishFirstTalkPerformance'
    assert at(metadata[edge['tableSource']],edge['idPointer'])==edge['performanceId']
    assert at(metadata[edge['tableSource']],edge['pathPointer'])==edge['target']
    targets={r['PerformancePath'] for t in edge['lookupTables'] for r in metadata[t] if r.get('PerformanceID')==edge['performanceId'] and r.get('PerformancePath')}
    assert targets=={edge['target']}
def verify_primary_legacy_membership(out,metadata):
    """Verify existing primary rows against their exact canonical source.

    Ownership of a file alone does not prove a legacy row belongs to it.
    Scoped sources retain only their already proved primary Talk IDs here;
    related message documents remain under their separate source checks.
    """
    from build_mission_dialogue_supplements import refs,objects
    counts={'scenes':0,'rows':0,'mappingRows':{}}
    source_ids={}
    for mid,coverage in out['coverage'].items():
        doc=read(SITE/'data/documents'/(mid+'.json'))
        for section in doc['sections']:
            source=section.get('source');chain=coverage['sourceOwnership'].get(source,[])
            if not chain or chain[0]['kind']!='EXPLICIT_MAIN_MISSION_ID':continue
            scope=coverage.get('sourceTalkScopes',{}).get(source)
            rows=[row for row in section['rows'] if row.get('talk_id') and row.get('hash') and row.get('text') and (scope is None or row['talk_id'] in scope['talkIds'])]
            if not rows:continue
            location=mid+'#'+section['anchor']+' '+str(source)
            assert source in metadata,'Primary legacy source unavailable: '+location
            if source not in source_ids:source_ids[source]={tid for tid,_,_ in refs(metadata[source])}
            actual=source_ids[source]
            assert actual or not any(task.get('$type','').endswith('.PlayTimeline') for task,_ in objects(metadata[source])),'Timeline-only primary legacy source: '+location
            for row in rows:
                detail=location+' TalkID='+str(row['talk_id'])
                assert row['talk_id'] in actual,'Primary legacy TalkID outside canonical source: '+detail
                pointer=row.get('pointer')
                assert isinstance(pointer,str) and pointer.startswith('/'),'Primary legacy row pointer missing: '+detail
                try:row_object=at(metadata[source],pointer)
                except (KeyError,IndexError,TypeError,ValueError) as error:raise AssertionError('Primary legacy row pointer unavailable: '+detail+' '+pointer) from error
                assert row['talk_id'] in {tid for tid,_,_ in refs(row_object)},'Primary legacy row pointer mismatch: '+detail+' '+pointer
            counts['scenes']+=1;counts['rows']+=len(rows)
            mapping=section.get('mapping','UNKNOWN')
            counts['mappingRows'][mapping]=counts['mappingRows'].get(mapping,0)+len(rows)
    return counts

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
                    assert edge['kind'] in ('EXPLICIT_JSON_PATH','EXPLICIT_PERFORMANCE_LOOKUP','EXACT_UNIQUE_EVENT_CHANNEL','EXPLICIT_SUBMISSION_PERFORMANCE_BRANCH','EXPLICIT_STARTED_SUBMISSION_MENU','EXPLICIT_SUBMISSION_FINISH_SCOPE','EXPLICIT_MISSION_FINISH_PERFORMANCE')
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
        for source,scope in c.get('sourceTalkScopes',{}).items():
            assert source in c['sourceOwnership']
            assert c['sourceOwnership'][source][0]['kind']=='EXPLICIT_MAIN_MISSION_ID'
            assert c['sourceOwnership'][source][-1]['kind']=='EXPLICIT_SUBMISSION_FINISH_SCOPE'
            assert scope['pointers']==sorted({proof['scopePointer'] for proof in scope['proofs']})
            assert scope['talkIds']==sorted({tid for proof in scope['proofs'] for tid in proof['scopeTalkIds']})
            members={int(mid.split('-')[1])}|{int(x.split('-')[1]) for key in ('aliases','missionParts') for x in doc.get(key,[]) if re.fullmatch(r'quest-\d+',x)}
            for proof in scope['proofs']:
                assert proof['kind']=='EXPLICIT_SUBMISSION_FINISH_SCOPE' and proof['target']==source
                assert proof['missionId'] in members
                assert proof['sourceSha256']==evidence['structureFiles'][proof['source']]
                verify_finish_scope(proof,evidence)
            for scene in out['missions'].get(mid,[]):
                if scene['source']==source:
                    assert all(r['talk_id'] in scope['talkIds'] for r in scene['rows'])
                    assert all(any(ref['pointer'].startswith(pointer+'/') for pointer in scope['pointers']) for r in scene['rows'] for ref in r['references'])
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
                if edge['kind']=='EXPLICIT_SUBMISSION_PERFORMANCE_BRANCH':verify_branch(edge,evidence)
                if edge['kind']=='EXPLICIT_STARTED_SUBMISSION_MENU':verify_started_menu(edge,evidence)
                if edge['kind']=='EXPLICIT_SUBMISSION_FINISH_SCOPE':verify_finish_scope(edge,evidence)
                if edge['kind']=='EXPLICIT_MISSION_FINISH_PERFORMANCE':verify_finish_performance(edge,evidence)
                if i:
                    assert edge['kind'] in ('EXPLICIT_JSON_PATH','EXPLICIT_PERFORMANCE_LOOKUP','EXACT_UNIQUE_EVENT_CHANNEL','EXPLICIT_SUBMISSION_PERFORMANCE_BRANCH','EXPLICIT_STARTED_SUBMISSION_MENU','EXPLICIT_SUBMISSION_FINISH_SCOPE','EXPLICIT_MISSION_FINISH_PERFORMANCE')
                    assert edge['pointer'].startswith('/')
                    if edge.get('tableSource'):assert edge['tableSha256']==evidence['structureFiles'][edge['tableSource']]
                    current=edge['target']
            assert current==source and source in evidence['structureFiles']
            if any(e['kind']=='EXPLICIT_SUBMISSION_FINISH_SCOPE' and e['target']==source for e in chain):assert source in c.get('sourceTalkScopes',{})
        assert c['supplementRows']==sum(len(s['rows']) for s in out['missions'].get(mid,[]))
        assert c['supplementChoices']==sum(r['displayKind']=='선택지' for s in out['missions'].get(mid,[]) for r in s['rows'])
        assert c['originalRows']==c['originalDialogue']+c['originalChoices']
        assert c['supplementRows']==c['supplementDialogue']+c['supplementChoices']
        if 'primaryRows' in c:
            primary_added=sum(len(s['rows']) for s in out['missions'].get(mid,[]) if s['ownership'][0]['kind']=='EXPLICIT_MAIN_MISSION_ID')
            primary_old=sum(bool(r.get('talk_id') and r.get('hash') and r.get('text')) for s in doc['sections'] if c['sourceOwnership'].get(s.get('source'),[{}])[0].get('kind')=='EXPLICIT_MAIN_MISSION_ID' for r in s['rows'] if s.get('source') not in c.get('sourceTalkScopes',{}) or r.get('talk_id') in c['sourceTalkScopes'][s['source']]['talkIds'])
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
                if ref['kind']=='EXPLICIT_SUBMISSION_PERFORMANCE_BRANCH':verify_branch(ref,evidence)
                if ref['kind']=='EXPLICIT_STARTED_SUBMISSION_MENU':verify_started_menu(ref,evidence)
                if ref['kind']=='EXPLICIT_MISSION_FINISH_PERFORMANCE':verify_finish_performance(ref,evidence)
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
            if ref.get('referenceKind') in ('MISSION_FINISH_MESSAGE_SECTION','MISSION_FINISH_PERFORM_MESSAGE_SECTION'):
                assert ref['referenceSource'].startswith('Config/Level/Mission/') and Path(ref['referenceSource']).name.startswith('MissionInfo_')
                assert re.fullmatch(r'/SubMissionList/\d+/ParamInt1',ref['pointer'])
                if ref['referenceKind']=='MISSION_FINISH_PERFORM_MESSAGE_SECTION':
                    assert ref['sectionTableSource']=='ExcelOutput/MessageSectionConfig.json'
                    assert ref['sectionTableSha256']==evidence['structureFiles'][ref['sectionTableSource']]
                    assert re.fullmatch(r'/\d+/ID',ref['sectionIdPointer'])
                    assert ref['sectionPerformPointer']==ref['sectionIdPointer'].rsplit('/',1)[0]+'/IsPerformMessage'
    legacy_membership=None
    if archive:
      assert evidence['archiveSha256']==sha(archive.read_bytes())
      metadata={};event_objects={};performance_tables_found=set()
      with tarfile.open(archive,'r:gz') as tf:
        for m in tf:
            name=m.name.split('/',1)[-1]
            if re.fullmatch(r'ExcelOutput/Performance(?:A|C|D|E|DS|CG|CLD|DLD|DSLD|Video|VideoLD)\.json',name):performance_tables_found.add(name)
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
      legacy_membership=verify_primary_legacy_membership(out,metadata)
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
          for chain in c['sourceOwnership'].values():
              for edge in chain:
                  if edge['kind']=='EXPLICIT_MISSION_FINISH_PERFORMANCE':assert set(edge['lookupTables'])==performance_tables_found
          for source,scope in c.get('sourceTalkScopes',{}).items():
              for proof in scope['proofs']:verify_finish_scope(proof,evidence,metadata)
          for ref in c.get('unavailablePathReferences',[]):
              origin=metadata[ref['source']]
              if ref['kind']=='EXPLICIT_SUBMISSION_PERFORMANCE_BRANCH':verify_branch(ref,evidence,metadata)
              if ref['kind']=='EXPLICIT_STARTED_SUBMISSION_MENU':verify_started_menu(ref,evidence,metadata)
              if ref['kind']=='EXPLICIT_MISSION_FINISH_PERFORMANCE':
                  assert set(ref['lookupTables'])==performance_tables_found
                  verify_finish_performance(ref,evidence,metadata)
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
                  if edge['kind']=='EXPLICIT_SUBMISSION_PERFORMANCE_BRANCH':verify_branch(edge,evidence,metadata)
                  if edge['kind']=='EXPLICIT_STARTED_SUBMISSION_MENU':verify_started_menu(edge,evidence,metadata)
                  if edge['kind']=='EXPLICIT_SUBMISSION_FINISH_SCOPE':verify_finish_scope(edge,evidence,metadata)
                  if edge['kind']=='EXPLICIT_MISSION_FINISH_PERFORMANCE':verify_finish_performance(edge,evidence,metadata)
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
              if ref.get('referenceKind') in ('MISSION_FINISH_MESSAGE_SECTION','MISSION_FINISH_PERFORM_MESSAGE_SECTION'):
                  row=at(metadata[ref['referenceSource']],ref['pointer'].rsplit('/',1)[0])
                  assert row['FinishType']==('MessagePerformSectionFinish' if ref['referenceKind']=='MISSION_FINISH_PERFORM_MESSAGE_SECTION' else 'MessageSectionFinish') and row['ParamType']=='Equal'
                  if ref['referenceKind']=='MISSION_FINISH_PERFORM_MESSAGE_SECTION':
                      assert at(metadata[ref['sectionTableSource']],ref['sectionIdPointer'])==ref['messageSectionId']
                      assert at(metadata[ref['sectionTableSource']],ref['sectionPerformPointer']) is True
                  doc=read(SITE/'data/documents'/(mid+'.json'))
                  members={int(mid.split('-')[1])}|{int(x.split('-')[1]) for k in ('aliases','missionParts') for x in doc.get(k,[]) if re.fullmatch(r'quest-\d+',x)}
                  assert row['MainMissionID'] in members
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
    for mid in range(4065061,4065068):
        # Explicit fixture IDs enumerate independent exact-condition fixtures;
        # the parser never uses a mission or dialogue numeric range.
        key='quest-'+str(mid);target='Config/Level/Mission/3050060/Act/Act305006014.json'
        branch=out['coverage'][key]['sourceOwnership'][target]
        assert branch[0]['kind']=='EXPLICIT_MAIN_MISSION_ID' and branch[0]['missionId']==mid
        assert branch[-1]['kind']=='EXPLICIT_SUBMISSION_PERFORMANCE_BRANCH'
        rows={r['talk_id'] for s in out['missions'][key] if s['source']==target for r in s['rows']}
        assert rows=={350605626,350605627,350605628}
        assert branch[-1]['graphSource'] not in out['coverage'][key]['sourceOwnership']
    dialogue_end='Config/Level/Mission/3000522/Talk/Talk_300052201.json'
    event_chain=out['coverage']['quest-3000522']['sourceOwnership'][dialogue_end]
    assert event_chain[0]['kind']=='EXPLICIT_MAIN_MISSION_ID'
    assert event_chain[-1]['kind'] in ('EXACT_UNIQUE_EVENT_CHANNEL','EXPLICIT_STARTED_SUBMISSION_MENU')
    if event_chain[-1]['kind']=='EXACT_UNIQUE_EVENT_CHANNEL':assert event_chain[-1]['event']=='Talk_300052201'
    else:assert event_chain[-1]['submissionId']==300052201
    original_daily=read(SITE/'data/documents/quest-3000522.json')
    assert any(r.get('talk_id')==300052302 for s in original_daily['sections']+out['missions'].get('quest-3000522',[]) if out['coverage']['quest-3000522']['sourceOwnership'].get(s.get('source'),[{}])[0].get('kind')=='EXPLICIT_MAIN_MISSION_ID' for r in s['rows'])
    if archive:
        assert at(metadata[dialogue_end],'/OnStartSequece/0/TaskList/1/$type')=='RPG.GameCore.TriggerCustomStringOnDialogEnd'
        bridge='Config/Level/Mission/3000522/Mission_300052201.json'
        assert at(metadata[bridge],'/OnStartSequece/1/TaskList/0/$type')=='RPG.GameCore.WaitCustomString'
        assert at(metadata[bridge],'/OnStartSequece/1/TaskList/1/$type')=='RPG.GameCore.FinishPerformanceMission'
        assert at(metadata[bridge],'/OnStartSequece/1/TaskList/1/Key')==at(metadata['Config/Level/Mission/3000522/MissionInfo_3000522.partial.json'],'/SubMissionList/0/ParamStr1')
        assert producers['Talk_300052201']==[{'source':dialogue_end,'pointer':'/OnStartSequece/0/TaskList/1/CustomString/Value'}]
        assert consumers['Talk_300052201']==[{'source':bridge,'pointer':'/OnStartSequece/1/TaskList/0/CustomString/Value'}]
    menu_target='Config/Level/Mission/3000702/Talk/Talk_300070201.json'
    menu_chain=out['coverage']['quest-3000702']['sourceOwnership'][menu_target]
    assert menu_chain[-1]['kind']=='EXPLICIT_STARTED_SUBMISSION_MENU' and menu_chain[-1]['submissionId']==300070201
    assert menu_chain[-1]['graphSource'] not in out['coverage']['quest-3000702']['sourceOwnership']
    menu_original=read(SITE/'data/documents/quest-3000702.json')
    assert any(r.get('talk_id')==300070201 for s in menu_original['sections']+out['missions'].get('quest-3000702',[]) if out['coverage']['quest-3000702']['sourceOwnership'].get(s.get('source'),[{}])[0].get('kind')=='EXPLICIT_MAIN_MISSION_ID' for r in s['rows'])
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
    print(json.dumps({'status':'PASS','scope':'local-original-preservation-and-provenance-plus-archive-pointers' if archive else 'local-original-preservation-and-provenance','archivePointersVerified':bool(archive),'archiveSourcesVerified':len(verified),'primaryLegacyMembershipVerified':bool(archive),'primaryLegacyMembership':legacy_membership,'missions':len(out['missions']),'scenes':scene_count,'supplementRows':row_count,'uniqueTalkIds':len(unique),'unchangedLocalKoreanRows':len(local),'coverageMissions':len(quest_ids),'sourceOwnershipChains':sum(len(c['sourceOwnership']) for c in out['coverage'].values()),'requiredExamples':[803130057,845000106]}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);main(p.parse_args().archive)
