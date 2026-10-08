"""Independently compare universe records with pinned metadata and local Korean."""
import argparse,hashlib,json,re,tarfile
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text('utf8'))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def at(obj,pointer):
 for k in pointer.split('/')[1:]:obj=obj[int(k)] if isinstance(obj,list) else obj[k]
 return obj
def talk_references(obj,pointer=''):
 if isinstance(obj,dict):
  for key,value in obj.items():
   loc=pointer+'/'+key
   if key=='TalkSentenceID' and type(value) is int:yield value,loc
   elif key=='TalkSentenceIDList' and isinstance(value,list):
    for i,tid in enumerate(value):
     if type(tid) is int:yield tid,loc+'/'+str(i)
   elif isinstance(value,str) and re.fullmatch(r'TalkSentence_\d+',value):yield int(value.split('_')[1]),loc
   if isinstance(value,(dict,list)):yield from talk_references(value,loc)
 elif isinstance(obj,list):
  for i,value in enumerate(obj):yield from talk_references(value,pointer+'/'+str(i))

def text_hashes(obj,pointer=''):
 if isinstance(obj,dict):
  if type(obj.get('Hash')) is int:yield str(obj['Hash']),pointer
  for key,value in obj.items():yield from text_hashes(value,pointer+'/'+key)
 elif isinstance(obj,list):
  for index,value in enumerate(obj):yield from text_hashes(value,pointer+'/'+str(index))

def verify_role(row,choice):
 assert row['kind']==('choice' if choice else 'dialogue') and row['displayKind']==('선택지' if choice else '대사')

def role_mutation_canaries():
 for choice,kind,label in [(True,'dialogue','대사'),(False,'choice','선택지')]:
  try:verify_role({'kind':kind,'displayKind':label},choice)
  except AssertionError:continue
  raise AssertionError('Wrong-role mutation was accepted')

def dict_nodes(obj,pointer=''):
 if isinstance(obj,dict):
  yield obj,pointer
  for key,value in obj.items():yield from dict_nodes(value,pointer+'/'+key)
 elif isinstance(obj,list):
  for index,value in enumerate(obj):yield from dict_nodes(value,pointer+'/'+str(index))

def expected_branches(obj,row,available):
 expected={}
 for ref in row['references']:
  p=ref['pointer'];parts=p.split('/')
  if not p.endswith('/TalkSentenceID') or len(parts)<4 or parts[-3]!='OptionList':continue
  if at(obj,'/'.join(parts[:-3])).get('$type')!='RPG.GameCore.PlayRogueOptionTalk':continue
  option=at(obj,'/'.join(parts[:-1]));event=option.get('TriggerCustomString','')
  if not re.fullmatch(r'TalkSentence_[0-9]+',event):continue
  tid=int(event.removeprefix('TalkSentence_'))
  if tid not in available:continue
  receivers=[p for item,p in dict_nodes(obj) if item.get('$type')=='RPG.GameCore.WaitCustomString' and item.get('CustomString',{}).get('Value')==event]
  if len(receivers)!=1:continue
  receiver=receivers[0];base,position=receiver.rsplit('/',1)
  if not base.endswith('/TaskList') or not position.isdigit():continue
  targets=[f'{base}/{n}/SimpleTalkList/{i}/TalkSentenceID' for n,task in enumerate(at(obj,base)) if n>int(position) and task.get('$type')=='RPG.GameCore.PlayAndWaitRogueSimpleTalk' for i,item in enumerate(task.get('SimpleTalkList',[])) if item.get('TalkSentenceID')==tid]
  if len(targets)!=1:continue
  source='/'.join(parts[:-1])+'/TriggerCustomString'
  expected[source]={'talkId':tid,'kind':'exact-talk-event','event':event,'sourcePointer':source,'receiverPointer':receiver+'/CustomString/Value','targetPointer':targets[0]}
 return list(expected.values())
def verify(archive):
 role_mutation_canaries()
 path=SITE/'data/universe-source-records.json';result=read(path);evidence=result['evidence']
 assert path.read_bytes()==(SITE/'public/universe-source-records.json').read_bytes()
 assert result['schemaVersion']=='starrail-universe-source-records.v1'
 assert evidence['repository']=='DimbreathBot/TurnBasedGameData' and evidence['commit']=='8b178dd48698e5e7b12f0cc319ddab149f2ffc5c'
 assert evidence['executionOrder']=='UNVERIFIED' and sha(archive.read_bytes())==evidence['archiveSha256']
 assert evidence['dialogueIndexSha256']==sha((SITE/'data/dialogue-index.json').read_bytes())
 assert evidence['preservedLocalSources']==read(SITE/'data/dialogue-index.json')['evidence']['sources']
 assert all(re.fullmatch(r'[a-f0-9]{64}',h) for h in evidence['structureFiles'].values())
 metadata={}
 with tarfile.open(archive,'r:gz') as tf:
  for item in tf:
   name=item.name.split('/',1)[-1]
   if name not in evidence['structureFiles']:continue
   assert name.startswith(('ExcelOutput/','Config/','Story/')) and 'TextMap' not in name
   raw=tf.extractfile(item).read();assert sha(raw)==evidence['structureFiles'][name],name
   metadata[name]=json.loads(raw)
 assert set(metadata)==set(evidence['structureFiles'])
 local={};byhash={}
 for p in (SITE/'data/dialogues').glob('*.json'):
  for row in read(p)['section']['rows']:
   assert row['talk_id'] not in local;local[row['talk_id']]=(row,p.stem)
   if row.get('hash'):byhash[row['hash']]=row['text']
 assert len(local)==240078
 curated={row['talk_id'] for mode in read(SITE/'data/universe-catalog.json')['modes'] for group in mode['dialogueGroups'] for row in group['rows']}
 contracts={'divergent-universe':('RogueTournFormula','FormulaID','FormulaStoryJson','방정식 기록'),'swarm-disaster':('RogueDLCSubStory','RogueDLCSubStoryID','LevelGraphPath','곤충 떼 재난 기록'),'gold-and-gears':('RogueNousSubStory','StoryID','LevelGraphPath','황금과 기계 기록'),'unknowable-domain':('RogueMagicStory','StoryID','LevelGraphPath','인지 불가 영역 기록')}
 assert {m['id'] for m in result['modes']}==set(contracts)
 ids=set();scene_count=row_count=ref_count=record_count=0;record_ids=set();expected_script_hashes=set()
 for mode in result['modes']:
  table,key,path_field,label=contracts[mode['id']];table_path='ExcelOutput/'+table+'.json'
  expected={row[key] for row in metadata[table_path] if row.get(path_field) and row[path_field] in metadata}
  assert {r['sourceRecordId'] for r in mode['records']}==expected
  for record in mode['records']:
   record_count+=1;assert record['id'] not in record_ids;record_ids.add(record['id'])
   assert re.fullmatch(r'[a-z0-9-]+',record['id'])
   assert record['sourceTable']==table_path and record['idField']==key
   assert record['sourceSha256']==evidence['structureFiles'][table_path]
   origin=metadata[table_path][record['sourceRow']]
   assert origin[key]==record['sourceRecordId'] and record['pointer']==f'/{record["sourceRow"]}/{path_field}'
   assert at(metadata[table_path],record['pointer'])==record['path']
   assert record['pathSha256']==evidence['structureFiles'][record['path']]
   assert record['executionOrder']=='UNVERIFIED' and record['orderStatus']=='TABLE_AND_REFERENCE_ARRAY_ORDER'
   title_field={'swarm-disaster':'SubStoryName','unknowable-domain':'StoryName'}.get(mode['id'])
   assert record['titleHash']==(str(origin.get(title_field,{}).get('Hash','')) if title_field else '')
   if record['titleStatus']=='EXACT_PRESERVED_KOREAN_HASH':assert byhash[record['titleHash']]==record['title']
   else:assert record['titleStatus']=='NEUTRAL_RECORD_ID' and record['title']==label+' '+str(origin[key])
   assert len({s['anchor'] for s in record['scenes']})==len(record['scenes'])
   assert not any(tid in local for tid,_ in talk_references(metadata[record['path']])) or any(s['source']==record['path'] for s in record['scenes'])
   for scene_index,scene in enumerate(record['scenes'],1):
    scene_count+=1;source=scene['source'];assert scene['pathSha256']==evidence['structureFiles'][source]
    for text_hash,pointer in text_hashes(metadata[source]):
     if text_hash!='0' and text_hash not in byhash:expected_script_hashes.add((mode['id'],record['id'],source,pointer,text_hash))
    assert scene['sourceSha256']==scene['pathSha256'] and scene['anchor']==record['id']+'-scene-'+str(scene_index)
    assert scene['mapping']=='EXACT_PUBLIC_STRUCTURE_REFERENCE_TO_PRESERVED_LOCAL_TALK'
    assert scene['sourceUrl']==f'https://github.com/{evidence["repository"]}/blob/{evidence["commit"]}/{source}'
    chain=scene['ownership'];current=table_path
    for i,edge in enumerate(chain):
     assert edge['source']==current and edge['sourceSha256']==evidence['structureFiles'][current]
     obj=metadata[current]
     if i==0:
      assert edge['kind']=='EXPLICIT_CONTENT_PATH' and edge['pointer']==record['pointer'] and edge['recordId']==origin[key]
      assert edge['target']==record['path']
     if edge['kind'] in ('EXPLICIT_CONTENT_PATH','EXPLICIT_JSON_PATH'):assert at(obj,edge['pointer'])==edge['target']
     elif edge['kind']=='EXPLICIT_PERFORMANCE_LOOKUP':
      task=at(obj,edge['pointer'].rsplit('/',1)[0])
      assert task['$type']=='RPG.GameCore.TriggerPerformance' and task['PerformanceID']==edge['performanceId'] and task['PerformanceType']==edge['performanceType']
      assert edge['tableSha256']==evidence['structureFiles'][edge['tableSource']]
      assert at(metadata[edge['tableSource']],edge['idPointer'])==edge['performanceId']
      assert at(metadata[edge['tableSource']],edge['pathPointer'])==edge['target']
      eligible={'A':{'A'},'C':{'C','CLD'},'D':{'D','DS','DLD','DSLD'},'DS':{'DS','DSLD'},'E':{'E'},'CG':{'CG'},'Video':{'Video','VideoLD'}}[edge['performanceType']]
      assert Path(edge['tableSource']).stem.removeprefix('Performance') in eligible
     else:raise AssertionError('Unknown exact chain kind')
     current=edge['target']
    assert current==source
    exact=list(talk_references(metadata[source]));available={tid for tid,_ in exact if tid in local}
    assert {r['TalkID'] for r in scene['rows']}==available
    direct_order=list(dict.fromkeys(tid for tid,pointer in exact if tid in local and pointer.endswith('/TalkSentenceID')))
    assert [r['TalkID'] for r in scene['rows']]==direct_order+list(dict.fromkeys(tid for tid,_ in exact if tid in local and tid not in direct_order))
    assert len(scene['rows'])==len(available)
    for row in scene['rows']:
     row_count+=1;tid=row['TalkID'];ids.add(tid);original,page=local[tid]
     assert row['talk_id']==tid and row['textmapHash']==original['hash'] and row['hash']==original['hash']
     for field in ('speaker','text','speaker_hash','offset','end'):assert row.get(field)==original.get(field),(record['id'],tid,field)
     assert row['sourceKind']==original.get('kind',original.get('label',''))
     assert row['pageId']==page and row['url']=='대사/'+page+'.html#talk-'+str(tid)
     pointers=[p for target,p in exact if target==tid]
     primary_pointer=next((p for p in pointers if p.endswith('/TalkSentenceID')),pointers[0])
     assert [r['pointer'] for r in row['references']]==pointers and row['pointer']==primary_pointer
     ref_count+=len(pointers);choice=False
     for pointer,proof in zip(pointers,row['references']):
      if pointer.endswith('/TalkSentenceID'):
       parts=pointer.split('/');owner=at(metadata[source],pointer.rsplit('/',1)[0]);expected_task=owner.get('$type','');expected_choice=expected_task.endswith('.OptionTalkInfo')
       if len(parts)>3 and parts[-3]=='OptionList' and parts[-2].isdigit():
        task=at(metadata[source],'/'.join(parts[:-3]))
        if task.get('$type')=='RPG.GameCore.PlayRogueOptionTalk':expected_task=task['$type'];expected_choice=True
       choice=choice or expected_choice
       assert proof['task']==expected_task and proof['choice']==expected_choice
       assert proof['destinations']=={k:v for k,v in owner.items() if re.search('next|jump|target|optionid|trigger|finishkey|sequence|branch|condition|success|fail',k,re.I)}
      else:assert proof['task']=='' and proof['destinations']=={}
     assert row['destinations']==next(p['destinations'] for p in row['references'] if p['pointer']==primary_pointer)
     verify_role(row,choice)
     assert row['branchTargets']==expected_branches(metadata[source],row,available)
 for missing in result['unresolvedTalkReferences']:
  assert missing['TalkID'] not in local
  assert (missing['TalkID'],missing['pointer']) in set(talk_references(metadata[missing['source']]))
 for unresolved in result['unresolvedTextFields']:
  table=unresolved['sourceTable'];assert unresolved['sourceSha256']==evidence['structureFiles'][table]
  assert str(at(metadata[table],unresolved['pointer'])['Hash'])==unresolved['textmapHash']
  assert unresolved['textmapHash']!='0' and unresolved['textmapHash'] not in byhash
  assert unresolved['status']=='NO_PRESERVED_KOREAN_HASH_JOIN'
 actual_script_hashes=set()
 for unresolved in result['unresolvedScriptTextFields']:
  source=unresolved['source'];assert unresolved['sourceSha256']==evidence['structureFiles'][source]
  assert str(at(metadata[source],unresolved['pointer'])['Hash'])==unresolved['textmapHash']
  assert unresolved['status']=='NO_PRESERVED_KOREAN_HASH_JOIN'
  actual_script_hashes.add((unresolved['modeId'],unresolved['recordId'],source,unresolved['pointer'],unresolved['textmapHash']))
 assert actual_script_hashes==expected_script_hashes and len(actual_script_hashes)==len(result['unresolvedScriptTextFields'])
 counts={'records':record_count,'scenes':scene_count,'renderedRows':row_count,'uniqueTalkIds':len(ids),'exactReferences':ref_count,'curatedOverlap':len(ids&curated),'newToReviewedDialogueGroups':len(ids-curated),'unresolvedTextFields':len(result['unresolvedTextFields']),'unresolvedScriptTextFields':len(actual_script_hashes),'missingPaths':len(result['unavailablePaths']),'unresolvedTalkReferences':len(result['unresolvedTalkReferences'])}
 source_rows=[row for mode in result['modes'] for record in mode['records'] for scene in record['scenes'] for row in scene['rows']]
 counts['choiceRows']=sum(row['kind']=='choice' for row in source_rows)
 counts['dialogueRows']=sum(row['kind']=='dialogue' for row in source_rows)
 counts['eventReferences']=sum(ref['referenceKind']=='TalkSentence event reference' for row in source_rows for ref in row['references'])
 counts['branchTargetRows']=sum(bool(row['branchTargets']) for row in source_rows)
 counts['branchTargets']=sum(len(row['branchTargets']) for row in source_rows)
 assert result['counts']==counts
 def public_paths(value):
  if isinstance(value,dict):
   assert 'originalPath' not in value,'Internal originalPath key in public output'
   for child in value.values():public_paths(child)
  elif isinstance(value,list):
   for child in value:public_paths(child)
  elif isinstance(value,str):
   assert not re.match(r'^(?:[A-Za-z]:[\\/]|\\\\)',value),'Absolute filesystem path in public output'
 public_paths(result)
 print(json.dumps({'status':'PASS','scope':'pinned-metadata-pointers-and-preserved-local-Korean','archiveSourcesVerified':len(metadata),'unchangedLocalKoreanRows':len(local),**counts}))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,required=True);verify(parser.parse_args().archive)
