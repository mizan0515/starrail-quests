"""Portable original-metadata fixture: reject incorrect mission ownership."""
import argparse,copy,hashlib,json,pathlib,sys

def fixture_hashes(metadata):
 return {p:hashlib.sha256(json.dumps(o,ensure_ascii=False,separators=(',',':')).encode()).hexdigest() for p,o in metadata.items()}

def main():
 default_root=pathlib.Path(__file__).resolve().parents[1]
 parser=argparse.ArgumentParser();parser.add_argument('--site',type=pathlib.Path,default=default_root);parser.add_argument('--fixture',type=pathlib.Path);parser.add_argument('--output',type=pathlib.Path)
 args=parser.parse_args();sys.path.insert(0,str(args.site/'tools'))
 from build_mission_dialogue_supplements import submission_started_event_performances,event_refs
 from verify_mission_dialogue_supplements import verify_started_event_branch
 fixture=json.loads((args.fixture or args.site/'tools/fixtures/started-event-branch.json').read_text('utf8'))
 assert fixture['schemaVersion']=='started-event-branch-fixture.v1'
 metadata=fixture['metadata'];hashes=fixture_hashes(metadata);assert hashes==fixture['fixtureHashes']
 MI='Config/Level/Mission/8021201/MissionInfo_8021201.partial.json';GRAPH='Config/Level/NPCDialogue/P20003/F20003001_G151/DialogueMain_F20003001_G151_N400001.json';MISSION='Config/Level/Mission/8021201/Mission_802120101.json';ACT='Config/Level/Mission/8021201/Act/Act802120101.json';TABLE='ExcelOutput/PerformanceE.json'
 assert len(metadata[TABLE])==1 and fixture['attribution']['sources'][TABLE]['originalRowPointer']=='/11509'
 assert metadata[TABLE][0]['PerformanceID']==802120101 and metadata[TABLE][0]['PerformancePath']==ACT
 performances={802120101:[{'source':TABLE,'idPointer':'/0/PerformanceID','pathPointer':'/0/PerformancePath','target':ACT}]}
 def branch(m):return m[GRAPH]['OnStartSequece'][0]['TaskList'][1]['TaskList'][0]
 def select(m):return submission_started_event_performances(m,fixture_hashes(m),performances)
 links=select(metadata);assert len(links[MI])==1 and links[MI][0][0]==ACT
 edge=links[MI][0][1];assert edge['submissionId']==802120101 and edge['missionId']==8021201
 assert edge['scopePointer']=='/OnStartSequece/0/TaskList/1/TaskList/0/SuccessTaskList'
 proof={**edge,'tableSha256':hashes[TABLE]};verify_started_event_branch(proof,{'structureFiles':hashes},metadata,event_refs(metadata,all_names=True))
 ids=[t['TalkSentenceID'] for t in metadata[ACT]['OnStartSequece'][0]['TaskList'][2]['SimpleTalkList']]
 assert ids==fixture['expected']['talkIds']==[821210102,821210104,821210105]
 def completed(m):branch(m)['Predicate']['SubMissionState']='Completed'
 def foreign_sid(m):branch(m)['Predicate']['SubMissionID']=999000001
 def default_call(m):m[GRAPH]['OnStartSequece'][0]['TaskList'][1]['DefaultTask'].insert(0,branch(m)['SuccessTaskList'].pop(0))
 def nested_call(m):branch(m)['SuccessTaskList'][0]={'$type':'RPG.GameCore.PredicateTaskList','Predicate':{'$type':'RPG.GameCore.ByCompareSubMissionState','SubMissionID':999000001,'SubMissionState':'Started'},'SuccessTaskList':[branch(m)['SuccessTaskList'][0]]}
 def wrong_container(m):m[GRAPH]['OnStartSequece'][0]['TaskList'][1]['$type']='RPG.GameCore.FinishLevelGraph'
 def foreign_owner(m):m[MI]['SubMissionList'].append({**m[MI]['SubMissionList'][0],'MainMissionID':9990000})
 def second_receiver(m):m['Config/Level/Mission/foreign.json']=copy.deepcopy(m[MISSION])
 def foreign_sender(m):m['Config/Level/NPCDialogue/foreign.json']={'OnStartSequece':[{'TaskList':[{'$type':'RPG.GameCore.TriggerCustomString','CustomString':{'Value':'Talk_802120101'}}]}]}
 def wrong_finish(m):m[MISSION]['OnStartSequece'][0]['TaskList'][1]['Key']='Mission_802120102'
 def wrong_path(m):m[MI]['SubMissionList'][0]['MissionJsonPath']=ACT
 def event_before_call(m):branch(m)['SuccessTaskList'][:2]=list(reversed(branch(m)['SuccessTaskList'][:2]))
 def nested_default_branch(m):
  switch=m[GRAPH]['OnStartSequece'][0]['TaskList'][1];b=copy.deepcopy(branch(m));b['$type']='RPG.GameCore.PredicateTaskList';switch['TaskList']=[];switch['DefaultTask']=[b]
 mutations=[]
 for change in [completed,foreign_sid,default_call,nested_call,wrong_container,foreign_owner,second_receiver,foreign_sender,wrong_finish,wrong_path,event_before_call,nested_default_branch]:
  m=copy.deepcopy(metadata);change(m);got=select(m)
  assert not any(target==ACT for values in got.values() for target,_ in values),'Selector accepted '+change.__name__
  if change in [completed,foreign_sid,foreign_owner,wrong_finish,wrong_path,event_before_call,second_receiver,foreign_sender,nested_default_branch]:
   h=fixture_hashes(m);forged={**proof,'graphSha256':h[GRAPH],'missionSha256':h[MISSION],'tableSha256':h[TABLE]}
   if change==nested_default_branch:
    for key in ['predicatePointer','scopePointer','performancePointer','sendPointer']:forged[key]=forged[key].replace('/TaskList/0/','/DefaultTask/0/',1)
    forged['eventProducers'],forged['eventConsumers']=event_refs(m,all_names=True)[0][edge['event']],event_refs(m,all_names=True)[1][edge['event']]
   try:verify_started_event_branch(forged,{'structureFiles':h},m,event_refs(m,all_names=True))
   except (AssertionError,KeyError,IndexError):pass
   else:raise AssertionError('Verifier accepted '+change.__name__)
  print(change.__name__+': REJECTED_AS_REQUIRED');mutations.append({'name':change.__name__,'status':'REJECTED_AS_REQUIRED'})
 report={'status':'PASS','scope':'portable actual8021201metadata fixture; ownership and conditional negative mutations, not whole corpus coverage','sourceAttribution':fixture['attribution'],'fixtureHashes':hashes,'exactProof':proof,'expectedTalkIds':ids,'mutations':mutations}
 if args.output:args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
 print(json.dumps({'status':'PASS','baselineMission':8021201,'exactTalkIds':ids,'mutationsRejected':len(mutations)}))

if __name__=='__main__':main()
