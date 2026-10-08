"""Join explicitly referenced universe scripts with preserved local Korean rows."""
import argparse, hashlib, json, re, tarfile
from collections import defaultdict, deque
from pathlib import Path
from build_mission_dialogue_supplements import load_metadata, refs, objects, path_refs, performance_matches

SITE=Path(__file__).resolve().parents[1]
COMMIT='8b178dd48698e5e7b12f0cc319ddab149f2ffc5c'
REPOSITORY='DimbreathBot/TurnBasedGameData'
SPECS=[
 ('divergent-universe','RogueTournFormula','FormulaID','FormulaStoryJson',None,'방정식 기록'),
 ('swarm-disaster','RogueDLCSubStory','RogueDLCSubStoryID','LevelGraphPath','SubStoryName','곤충 떼 재난 기록'),
 ('gold-and-gears','RogueNousSubStory','StoryID','LevelGraphPath',None,'황금과 기계 기록'),
 ('unknowable-domain','RogueMagicStory','StoryID','LevelGraphPath','StoryName','인지 불가 영역 기록')]
HASH_TABLES={
 'divergent-universe':['RogueTournFormulaDisplay','RogueTournMiracleDisplay','RogueTournCollection','RogueTournRecordShowcase'],
 'swarm-disaster':['RogueDLCSubStory','RogueDLCMainStory'],
 'gold-and-gears':['RogueNousSubStory','RogueNousMainStory','RogueNousStoryDisplay'],
 'unknowable-domain':['RogueMagicStory','RogueMagicScepterDisplay']}
def read(p):return json.loads(p.read_text('utf8'))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def at(obj,pointer):
 for k in pointer.split('/')[1:]:obj=obj[int(k)] if isinstance(obj,list) else obj[k]
 return obj
def hash_fields(obj,pointer=''):
 if isinstance(obj,dict):
  if type(obj.get('Hash')) is int:yield str(obj['Hash']),pointer
  for k,v in obj.items():yield from hash_fields(v,pointer+'/'+k)
 elif isinstance(obj,list):
  for i,v in enumerate(obj):yield from hash_fields(v,pointer+'/'+str(i))

def branch_targets(obj,pointer,available):
 match=re.fullmatch(r'(.+)/OptionList/\d+/TalkSentenceID',pointer)
 if not match or at(obj,match[1]).get('$type')!='RPG.GameCore.PlayRogueOptionTalk':return []
 option=at(obj,pointer.rsplit('/',1)[0]);event=option.get('TriggerCustomString','')
 token=re.fullmatch(r'TalkSentence_(\d+)',event)
 if not token or int(token[1]) not in available:return []
 receivers=[(task,p) for task,p in objects(obj) if task.get('$type')=='RPG.GameCore.WaitCustomString' and task.get('CustomString',{}).get('Value')==event]
 if len(receivers)!=1:return []
 _,receiver=receivers[0];list_pointer,index=receiver.rsplit('/',1)
 if not list_pointer.endswith('/TaskList') or not index.isdigit():return []
 targets=[]
 for n,task in enumerate(at(obj,list_pointer)):
  if n<=int(index) or task.get('$type')!='RPG.GameCore.PlayAndWaitRogueSimpleTalk':continue
  for i,item in enumerate(task.get('SimpleTalkList',[])):
   if item.get('TalkSentenceID')==int(token[1]):targets.append(f'{list_pointer}/{n}/SimpleTalkList/{i}/TalkSentenceID')
 if len(targets)!=1:return []
 return [{'talkId':int(token[1]),'kind':'exact-talk-event','event':event,'sourcePointer':pointer.rsplit('/',1)[0]+'/TriggerCustomString','receiverPointer':receiver+'/CustomString/Value','targetPointer':targets[0]}]

def build(archive):
 metadata,hashes,performances=load_metadata(archive)
 table_names={s[1] for s in SPECS}|{n for ns in HASH_TABLES.values() for n in ns}
 with tarfile.open(archive,'r:gz') as tf:
  for item in tf:
   name=item.name.split('/',1)[-1]
   if name not in {'ExcelOutput/'+n+'.json' for n in table_names}:continue
   raw=tf.extractfile(item).read();metadata[name]=json.loads(raw);hashes[name]=sha(raw)
 local={};local_by_hash={}
 for p in (SITE/'data/dialogues').glob('*.json'):
  for row in read(p)['section']['rows']:
   assert row['talk_id'] not in local
   local[row['talk_id']]={**row,'pageId':p.stem,'url':'대사/'+p.stem+'.html#talk-'+str(row['talk_id'])}
   if row.get('hash'):local_by_hash[row['hash']]=row['text']
 assert len(local)==240078
 index=read(SITE/'data/dialogue-index.json')
 curated={r['talk_id'] for mode in read(SITE/'data/universe-catalog.json')['modes'] for group in mode['dialogueGroups'] for r in group['rows']}
 files={};modes=[];missing=[];missing_talks=[];unresolved_scripts=[];all_ids=set();references_count=0
 for mode_id,table,key,path_field,title_field,label in SPECS:
  source_table='ExcelOutput/'+table+'.json';files[source_table]=hashes[source_table];records=[]
  for i,record in enumerate(metadata[source_table]):
   path=record.get(path_field)
   if not path:continue
   origin={'kind':'EXPLICIT_CONTENT_PATH','source':source_table,'sourceSha256':hashes[source_table],'pointer':f'/{i}/{path_field}','recordId':record[key],'target':path}
   if path not in metadata:missing.append({'modeId':mode_id,**origin});continue
   title_hash=str(record.get(title_field,{}).get('Hash','')) if title_field else ''
   title=local_by_hash.get(title_hash) or f'{label} {record[key]}'
   record_id=mode_id+'-'+str(record[key])
   queue=deque([(path,[origin])]);seen=set();scenes=[]
   while queue:
    source,ownership=queue.popleft()
    if source in seen:continue
    seen.add(source);obj=metadata[source];files[source]=hashes[source]
    for text_hash,pointer in hash_fields(obj):
     if text_hash!='0' and text_hash not in local_by_hash:unresolved_scripts.append({'modeId':mode_id,'recordId':record_id,'source':source,'pointer':pointer,'textmapHash':text_hash,'sourceSha256':hashes[source],'status':'NO_PRESERVED_KOREAN_HASH_JOIN'})
    exact=defaultdict(list)
    for tid,pointer,ref_kind in refs(obj):
     if tid not in local:missing_talks.append({'modeId':mode_id,'recordId':record[key],'source':source,'sourceSha256':hashes[source],'TalkID':tid,'pointer':pointer});continue
     option=False;task_type='';destinations={}
     if pointer.endswith('/TalkSentenceID'):
      owner=at(obj,pointer.rsplit('/',1)[0]);option=isinstance(owner,dict) and owner.get('$type','').endswith('.OptionTalkInfo')
      task_type=owner.get('$type','');destinations={k:v for k,v in owner.items() if re.search('next|jump|target|optionid|trigger|finishkey|sequence|branch|condition|success|fail',k,re.I)}
      match=re.fullmatch(r'(.+)/OptionList/\d+/TalkSentenceID',pointer)
      if match and at(obj,match[1]).get('$type')=='RPG.GameCore.PlayRogueOptionTalk':option=True;task_type='RPG.GameCore.PlayRogueOptionTalk'
     exact[tid].append({'pointer':pointer,'referenceKind':ref_kind,'choice':option,'task':task_type,'destinations':destinations})
    direct_order=list(dict.fromkeys(tid for tid,_,kind in refs(obj) if kind=='TalkSentenceID' and tid in exact))
    rows=[]
    for tid in direct_order+[tid for tid in exact if tid not in direct_order]:
     proofs=exact[tid]
     source_row=local[tid];choice=any(p['choice'] for p in proofs)
     primary_ref=next((p for p in proofs if p['referenceKind']=='TalkSentenceID'),proofs[0])
     rows.append({**source_row,'TalkID':tid,'textmapHash':source_row['hash'],'sourceKind':source_row.get('kind',source_row.get('label','')),'kind':'choice' if choice else 'dialogue','displayKind':'선택지' if choice else '대사','pointer':primary_ref['pointer'],'destinations':primary_ref['destinations'],'references':proofs})
     all_ids.add(tid);references_count+=len(proofs)
    for row in rows:
     row['branchTargets']=list({target['sourcePointer']:target for proof in row['references'] if proof['choice'] for target in branch_targets(obj,proof['pointer'],exact)}.values())
    if rows:scenes.append({'anchor':record_id+'-scene-'+str(len(scenes)+1),'title':'원문 '+str(len(scenes)+1),'source':source,'pathSha256':hashes[source],'sourceSha256':hashes[source],'sourceUrl':f'https://github.com/{REPOSITORY}/blob/{COMMIT}/{source}','mapping':'EXACT_PUBLIC_STRUCTURE_REFERENCE_TO_PRESERVED_LOCAL_TALK','ownership':ownership,'rows':rows})
    links=[(target,{'kind':'EXPLICIT_JSON_PATH','source':source,'sourceSha256':hashes[source],'pointer':pointer,'target':target}) for target,pointer in path_refs(obj)]
    for task,pointer in objects(obj):
     if not task.get('$type','').endswith('.TriggerPerformance') or not isinstance(task.get('PerformanceID'),int):continue
     candidates,scope=performance_matches(performances,task['PerformanceID'],task.get('PerformanceType',''))
     if len({r['target'] for r in candidates})!=1:continue
     match=candidates[0];files[match['source']]=hashes[match['source']]
     links.append((match['target'],{'kind':'EXPLICIT_PERFORMANCE_LOOKUP','source':source,'sourceSha256':hashes[source],'pointer':pointer+'/PerformanceID','performanceId':task['PerformanceID'],'performanceType':task.get('PerformanceType',''),'lookupScope':scope,'tableSource':match['source'],'tableSha256':hashes[match['source']],'idPointer':match['idPointer'],'pathPointer':match['pathPointer'],'target':match['target']}))
    for target,proof in links:
     if target in metadata:queue.append((target,ownership+[proof]))
     else:missing.append({'modeId':mode_id,'recordId':record[key],**proof})
   records.append({'id':record_id,'title':title,'titleHash':title_hash,'titleStatus':'EXACT_PRESERVED_KOREAN_HASH' if title_hash in local_by_hash else 'NEUTRAL_RECORD_ID','sourceTable':source_table,'sourceRow':i,'sourceRecordId':record[key],'idField':key,'pointer':f'/{i}/{path_field}','sourceSha256':hashes[source_table],'path':path,'pathSha256':hashes[path],'recordMetadata':{k:v for k,v in record.items() if k in ('Layer','NextIDList','MinNousValue','MaxNousValue','FormulaCategory','MainBuffTypeID','SubBuffTypeID','MainBuffNum','SubBuffNum','FormulaDisplayID','StoryCategory')},'orderStatus':'TABLE_AND_REFERENCE_ARRAY_ORDER','executionOrder':'UNVERIFIED','scenes':scenes})
  modes.append({'id':mode_id,'records':records})
 unresolved=[]
 for mode_id,tables in HASH_TABLES.items():
  for table in tables:
   name='ExcelOutput/'+table+'.json';files[name]=hashes[name]
   for text_hash,pointer in hash_fields(metadata[name]):
    if text_hash!='0' and text_hash not in local_by_hash:unresolved.append({'modeId':mode_id,'sourceTable':name,'sourceRow':int(pointer.split('/')[1]),'pointer':pointer,'textmapHash':text_hash,'sourceSha256':hashes[name],'status':'NO_PRESERVED_KOREAN_HASH_JOIN'})
 counts={'records':sum(len(m['records']) for m in modes),'scenes':sum(len(r['scenes']) for m in modes for r in m['records']),'renderedRows':sum(len(s['rows']) for m in modes for r in m['records'] for s in r['scenes']),'uniqueTalkIds':len(all_ids),'exactReferences':references_count,'curatedOverlap':len(all_ids&curated),'newToReviewedDialogueGroups':len(all_ids-curated),'unresolvedTextFields':len(unresolved),'missingPaths':len(missing),'unresolvedTalkReferences':len(missing_talks)}
 counts['unresolvedScriptTextFields']=len(unresolved_scripts)
 source_rows=[row for mode in modes for record in mode['records'] for scene in record['scenes'] for row in scene['rows']]
 counts['choiceRows']=sum(row['kind']=='choice' for row in source_rows)
 counts['dialogueRows']=sum(row['kind']=='dialogue' for row in source_rows)
 counts['eventReferences']=sum(ref['referenceKind']=='TalkSentence event reference' for row in source_rows for ref in row['references'])
 counts['branchTargetRows']=sum(bool(row['branchTargets']) for row in source_rows)
 counts['branchTargets']=sum(len(row['branchTargets']) for row in source_rows)
 result={'schemaVersion':'starrail-universe-source-records.v1','evidence':{'repository':REPOSITORY,'commit':COMMIT,'archiveSha256':sha(archive.read_bytes()),'dialogueIndexSha256':sha((SITE/'data/dialogue-index.json').read_bytes()),'preservedLocalSources':index['evidence']['sources'],'structureFiles':files,'executionOrder':'UNVERIFIED'},'modes':modes,'counts':counts,'unresolvedTextFields':unresolved,'unresolvedScriptTextFields':unresolved_scripts,'unavailablePaths':missing,'unresolvedTalkReferences':missing_talks}
 for p in (SITE/'data/universe-source-records.json',SITE/'public/universe-source-records.json'):p.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),'utf8')
 print(json.dumps(counts))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,required=True);build(parser.parse_args().archive)
