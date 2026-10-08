"""Join exact public Story references with preserved local Korean dialogue.

Never uses a numeric prefix/range to assign a dialogue to a mission. Public
metadata provides IDs and pointers; all text and speaker fields come from the
preserved local extraction. Structure traversal order is not execution order.
"""
import argparse, hashlib, json, re, tarfile
from collections import defaultdict, deque
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
COMMIT = '8b178dd48698e5e7b12f0cc319ddab149f2ffc5c'
REPO = 'DimbreathBot/TurnBasedGameData'
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p): return json.loads(p.read_text('utf8'))
def refs(obj, pointer=''):
    if isinstance(obj, dict):
        for key, value in obj.items():
            p=pointer+'/'+key
            if key=='TalkSentenceID' and isinstance(value,int):
                yield value,p,'TalkSentenceID'
            elif key=='TalkSentenceIDList' and isinstance(value,list):
                for i,v in enumerate(value):
                    if isinstance(v,int): yield v,p+'/'+str(i),'TalkSentenceIDList'
            elif isinstance(value,str) and re.fullmatch(r'TalkSentence_\d+',value):
                yield int(value.split('_')[1]),p,'TalkSentence event reference'
            yield from refs(value,p)
    elif isinstance(obj,list):
        for i,v in enumerate(obj): yield from refs(v,pointer+'/'+str(i))

def objects(obj, pointer=''):
    if isinstance(obj,dict):
        yield obj,pointer
        for k,v in obj.items():yield from objects(v,pointer+'/'+k)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):yield from objects(v,pointer+'/'+str(i))

def path_refs(obj,pointer=''):
    if isinstance(obj,dict):
        for k,v in obj.items():yield from path_refs(v,pointer+'/'+k)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):yield from path_refs(v,pointer+'/'+str(i))
    elif isinstance(obj,str) and obj.endswith('.json') and obj.startswith(('Config/','Story/')):
        yield obj,pointer

def load_metadata(archive):
    metadata={}; hashes={}; performances=defaultdict(list)
    with tarfile.open(archive,'r:gz') as tf:
        for m in tf:
            n=m.name.split('/',1)[-1]
            table=bool(re.fullmatch(r'ExcelOutput/Performance(?:A|C|D|E|DS|CG|CLD|DLD|DSLD|Video|VideoLD)\.json',n))
            if not n.endswith('.json') or not (n.startswith(('Config/Level/','Story/')) or table):continue
            raw=tf.extractfile(m).read();obj=json.loads(raw);metadata[n]=obj;hashes[n]=sha(raw)
            if table:
                for i,row in enumerate(obj):
                    if isinstance(row.get('PerformanceID'),int) and row.get('PerformancePath'):
                        performances[row['PerformanceID']].append({'source':n,'idPointer':'/'+str(i)+'/PerformanceID','pathPointer':'/'+str(i)+'/PerformancePath','target':row['PerformancePath']})
    return metadata,hashes,performances

def event_refs(metadata):
    producers=defaultdict(list);consumers=defaultdict(list)
    for source,obj in metadata.items():
        if not source.startswith(('Config/','Story/')):continue
        for task,ptr in objects(obj):
            kind=task.get('$type','').split('.')[-1]
            if kind not in ('WaitCustomString','TriggerCustomString'):continue
            value=task.get('CustomString');pointer=ptr+'/CustomString'
            if isinstance(value,dict):value=value.get('Value');pointer+='/Value'
            # Match the entire event name; never derive mission or talk IDs.
            if isinstance(value,str) and re.fullmatch(r'Talk_\d+',value):
                (consumers if kind=='WaitCustomString' else producers)[value].append({'source':source,'pointer':pointer})
    return producers,consumers

def mission_ownership_index(metadata):
    result=defaultdict(list)
    for path,obj in metadata.items():
        # MissionInfo schema defines ownership. Predicate/trigger MainMissionID
        # fields in unrelated acts describe conditions, not source ownership.
        if not path.startswith('Config/Level/Mission/') or not Path(path).name.startswith('MissionInfo_'):continue
        if not isinstance(obj,dict):continue
        if isinstance(obj.get('MainMissionID'),int):result[obj['MainMissionID']].append((path,'/MainMissionID'))
        for i,row in enumerate(obj.get('SubMissionList',[])):
            if isinstance(row.get('MainMissionID'),int):result[row['MainMissionID']].append((path,f'/SubMissionList/{i}/MainMissionID'))
    return result

def performance_matches(performances,pid,performance_type):
    primary={'A':['A'],'C':['C'],'D':['D','DS'],'DS':['DS'],'E':['E'],'CG':['CG'],'Video':['Video']}.get(performance_type,[])
    preferred=[r for r in performances.get(pid,[]) if Path(r['source']).stem in {'Performance'+kind for kind in primary}]
    if preferred:return preferred,'TYPED_PRIMARY_TABLE'
    # Type-preserving LD variants are consulted when the primary is absent.
    variant={'C':['CLD'],'D':['DLD','DSLD'],'DS':['DSLD'],'Video':['VideoLD']}.get(performance_type,[])
    alternate=[r for r in performances.get(pid,[]) if Path(r['source']).stem in {'Performance'+kind for kind in variant}]
    return alternate,'TYPED_VARIANT_TABLE'

def build(archive):
    quests={d['id']:d for p in (SITE/'data/documents').glob('quest-*.json') if (d:=read(p))}
    messages={d['id']:d for p in (SITE/'data/documents').glob('message-*.json') if (d:=read(p))}
    local={}
    for p in (SITE/'data/dialogues').glob('*.json'):
        for row in read(p)['section']['rows']:
            local[row['talk_id']]={**row,'pageId':p.stem,'url':'대사/'+p.stem+'.html#talk-'+str(row['talk_id'])}
    expected={s['source'] for q in quests.values() for s in q['sections'] if s.get('source')}
    missions=defaultdict(list); files={}; unresolved=[];coverage={};ambiguous=[]
    metadata,hashes,performances=load_metadata(archive)
    producers,consumers=event_refs(metadata)
    ownership_index=mission_ownership_index(metadata)
    folder_sources=defaultdict(list)
    for path in metadata:
        match=re.match(r'(?:Story/(?:Discussion/)?Mission|Config/Level/Mission)/(\d+)(?:/|\.)',path)
        if match:folder_sources['quest-'+match[1]].append(path)
    for mid,quest in quests.items():
        owners={};queue=deque();main_id=int(mid.split('-')[1]);diagnostics=defaultdict(int)
        membership={main_id:'/id'}
        for key in ('missionParts','aliases'):
            for i,value in enumerate(quest.get(key,[])):
                if isinstance(value,str) and re.fullmatch(r'quest-\d+',value):
                    membership.setdefault(int(value.split('-')[1]),f'/{key}/{i}')
        document_sha=sha((SITE/'data/documents'/(mid+'.json')).read_bytes())
        def seed(kind,path,owner,pointer=None):
            edge={'kind':kind,'source':path,'missionId':owner,'canonicalMissionId':main_id,
                  'membershipSource':'data/documents/'+mid+'.json','membershipSha256':document_sha,
                  'membershipPointer':membership[owner]}
            if pointer:edge['pointer']=pointer
            owners[path]=[edge];queue.append(path)
        # Complete strict traversal before seeding directory fallbacks. This
        # prevents a fallback visit from suppressing a later exact chain.
        for owner in membership:
            for path,pointer in ownership_index.get(owner,[]):
                if path not in owners:seed('EXPLICIT_MAIN_MISSION_ID',path,owner,pointer)
        seen=set()
        for phase in ('explicit','directory'):
            if phase=='directory':
                for owner in membership:
                    for path in folder_sources['quest-'+str(owner)]:
                        if path not in owners:seed('MISSION_DIRECTORY_CONVENTION',path,owner)
            while queue:
                path=queue.popleft()
                if path in seen:continue
                seen.add(path);obj=metadata[path];chain=owners[path]
                links=[(target,{'kind':'EXPLICIT_JSON_PATH','source':path,'pointer':ptr,'target':target}) for target,ptr in path_refs(obj)]
                for task,ptr in objects(obj):
                    pid=task.get('PerformanceID')
                    if task.get('$type','').endswith('.TriggerPerformance') and isinstance(pid,int):
                        matches,lookup_scope=performance_matches(performances,pid,task.get('PerformanceType','')); targets={r['target'] for r in matches}
                        if len(targets)==1:
                            record=matches[0]
                            links.append((record['target'],{'kind':'EXPLICIT_PERFORMANCE_LOOKUP','source':path,'pointer':ptr+'/PerformanceID','performanceId':pid,'performanceType':task.get('PerformanceType',''),'lookupScope':lookup_scope,'tableSource':record['source'],'idPointer':record['idPointer'],'pathPointer':record['pathPointer'],'target':record['target']}))
                        elif len(targets)>1:
                            ambiguous.append({'missionId':mid,'source':path,'pointer':ptr+'/PerformanceID','performanceId':pid,'targets':sorted(targets)})
                    if task.get('$type','').endswith('.WaitCustomString'):
                        event=task.get('CustomString');event_pointer=ptr+'/CustomString'
                        if isinstance(event,dict):event=event.get('Value');event_pointer+='/Value'
                        if isinstance(event,str) and re.fullmatch(r'Talk_\d+',event):
                            ps=producers.get(event,[]);cs=consumers.get(event,[])
                            if len(ps)==1 and len(cs)==1 and cs[0]['source']==path:
                                producer=ps[0]
                                links.append((producer['source'],{'kind':'EXACT_UNIQUE_EVENT_CHANNEL','source':path,'pointer':event_pointer,'event':event,'producerPointer':producer['pointer'],'target':producer['source'],'producerCount':1,'consumerCount':1}))
                for target,edge in links:
                    if target not in metadata:
                        diagnostics['unavailableReferencedPaths']+=1;continue
                    if target not in owners or owners[target][0]['kind']=='MISSION_DIRECTORY_CONVENTION' and chain[0]['kind']!='MISSION_DIRECTORY_CONVENTION':
                        owners[target]=chain+[edge];queue.append(target)
                diagnostics['exactTalkReferences']+=len(list(refs(obj)))
                diagnostics['timelineReferences']+=sum(1 for task,_ in objects(obj) if task.get('$type','').endswith('.PlayTimeline'))
        for path in sorted(seen):
            obj=metadata[path];found=list(refs(obj));files[path]=hashes[path]
            option_ids={task['TalkSentenceID'] for task,_ in objects(obj) if task.get('$type','').endswith('.OptionTalkInfo') and isinstance(task.get('TalkSentenceID'),int)}
            for edge in owners[path]:
                files[edge['source']]=hashes[edge['source']]
                if edge.get('tableSource'):files[edge['tableSource']]=hashes[edge['tableSource']]
            existing={r.get('talk_id') for s in quests[mid]['sections'] if s.get('source')==path for r in s['rows']}
            grouped=defaultdict(list)
            for tid,ptr,kind in found: grouped[tid].append({'pointer':ptr,'kind':kind})
            rows=[]
            for tid,pointers in grouped.items():
                if tid in existing: continue
                if tid not in local:
                    unresolved.append({'missionId':mid,'source':path,'talkId':tid,'references':pointers}); continue
                row=local[tid]
                rows.append({**row,'references':pointers,'anchor':'talk-'+str(tid),'displayKind':'선택지' if tid in option_ids else '대사','classification':'EXPLICIT_OPTION_TASK' if tid in option_ids else 'PRESERVED_TALK_ROW'})
            if rows:
                missions[mid].append({'anchor':'supplement-'+sha(path.encode())[:12], 'title':'추가 대사 원문', 'source':path,'sourceSha256':hashes[path],'sourceUrl':f'https://github.com/{REPO}/blob/{COMMIT}/{path}', 'mapping':'EXACT_PUBLIC_STRUCTURE_REFERENCE_TO_PRESERVED_LOCAL_TALK','ownership':[{**edge,'sourceSha256':hashes[edge['source']],**({'tableSha256':hashes[edge['tableSource']]} if edge.get('tableSource') else {})} for edge in owners[path]], 'order':'구조 파일의 참조 순서', 'rows':rows})
        related_documents=[]
        for path in sorted(seen):
            for task,ptr in objects(metadata[path]):
                message_id=task.get('MessageSectionID');key='message-'+str(message_id)
                if isinstance(message_id,int) and key in messages:
                    document=messages[key]
                    related_documents.append({'id':key,'docId':key,'sourceId':key,'originalTableSource':document['source'],'sectionId':document['sections'][0]['anchor'] if document['sections'] else None,'sectionIds':[s['anchor'] for s in document['sections']],'title':document['title'],'url':document['url'],'count':document['count'],'sha256':sha((SITE/'data/documents'/(key+'.json')).read_bytes()),'messageSectionId':message_id,'referenceSource':path,'referenceSourceSha256':hashes[path],'pointer':ptr+'/MessageSectionID','ownership':[{**edge,'sourceSha256':hashes[edge['source']],**({'tableSha256':hashes[edge['tableSource']]} if edge.get('tableSource') else {})} for edge in owners[path]]})
        old_count=sum(bool(r.get('talk_id') and r.get('hash') and r.get('text')) for s in quest['sections'] for r in s['rows']);added_count=sum(len(s['rows']) for s in missions.get(mid,[]));local_count=sum(t in local for path in seen for t,_,_ in refs(metadata[path]))
        reason='LINKED' if old_count+added_count else 'STRUCTURE_UNAVAILABLE' if not seen else 'NO_LOCAL_KOREAN_FOR_EXACT_REFERENCES' if diagnostics['exactTalkReferences'] else 'TIMELINE_IDS_NOT_EXPOSED' if diagnostics['timelineReferences'] else 'NO_EXACT_DIALOGUE_REFERENCE'
        original_choices=sum(r.get('label')=='선택지' and bool(r.get('talk_id') and r.get('hash') and r.get('text')) for s in quest['sections'] for r in s['rows']);supplement_choices=sum(r['displayKind']=='선택지' for s in missions.get(mid,[]) for r in s['rows'])
        coverage[mid]={'originalRows':old_count,'originalChoices':original_choices,'originalDialogue':old_count-original_choices,'supplementRows':added_count,'supplementChoices':supplement_choices,'supplementDialogue':added_count-supplement_choices,'relatedDocuments':related_documents,'sourceOwnership':{path:[{**edge,'sourceSha256':hashes[edge['source']],**({'tableSha256':hashes[edge['tableSource']]} if edge.get('tableSource') else {})} for edge in owners[path]] for path in sorted(seen)},'structureFilesReached':len(seen),'localReferences':local_count,'reason':reason,**diagnostics}
    missing=sorted(expected-set(files))
    out={'schema':'starrail-mission-dialogue-supplements.v1','evidence':{'repository':REPO,'commit':COMMIT,'archiveSha256':sha(archive.read_bytes()),'dialogueIndexSha256':sha((SITE/'data/dialogue-index.json').read_bytes()),'preservedLocalSources':read(SITE/'data/dialogue-index.json')['evidence']['sources'],'currentInstallationReparse':'UNVERIFIED_FULL_KOREAN_PACK_UNAVAILABLE','structureFiles':files,'method':'Exact MissionInfo MainMissionID, JSON paths and unique PerformanceID-to-PerformancePath joins, with separately recorded mission-directory fallback. Exact TalkSentence IDs joined to unchanged local Korean rows.'},'missions':dict(missions),'coverage':coverage,'ambiguousPerformanceReferences':ambiguous,'unresolvedReferences':unresolved,'missingExistingStructurePaths':missing,'counts':{'localKoreanRows':len(local),'missions':len(missions),'scenes':sum(map(len,missions.values())),'rows':sum(len(s['rows']) for scenes in missions.values() for s in scenes),'structureFiles':len(files),'metadataFilesScanned':len(metadata),'missingStructurePaths':len(missing),'unresolvedReferences':len(unresolved),'coverageMissions':len(coverage)},'limitations':['공개 구조의 참조는 해당 장면에서 사용하는 식별자를 보여준다. 실제 실행 조건과 재생 순서는 별도 자료가 필요하다.','타임라인 내부 자막 중 구조 JSON에 식별자가 없는 대사는 이 연결 범위에 포함되지 않는다.','임무 폴더 관례에 따른 기존 연결과 MainMissionID·명시 경로에 따른 연결은 소유권 근거에서 구분한다.']}
    for p in [SITE/'data/mission-dialogue-supplements.json',SITE/'public/mission-dialogue-supplements.json']:
        p.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),'utf8')
    print(json.dumps(out['counts']))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);a=p.parse_args();build(a.archive)
