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

def string_case_conditions(obj,references):
    """Preserve typed case predicates; file ownership is not a playback claim."""
    result=[]
    for task,pointer in objects(obj):
        if task.get('$type')!='RPG.GameCore.GenericSwitchCase':continue
        switch=task.get('SwitchRef',{})
        if switch.get('$type')!='RPG.GameCore.SwitchRefGraphDynamicString' or not isinstance(switch.get('Name'),str):continue
        for i,case in enumerate(task.get('Cases',[])):
            if case.get('$type')!='RPG.GameCore.StringCaseContainer' or not isinstance(case.get('Case',{}).get('Value'),str):continue
            branch=pointer+f'/Cases/{i}'
            for ref in references:
                if ref['pointer'].startswith(branch+'/OnSuccess/'):
                    result.append({'kind':'GRAPH_DYNAMIC_STRING_CASE','referencePointer':ref['pointer'],'switchPointer':pointer,
                                   'casePointer':branch,'namePointer':pointer+'/SwitchRef/Name','valuePointer':branch+'/Case/Value',
                                   'name':switch['Name'],'value':case['Case']['Value']})
    return result

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
            if not n.endswith('.json') or not (n.startswith(('Config/Level/','Story/','Config/LevelOutput/RuntimeGroup/','Config/LevelOutput/SharedRuntimeGroup/')) or table or n=='ExcelOutput/MessageSectionConfig.json'):continue
            raw=tf.extractfile(m).read();obj=json.loads(raw);metadata[n]=obj;hashes[n]=sha(raw)
            if table:
                for i,row in enumerate(obj):
                    if isinstance(row.get('PerformanceID'),int) and row.get('PerformancePath'):
                        performances[row['PerformanceID']].append({'source':n,'idPointer':'/'+str(i)+'/PerformanceID','pathPointer':'/'+str(i)+'/PerformancePath','target':row['PerformancePath']})
    return metadata,hashes,performances

def event_refs(metadata, all_names=False):
    producers=defaultdict(list);consumers=defaultdict(list)
    for source,obj in metadata.items():
        if not source.startswith(('Config/','Story/')):continue
        for task,ptr in objects(obj):
            kind=task.get('$type','').split('.')[-1]
            if kind not in ('WaitCustomString','TriggerCustomString','TriggerCustomStringOnDialogEnd'):continue
            value=task.get('CustomString');pointer=ptr+'/CustomString'
            if isinstance(value,dict):value=value.get('Value');pointer+='/Value'
            # Match the entire event name; never derive mission or talk IDs.
            if isinstance(value,str) and value and (all_names or re.fullmatch(r'Talk_\d+',value)):
                (consumers if kind=='WaitCustomString' else producers)[value].append({'source':source,'pointer':pointer})
    return producers,consumers

def submission_started_event_performances(metadata, hashes, performances):
    """Follow a direct Started branch through its exact mission completion event.

    The branch and its explicitly called performance may both emit the event.
    Other producers, default tasks and nested performance calls are excluded.
    """
    submissions=defaultdict(list);result=defaultdict(list);all_owners=defaultdict(set)
    for source,obj in metadata.items():
        if not source.startswith('Config/Level/Mission/') or not Path(source).name.startswith('MissionInfo_') or not isinstance(obj,dict):continue
        for index,row in enumerate(obj.get('SubMissionList',[])):
            if type(row.get('ID')) is int and type(row.get('MainMissionID')) is int:all_owners[row['ID']].add(row['MainMissionID'])
            if type(row.get('ID')) is int and type(row.get('MainMissionID')) is int and row.get('FinishType')=='Talk' and row.get('ParamType')=='Equal' and row.get('MissionJsonPath') in metadata and isinstance(row.get('ParamStr1'),str):
                submissions[row['ID']].append((source,index,row))
    producers,consumers=event_refs(metadata,all_names=True)
    for graph,obj in metadata.items():
        if not graph.startswith(('Config/Level/NPCDialogue/','Config/Level/PropDialogue/','Config/Level/GroupGraph/')):continue
        for branch,ptr in objects(obj):
            predicate=branch.get('Predicate',{});sid=predicate.get('SubMissionID')
            if predicate.get('$type')!='RPG.GameCore.ByCompareSubMissionState' or predicate.get('SubMissionState')!='Started' or sid not in submissions:continue
            if len(all_owners[sid])!=1:continue
            parts=ptr.split('/')[1:]
            if any(key in ('DefaultTask','FailTaskList','FailureTaskList','OnFailure','OnFail','OnFailed') for key in parts):continue
            conflict=False;ancestor_conditions=[]
            ancestor=obj
            for depth,key in enumerate(parts):
                parent_predicate=ancestor.get('Predicate',{}) if isinstance(ancestor,dict) else {}
                if parent_predicate and key in ('SuccessTaskList','FailedTaskList'):
                    ancestor_conditions.append({'predicatePointer':'/'+('/'.join(parts[:depth]))+'/Predicate','branchKey':key,'predicate':parent_predicate})
                if key=='FailedTaskList' and not parent_predicate:conflict=True
                if parent_predicate.get('$type')=='RPG.GameCore.ByCompareSubMissionState':
                    same=parent_predicate.get('SubMissionID')==sid;started=parent_predicate.get('SubMissionState')=='Started'
                    if key=='SuccessTaskList' and ((started and not same) or (same and not started)):conflict=True
                    if key=='FailedTaskList' and same and started:conflict=True
                ancestor=ancestor[int(key)] if isinstance(ancestor,list) else ancestor[key]
            if conflict:continue
            # SwitchCase children have no type; validate their exact parent.
            if branch.get('$type')!='RPG.GameCore.PredicateTaskList':
                parts=ptr.rsplit('/',2)
                if len(parts)!=3 or parts[1]!='TaskList' or not parts[2].isdigit():continue
                parent=obj
                for key in parts[0].split('/')[1:]:parent=parent[int(key)] if isinstance(parent,list) else parent[key]
                if parent.get('$type')!='RPG.GameCore.SwitchCase':continue
            tasks=branch.get('SuccessTaskList',[])
            direct=[(i,t) for i,t in enumerate(tasks) if t.get('$type')=='RPG.GameCore.TriggerPerformance']
            if len(direct)!=1:continue
            perf_index,performance=direct[0]
            matches,lookup=performance_matches(performances,performance.get('PerformanceID'),performance.get('PerformanceType'))
            if len({r['target'] for r in matches})!=1:continue
            record=matches[0];target=record['target']
            if target not in metadata:continue
            sends=[(i,t) for i,t in enumerate(tasks) if t.get('$type')=='RPG.GameCore.TriggerCustomString']
            if len(sends)!=1 or sends[0][0]<=perf_index:continue
            send_index,send=sends[0];event=send.get('CustomString');event=event.get('Value') if isinstance(event,dict) else event
            if not isinstance(event,str) or not event:continue
            send_pointer=ptr+f'/SuccessTaskList/{send_index}/CustomString'+('/Value' if isinstance(send.get('CustomString'),dict) else '')
            actual=producers[event]
            if {'source':graph,'pointer':send_pointer} not in actual:continue
            if any(p!={'source':graph,'pointer':send_pointer} and p['source']!=target for p in actual):continue
            if len(consumers[event])!=1:continue
            for source,index,row in submissions[sid]:
                mission=row['MissionJsonPath'];receiver=consumers[event][0]
                if receiver['source']!=mission:continue
                wait_pointer=receiver['pointer'].rsplit('/CustomString',1)[0]
                base,position=wait_pointer.rsplit('/',1)
                if not base.endswith('/TaskList') or not position.isdigit():continue
                mission_tasks=metadata[mission]
                for key in base.split('/')[1:]:mission_tasks=mission_tasks[int(key)] if isinstance(mission_tasks,list) else mission_tasks[key]
                finishes=[i for i,t in enumerate(mission_tasks) if t.get('$type')=='RPG.GameCore.FinishPerformanceMission' and t.get('Key')==row['ParamStr1']]
                if len(finishes)!=1 or finishes[0]<=int(position):continue
                if any(t.get('$type')=='RPG.GameCore.FinishPerformanceMission' and t.get('Key')!=row['ParamStr1'] for t in mission_tasks):continue
                edge={'kind':'EXPLICIT_STARTED_PERFORMANCE_EVENT_BRANCH','source':source,'pointer':f'/SubMissionList/{index}/ID','submissionId':sid,'missionId':row['MainMissionID'],'ownerPointer':f'/SubMissionList/{index}/MainMissionID','missionPathPointer':f'/SubMissionList/{index}/MissionJsonPath','finishKeyPointer':f'/SubMissionList/{index}/ParamStr1','finishKey':row['ParamStr1'],'graphSource':graph,'graphSha256':hashes[graph],'predicatePointer':ptr+'/Predicate','scopePointer':ptr+'/SuccessTaskList','performancePointer':ptr+f'/SuccessTaskList/{perf_index}/PerformanceID','performanceId':performance['PerformanceID'],'performanceType':performance['PerformanceType'],'lookupScope':lookup,'tableSource':record['source'],'idPointer':record['idPointer'],'pathPointer':record['pathPointer'],'target':target,'event':event,'sendPointer':send_pointer,'missionSource':mission,'missionSha256':hashes[mission],'receiverPointer':receiver['pointer'],'finishPointer':base+f'/{finishes[0]}/Key','eventProducers':actual,'eventConsumers':consumers[event]}
                edge['ancestorConditions']=ancestor_conditions
                result[source].append((target,edge))
    return result

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

def runtime_group_ownership_index(metadata):
    """Use the runtime group's declared owner, never its name or numeric IDs.

    A group that explicitly finishes another main mission is retained as a
    conflict diagnostic, rather than assigning its whole graph to either one.
    Shared groups without an owner are not assigned through GroupIDList.
    """
    subowners=defaultdict(set);subproofs=defaultdict(list)
    for path,obj in metadata.items():
        if not path.startswith('Config/Level/Mission/') or not Path(path).name.startswith('MissionInfo_') or not isinstance(obj,dict):continue
        for i,row in enumerate(obj.get('SubMissionList',[])):
            if isinstance(row.get('ID'),int) and isinstance(row.get('MainMissionID'),int):
                subowners[row['ID']].add(row['MainMissionID'])
                subproofs[row['ID']].append({'source':path,'idPointer':f'/SubMissionList/{i}/ID','ownerPointer':f'/SubMissionList/{i}/MainMissionID','missionId':row['MainMissionID']})
    result=defaultdict(list);conflicts=[]
    for path,obj in metadata.items():
        if not path.startswith(('Config/LevelOutput/RuntimeGroup/','Config/LevelOutput/SharedRuntimeGroup/')) or not isinstance(obj,dict):continue
        if obj.get('$type')!='RPG.GameCore.RtLevelGroupInfo':continue
        owner=obj.get('OwnerMainMissionID');target=obj.get('LevelGraph')
        if not isinstance(owner,int) or owner<=0 or not isinstance(target,str) or not target:continue
        foreign=[]
        for task,ptr in objects(metadata.get(target,{})):
            sid=task.get('SubmissionID')
            if task.get('$type','').endswith('.ClientFinishMission') and isinstance(sid,int) and subowners[sid] and owner not in subowners[sid]:
                foreign.append({'pointer':ptr+'/SubmissionID','submissionId':sid,'mainMissionIds':sorted(subowners[sid]),'ownerProofs':subproofs[sid]})
        if foreign:
            conflicts.append({'source':path,'ownerPointer':'/OwnerMainMissionID','missionId':owner,'graphPointer':'/LevelGraph','target':target,'conflictingFinishReferences':foreign})
        else:result[owner].append((path,'/OwnerMainMissionID'))
    return result,conflicts

def submission_performance_branches(metadata, hashes, performances):
    """Read only performances in an exact Started -> finish-success branch.

    The surrounding group may serve several missions. Its other dialogue and
    event handlers never become owned through this relation.
    """
    submissions=defaultdict(list); result=defaultdict(list)
    for path,obj in metadata.items():
        if not path.startswith('Config/Level/Mission/') or not Path(path).name.startswith('MissionInfo_') or not isinstance(obj,dict):continue
        for i,row in enumerate(obj.get('SubMissionList',[])):
            if isinstance(row.get('ID'),int) and isinstance(row.get('MainMissionID'),int):
                submissions[row['ID']].append((path,i,row['MainMissionID']))
    for graph,obj in metadata.items():
        if not graph.startswith('Config/Level/GroupGraph/'):continue
        for branch,ptr in objects(obj):
            predicate=branch.get('Predicate',{})
            if not branch.get('$type','').endswith('.PredicateTaskList') or not predicate.get('$type','').endswith('.ByCompareSubMissionState') or predicate.get('SubMissionState')!='Started':continue
            sid=predicate.get('SubMissionID');tasks=branch.get('SuccessTaskList',[])
            finishes=[i for i,t in enumerate(tasks) if isinstance(t,dict) and t.get('$type','').endswith('.ClientFinishMission') and t.get('SubmissionID')==sid]
            if len(finishes)!=1:continue
            # Nested or foreign finish branches are not promoted wholesale.
            if any(t.get('$type','').endswith('.ClientFinishMission') and t.get('SubmissionID')!=sid for t,_ in objects(tasks)):continue
            for i,task in enumerate(tasks[:finishes[0]]):
                if not isinstance(task,dict) or not task.get('$type','').endswith('.TriggerPerformance') or not isinstance(task.get('PerformanceID'),int):continue
                matches,scope=performance_matches(performances,task['PerformanceID'],task.get('PerformanceType',''))
                if len({r['target'] for r in matches})!=1:continue
                record=matches[0]
                for source,row_index,owner in submissions.get(sid,[]):
                    edge={'kind':'EXPLICIT_SUBMISSION_PERFORMANCE_BRANCH','source':source,'pointer':f'/SubMissionList/{row_index}/ID','submissionId':sid,'missionId':owner,'ownerPointer':f'/SubMissionList/{row_index}/MainMissionID','graphSource':graph,'graphSha256':hashes[graph],'predicatePointer':ptr+'/Predicate','scopePointer':ptr+'/SuccessTaskList','finishPointer':ptr+f'/SuccessTaskList/{finishes[0]}/SubmissionID','performancePointer':ptr+f'/SuccessTaskList/{i}/PerformanceID','performanceId':task['PerformanceID'],'performanceType':task.get('PerformanceType',''),'lookupScope':scope,'tableSource':record['source'],'idPointer':record['idPointer'],'pathPointer':record['pathPointer'],'target':record['target']}
                    result[source].append((record['target'],edge))
    return result

def submission_started_menu_links(metadata, hashes):
    """Follow an explicitly owned mission menu, without assigning its NPC file.

    Both the Started predicate and the direct menu item name the same exact
    sub-mission. Only that item's DialoguePath is traversed. Integer state
    values in unrelated condition tables are not interpreted here.
    """
    submissions=defaultdict(list);result=defaultdict(list)
    for source,obj in metadata.items():
        if not source.startswith('Config/Level/Mission/') or not Path(source).name.startswith('MissionInfo_') or not isinstance(obj,dict):continue
        for i,row in enumerate(obj.get('SubMissionList',[])):
            if isinstance(row.get('ID'),int) and isinstance(row.get('MainMissionID'),int):submissions[row['ID']].append((source,i,row['MainMissionID']))
    for graph,obj in metadata.items():
        if not graph.startswith(('Config/Level/NPCDialogue/','Config/Level/PropDialogue/')):continue
        for branch,ptr in objects(obj):
            predicate=branch.get('Predicate',{})
            if branch.get('$type')!='RPG.GameCore.PredicateTaskList' or predicate.get('$type')!='RPG.GameCore.ByCompareSubMissionState' or predicate.get('SubMissionState')!='Started':continue
            sid=predicate.get('SubMissionID');proofs=submissions.get(sid,[])
            if len({p[2] for p in proofs})!=1:continue
            for j,menu in enumerate(branch.get('SuccessTaskList',[])):
                if not isinstance(menu,dict) or menu.get('$type')!='RPG.GameCore.AddMenuItem' or menu.get('MissionID')!=sid:continue
                target=menu.get('DialoguePath')
                if not isinstance(target,str) or not target.startswith('Config/Level/') or not target.endswith('.json'):continue
                for source,i,owner in proofs:
                    edge={'kind':'EXPLICIT_STARTED_SUBMISSION_MENU','source':source,'pointer':f'/SubMissionList/{i}/ID','ownerPointer':f'/SubMissionList/{i}/MainMissionID','missionId':owner,'submissionId':sid,'graphSource':graph,'graphSha256':hashes[graph],'predicatePointer':ptr+'/Predicate','menuPointer':ptr+f'/SuccessTaskList/{j}','dialoguePathPointer':ptr+f'/SuccessTaskList/{j}/DialoguePath','target':target}
                    result[source].append((target,edge))
    return result

def submission_dialogue_scopes(metadata, hashes):
    """Limit a dialogue source to exact TaskLists containing a matching finish.

    Completion belongs to an exact MissionInfo sub-mission. Other branches of
    a shared NPC or group file are excluded, even if they have Korean rows.
    """
    submissions=defaultdict(list);result=defaultdict(list)
    for source,obj in metadata.items():
        if not source.startswith('Config/Level/Mission/') or not Path(source).name.startswith('MissionInfo_') or not isinstance(obj,dict):continue
        for i,row in enumerate(obj.get('SubMissionList',[])):
            if isinstance(row.get('ID'),int) and isinstance(row.get('MainMissionID'),int):submissions[row['ID']].append((source,i,row['MainMissionID']))
    for target,obj in metadata.items():
        if not target.startswith(('Config/Level/NPCDialogue/','Config/Level/PropDialogue/')):continue
        talk_refs=list(refs(obj))
        for task,ptr in objects(obj):
            if not task.get('$type','').endswith('.ClientFinishMission'):continue
            sid=task.get('SubmissionID');parts=ptr.split('/')
            indexes=[i for i,x in enumerate(parts) if x in ('TaskList','SuccessTaskList','OnSuccess','OnEvent','OnPressedCallback')]
            if not indexes:continue
            scope='/'.join(parts[:indexes[-1]+1])
            scoped=obj
            for component in scope.split('/')[1:]:scoped=scoped[int(component)] if isinstance(scoped,list) else scoped[component]
            scope_ids=sorted({tid for tid,_,_ in refs(scoped)})
            if not scope_ids and not list(path_refs(scoped)) and not any(t.get('$type','').endswith('.TriggerPerformance') and isinstance(t.get('PerformanceID'),int) for t,_ in objects(scoped)):continue
            for source,i,owner in submissions.get(sid,[]):
                finish_proofs=[];valid=True
                for finish,finish_ptr in objects(scoped,scope):
                    if not finish.get('$type','').endswith('.ClientFinishMission'):continue
                    finish_sid=finish.get('SubmissionID');proofs=submissions.get(finish_sid,[])
                    if {p[2] for p in proofs}!={owner}:valid=False;break
                    proof_source,proof_row,_=proofs[0]
                    finish_proofs.append({'finishPointer':finish_ptr+'/SubmissionID','submissionId':finish_sid,'source':proof_source,'sourceSha256':hashes[proof_source],'idPointer':f'/SubMissionList/{proof_row}/ID','ownerPointer':f'/SubMissionList/{proof_row}/MainMissionID','missionId':owner})
                if not valid:continue
                result[source].append((target,{'kind':'EXPLICIT_SUBMISSION_FINISH_SCOPE','source':source,'pointer':f'/SubMissionList/{i}/ID','submissionId':sid,'missionId':owner,'ownerPointer':f'/SubMissionList/{i}/MainMissionID','target':target,'scopePointer':scope,'scopeTalkIds':scope_ids,'finishPointer':ptr+'/SubmissionID','finishOwnershipProofs':finish_proofs,'scopeSourceSha256':hashes[target],'allTalkReferencesInsideScope':all(pointer.startswith(scope+'/') for _,pointer,_ in talk_refs)}))
    return result

def build(archive):
    quests={d['id']:d for p in (SITE/'data/documents').glob('quest-*.json') if (d:=read(p))}
    messages={d['id']:d for p in (SITE/'data/documents').glob('message-*.json') if (d:=read(p))}
    local={}
    for p in (SITE/'data/dialogues').glob('*.json'):
        for row in read(p)['section']['rows']:
            local[row['talk_id']]={**row,'pageId':p.stem,'url':'대사/'+p.stem+'.html#talk-'+str(row['talk_id'])}
    official_path=SITE/'data/official-mission-talks.json'
    official_input=read(official_path) if official_path.exists() else None
    official={row['talk_id']:{k:v for k,v in row.items() if k!='references'} for row in official_input['rows']} if official_input else {}
    assert not set(official).intersection(local),'An official addition must preserve existing Korean rows'
    expected={s['source'] for q in quests.values() for s in q['sections'] if s.get('source')}
    missions=defaultdict(list); files={}; unresolved=[];coverage={};ambiguous=[]
    metadata,hashes,performances=load_metadata(archive)
    producers,consumers=event_refs(metadata)
    ownership_index=mission_ownership_index(metadata)
    group_index,group_conflicts=runtime_group_ownership_index(metadata)
    branch_links=submission_performance_branches(metadata,hashes,performances)
    event_branch_links=submission_started_event_performances(metadata,hashes,performances)
    menu_links=submission_started_menu_links(metadata,hashes)
    dialogue_links=submission_dialogue_scopes(metadata,hashes)
    message_table='ExcelOutput/MessageSectionConfig.json'
    perform_messages={row['ID']:i for i,row in enumerate(metadata.get(message_table,[])) if isinstance(row.get('ID'),int) and row.get('IsPerformMessage') is True}
    for owner,entries in group_index.items():ownership_index[owner].extend(entries)
    folder_sources=defaultdict(list)
    for path in metadata:
        match=re.match(r'(?:Story/(?:Discussion/)?Mission|Config/Level/Mission)/(\d+)(?:/|\.)',path)
        if match:folder_sources['quest-'+match[1]].append(path)
    for mid,quest in quests.items():
        owners={};queue=deque();scope_proofs=defaultdict(list);main_id=int(mid.split('-')[1]);diagnostics=defaultdict(int);unavailable_paths=[]
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
        seen=set();processed_scopes={}
        def scope_pointers(path):
            return sorted({edge['scopePointer'] for edge in scope_proofs[path]}) if owners[path][-1]['kind']=='EXPLICIT_SUBMISSION_FINISH_SCOPE' else []
        def allowed_pointer(path,pointer):
            scopes=scope_pointers(path)
            return not scopes or any(pointer.startswith(scope+'/') for scope in scopes)
        for phase in ('explicit','directory'):
            if phase=='directory':
                for owner in membership:
                    for path in folder_sources['quest-'+str(owner)]:
                        if path not in owners:seed('MISSION_DIRECTORY_CONVENTION',path,owner)
            while queue:
                path=queue.popleft()
                signature=tuple(scope_pointers(path))
                if path in seen and processed_scopes.get(path)==signature:continue
                processed_scopes[path]=signature
                seen.add(path);obj=metadata[path];chain=owners[path]
                links=[(target,{'kind':'EXPLICIT_JSON_PATH','source':path,'pointer':ptr,'target':target}) for target,ptr in path_refs(obj) if allowed_pointer(path,ptr)]
                if chain[0]['kind']=='EXPLICIT_MAIN_MISSION_ID':
                    links.extend((target,edge) for target,edge in branch_links.get(path,[]) if edge['missionId'] in membership)
                    links.extend((target,edge) for target,edge in event_branch_links.get(path,[]) if edge['missionId'] in membership)
                    links.extend((target,edge) for target,edge in menu_links.get(path,[]) if edge['missionId'] in membership)
                    links.extend((target,edge) for target,edge in dialogue_links.get(path,[]) if edge['missionId'] in membership)
                for task,ptr in objects(obj):
                    if not allowed_pointer(path,ptr):continue
                    if path.startswith('Config/Level/Mission/') and Path(path).name.startswith('MissionInfo_') and task.get('MainMissionID') in membership and task.get('FinishType')=='FinishFirstTalkPerformance':
                        for i,pid in enumerate(task.get('ParamIntList',[])):
                            if not isinstance(pid,int):continue
                            records=performances.get(pid,[])
                            if len({r['target'] for r in records})!=1:continue
                            record=records[0]
                            # No type is invented: all eligible table matches
                            # must agree on the exact target path.
                            tables=sorted(n for n in metadata if re.fullmatch(r'ExcelOutput/Performance(?:A|C|D|E|DS|CG|CLD|DLD|DSLD|Video|VideoLD)\.json',n))
                            for table in tables:files[table]=hashes[table]
                            links.append((record['target'],{'kind':'EXPLICIT_MISSION_FINISH_PERFORMANCE','source':path,'pointer':ptr+f'/ParamIntList/{i}','ownerPointer':ptr+'/MainMissionID','missionId':task['MainMissionID'],'finishTypePointer':ptr+'/FinishType','performanceId':pid,'lookupScope':'UNIQUE_CROSS_TYPED_TABLE_TARGET','lookupTables':tables,'tableSource':record['source'],'idPointer':record['idPointer'],'pathPointer':record['pathPointer'],'target':record['target']}))
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
                    if edge.get('graphSource'):files[edge['graphSource']]=hashes[edge['graphSource']]
                    if edge.get('missionSource'):files[edge['missionSource']]=hashes[edge['missionSource']]
                    if target not in metadata:
                        unavailable_paths.append({**edge,'sourceSha256':hashes[path],**({'tableSha256':hashes[edge['tableSource']]} if edge.get('tableSource') else {}),'ownershipSeed':chain[0]})
                        if edge.get('tableSource'):files[edge['tableSource']]=hashes[edge['tableSource']]
                        diagnostics['unavailableReferencedPaths']+=1;continue
                    if edge['kind']=='EXPLICIT_SUBMISSION_FINISH_SCOPE' and edge not in scope_proofs[target]:
                        scope_proofs[target].append(edge)
                        if target in owners and owners[target][-1]['kind']=='EXPLICIT_SUBMISSION_FINISH_SCOPE':queue.append(target)
                    if target not in owners or owners[target][0]['kind']=='MISSION_DIRECTORY_CONVENTION' and chain[0]['kind']!='MISSION_DIRECTORY_CONVENTION' or owners[target][-1]['kind']=='EXPLICIT_SUBMISSION_FINISH_SCOPE' and edge['kind']!='EXPLICIT_SUBMISSION_FINISH_SCOPE' and chain[0]['kind']=='EXPLICIT_MAIN_MISSION_ID':
                        owners[target]=chain+[edge];queue.append(target)
        source_talk_scopes={path:{'pointers':scope_pointers(path),'talkIds':sorted({tid for edge in scope_proofs[path] for tid in edge['scopeTalkIds']}),'proofs':[{**edge,'sourceSha256':hashes[edge['source']]} for edge in scope_proofs[path]]} for path in sorted(seen) if scope_pointers(path)}
        diagnostics['exactTalkReferences']=sum(1 for path in seen for _,ptr,_ in refs(metadata[path]) if allowed_pointer(path,ptr))
        diagnostics['timelineReferences']=sum(1 for path in seen for task,ptr in objects(metadata[path]) if allowed_pointer(path,ptr) and task.get('$type','').endswith('.PlayTimeline'))
        for path in sorted(seen):
            obj=metadata[path];found=[ref for ref in refs(obj) if allowed_pointer(path,ref[1])];files[path]=hashes[path]
            option_ids={task['TalkSentenceID'] for task,_ in objects(obj) if task.get('$type','').endswith('.OptionTalkInfo') and isinstance(task.get('TalkSentenceID'),int)}
            for edge in owners[path]:
                files[edge['source']]=hashes[edge['source']]
                if edge.get('tableSource'):files[edge['tableSource']]=hashes[edge['tableSource']]
            for edge in scope_proofs[path]:
                files[edge['source']]=hashes[edge['source']]
                for proof in edge['finishOwnershipProofs']:files[proof['source']]=hashes[proof['source']]
            existing={r.get('talk_id') for s in quests[mid]['sections'] if s.get('source')==path for r in s['rows']}
            grouped=defaultdict(list)
            for tid,ptr,kind in found: grouped[tid].append({'pointer':ptr,'kind':kind})
            rows=[]
            for tid,pointers in grouped.items():
                if tid in existing: continue
                if tid not in local and tid not in official:
                    unresolved.append({'missionId':mid,'source':path,'talkId':tid,'references':pointers}); continue
                row=local.get(tid) or official[tid]
                conditions=string_case_conditions(obj,pointers) if tid in official else []
                rows.append({**row,'references':pointers,'anchor':'talk-'+str(tid),'displayKind':'선택지' if tid in option_ids else '대사','classification':'EXPLICIT_OPTION_TASK' if tid in option_ids else 'OFFICIAL_KOREAN_TALK_ROW' if tid in official else 'PRESERVED_TALK_ROW',**({'sourceConditions':conditions} if conditions else {})})
            if rows:
                missions[mid].append({'anchor':'supplement-'+sha(path.encode())[:12], 'title':'추가 대사 원문', 'source':path,'sourceSha256':hashes[path],'sourceUrl':f'https://github.com/{REPO}/blob/{COMMIT}/{path}', 'mapping':'EXACT_PUBLIC_STRUCTURE_REFERENCE_TO_PRESERVED_LOCAL_TALK','ownership':[{**edge,'sourceSha256':hashes[edge['source']],**({'tableSha256':hashes[edge['tableSource']]} if edge.get('tableSource') else {})} for edge in owners[path]], 'order':'구조 파일의 참조 순서', 'rows':rows})
        related_documents=[]
        for path in sorted(seen):
            for task,ptr in objects(metadata[path]):
                if not allowed_pointer(path,ptr):continue
                message_id=task.get('MessageSectionID');message_pointer=ptr+'/MessageSectionID';reference_kind='EXPLICIT_MESSAGE_SECTION_ID';message_proof={}
                if path.startswith('Config/Level/Mission/') and Path(path).name.startswith('MissionInfo_') and task.get('MainMissionID') in membership and task.get('FinishType')=='MessageSectionFinish' and task.get('ParamType')=='Equal':
                    message_id=task.get('ParamInt1');message_pointer=ptr+'/ParamInt1';reference_kind='MISSION_FINISH_MESSAGE_SECTION'
                elif path.startswith('Config/Level/Mission/') and Path(path).name.startswith('MissionInfo_') and task.get('MainMissionID') in membership and task.get('FinishType')=='MessagePerformSectionFinish' and task.get('ParamType')=='Equal' and task.get('ParamInt1') in perform_messages:
                    message_id=task['ParamInt1'];message_pointer=ptr+'/ParamInt1';reference_kind='MISSION_FINISH_PERFORM_MESSAGE_SECTION'
                    table_index=perform_messages[message_id];files[message_table]=hashes[message_table]
                    message_proof={'sectionTableSource':message_table,'sectionTableSha256':hashes[message_table],'sectionIdPointer':f'/{table_index}/ID','sectionPerformPointer':f'/{table_index}/IsPerformMessage'}
                key='message-'+str(message_id)
                if isinstance(message_id,int) and key in messages:
                    document=messages[key]
                    related_documents.append({'id':key,'docId':key,'sourceId':key,'originalTableSource':document['source'],'sectionId':document['sections'][0]['anchor'] if document['sections'] else None,'sectionIds':[s['anchor'] for s in document['sections']],'title':document['title'],'url':document['url'],'count':document['count'],'sha256':sha((SITE/'data/documents'/(key+'.json')).read_bytes()),'messageSectionId':message_id,'referenceKind':reference_kind,**message_proof,'referenceSource':path,'referenceSourceSha256':hashes[path],'pointer':message_pointer,'ownership':[{**edge,'sourceSha256':hashes[edge['source']],**({'tableSha256':hashes[edge['tableSource']]} if edge.get('tableSource') else {})} for edge in owners[path]]})
        old_count=sum(bool(r.get('talk_id') and r.get('hash') and r.get('text')) for s in quest['sections'] for r in s['rows']);added_count=sum(len(s['rows']) for s in missions.get(mid,[]));local_count=sum(t in local for path in seen for t,_,_ in refs(metadata[path]))
        reason='LINKED' if old_count+added_count else 'STRUCTURE_UNAVAILABLE' if not seen else 'NO_LOCAL_KOREAN_FOR_EXACT_REFERENCES' if diagnostics['exactTalkReferences'] else 'TIMELINE_IDS_NOT_EXPOSED' if diagnostics['timelineReferences'] else 'NO_EXACT_DIALOGUE_REFERENCE'
        original_choices=sum(r.get('label')=='선택지' and bool(r.get('talk_id') and r.get('hash') and r.get('text')) for s in quest['sections'] for r in s['rows']);supplement_choices=sum(r['displayKind']=='선택지' for s in missions.get(mid,[]) for r in s['rows'])
        missing_primary_story=[ref for ref in unavailable_paths if ref['target'].startswith('Story/') and ref['ownershipSeed']['kind']=='EXPLICIT_MAIN_MISSION_ID']
        missing_reference_story=[ref for ref in unavailable_paths if ref['target'].startswith('Story/') and ref['ownershipSeed']['kind']=='MISSION_DIRECTORY_CONVENTION']
        primary_supplement=sum(len(s['rows']) for s in missions.get(mid,[]) if s['ownership'][0]['kind']=='EXPLICIT_MAIN_MISSION_ID')
        primary_original=sum(bool(r.get('talk_id') and r.get('hash') and r.get('text')) for s in quest['sections'] if owners.get(s.get('source'),[{}])[0].get('kind')=='EXPLICIT_MAIN_MISSION_ID' for r in s['rows'] if s.get('source') not in source_talk_scopes or r.get('talk_id') in source_talk_scopes[s['source']]['talkIds'])
        coverage[mid]={'originalRows':old_count,'originalChoices':original_choices,'originalDialogue':old_count-original_choices,'supplementRows':added_count,'supplementChoices':supplement_choices,'supplementDialogue':added_count-supplement_choices,'primaryOriginalRows':primary_original,'primarySupplementRows':primary_supplement,'primaryRows':primary_original+primary_supplement,'referenceRows':old_count+added_count-primary_original-primary_supplement,'primaryReason':'LINKED' if primary_original+primary_supplement else 'NO_CONFIRMED_PRIMARY_ROWS','primaryCompleteness':'PARTIAL_MISSING_REFERENCED_STRUCTURE' if missing_primary_story else 'NO_MISSING_REFERENCED_STORY_STRUCTURE','missingPrimaryStoryReferences':missing_primary_story,'missingReferenceStoryReferences':missing_reference_story,'unavailablePathReferences':unavailable_paths,'relatedDocuments':related_documents,'sourceTalkScopes':source_talk_scopes,'sourceOwnership':{path:[{**edge,'sourceSha256':hashes[edge['source']],**({'tableSha256':hashes[edge['tableSource']]} if edge.get('tableSource') else {})} for edge in owners[path]] for path in sorted(seen)},'structureFilesReached':len(seen),'localReferences':local_count,'reason':reason,**diagnostics}
    for scenes in missions.values():
        for scene in scenes:
            official_rows=sum(bool(r.get('officialSource')) for r in scene['rows'])
            if official_rows:
                scene['mapping']='EXACT_PUBLIC_STRUCTURE_REFERENCE_TO_OFFICIAL_KOREAN_TALK' if official_rows==len(scene['rows']) else 'EXACT_PUBLIC_STRUCTURE_REFERENCE_TO_MIXED_KOREAN_TALK'
    for conflict in group_conflicts:
        conflict['sourceSha256']=hashes[conflict['source']]
        conflict['targetSha256']=hashes.get(conflict['target'])
        files[conflict['source']]=hashes[conflict['source']]
        if conflict['target'] in hashes:files[conflict['target']]=hashes[conflict['target']]
        for finish in conflict['conflictingFinishReferences']:
            for proof in finish['ownerProofs']:
                proof['sourceSha256']=hashes[proof['source']];files[proof['source']]=hashes[proof['source']]
    missing=sorted(expected-set(files))
    out={'schema':'starrail-mission-dialogue-supplements.v1','evidence':{'repository':REPO,'commit':COMMIT,'archiveSha256':sha(archive.read_bytes()),'dialogueIndexSha256':sha((SITE/'data/dialogue-index.json').read_bytes()),'preservedLocalSources':read(SITE/'data/dialogue-index.json')['evidence']['sources'],'currentInstallationReparse':'UNVERIFIED_FULL_KOREAN_PACK_UNAVAILABLE','structureFiles':files,'method':'Exact MissionInfo MainMissionID and RtLevelGroupInfo OwnerMainMissionID (excluding conflicting finish ownership), JSON paths and unique PerformanceID-to-PerformancePath joins, with separately recorded mission-directory fallback. Exact TalkSentence IDs joined to unchanged local Korean rows.'},'missions':dict(missions),'coverage':coverage,'runtimeGroupOwnershipConflicts':group_conflicts,'ambiguousPerformanceReferences':ambiguous,'unresolvedReferences':unresolved,'missingExistingStructurePaths':missing,'counts':{'localKoreanRows':len(local),'missions':len(missions),'scenes':sum(map(len,missions.values())),'rows':sum(len(s['rows']) for scenes in missions.values() for s in scenes),'structureFiles':len(files),'metadataFilesScanned':len(metadata),'missingStructurePaths':len(missing),'unresolvedReferences':len(unresolved),'coverageMissions':len(coverage)},'limitations':['공개 구조의 참조는 해당 장면에서 사용하는 식별자를 보여준다. 실제 실행 조건과 재생 순서는 별도 자료가 필요하다.','타임라인 내부 자막 중 구조 JSON에 식별자가 없는 대사는 이 연결 범위에 포함되지 않는다.','임무 폴더 관례에 따른 기존 연결과 MainMissionID·명시 경로에 따른 연결은 소유권 근거에서 구분한다.']}
    if official_input:
        out['evidence']['officialTalkAdditions']={'path':'data/official-mission-talks.json','sha256':sha(official_path.read_bytes()),'clientVersion':official_input['evidence']['clientVersion']}
        out['evidence']['method']+=' Newly readable official Korean additions retain their separate client version, original TalkSentenceConfig/TextMap rows and byte spans; existing local rows remain unchanged.'
        out['counts']['officialKoreanRows']=len(official)
    for p in [SITE/'data/mission-dialogue-supplements.json',SITE/'public/mission-dialogue-supplements.json']:
        p.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),'utf8')
    print(json.dumps(out['counts']))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);a=p.parse_args();build(a.archive)
