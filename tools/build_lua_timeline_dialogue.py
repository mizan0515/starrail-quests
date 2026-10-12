"""Project verified static Lua arguments into screen-text readers."""
import argparse, hashlib, json, math
from collections import Counter
from pathlib import Path

SITE=Path(__file__).resolve().parents[1]
SCHEMA='starrail-lua-timeline-dialogue.v1'
FIELDS=('text_sub_title','text_main_title','text_bottom_title','text_bottom_content')
def read(p):return json.loads(Path(p).read_text('utf8'))
def digest(b):return hashlib.sha256(b).hexdigest()
def require(v,msg):
 if not v:raise ValueError(msg)
def pointer(o,p):
 for part in p.split('/')[1:]:o=o[int(part)] if isinstance(o,list) else o[part.replace('~1','/').replace('~0','~')]
 return o
def write(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n').encode())
def safe_numbers(value):
 if type(value)is int and abs(value)>=2**53:return str(value)
 if isinstance(value,dict):return {k:safe_numbers(v) for k,v in value.items()}
 if isinstance(value,list):return [safe_numbers(v) for v in value]
 return value

def project(audit_path,cohort_path):
 audit_bytes=Path(audit_path).read_bytes();audit=json.loads(audit_bytes);cohort=read(cohort_path)
 require(audit['schema']=='starrail-fate-luau-screen-delta.v1','Unsupported Lua argument audit')
 require(audit['cohortFrozenSha256']==digest(Path(cohort_path).read_bytes()),'Frozen argument cohort changed')
 frozen=set(cohort['starrail']['ids']);require(len(frozen)==cohort['starrail']['count'],'Frozen ID count changed')
 require(audit['counts']['readableOccurrences']==len(audit['readableDelta']) and audit['counts']['readableUniqueIDs']==len(audit['joins']),'Partial argument audit')
 for name,h in audit['sourceGuards'].items():require(digest((Path(audit_path).parent/name).read_bytes())==h,'Native/Lua source guard changed: '+name)
 joins={};files={}
 for j in audit['joins']:
  require(j['status']=='EXACT_KOREAN_LOCAL_HASH_TEXT_SPEAKER_VOICE_PASS' and all(j['checks'].values()),'Korean argument join incomplete')
  tid=int(j['talkID']);require(0<tid<2**32 and str(tid) not in joins,'Invalid/duplicate Talk ID')
  source=j['preservedSource'];require(source['file'].startswith('data/dialogues/') and '..' not in source['file'].split('/'),'Unsafe preserved source')
  if source['file'] not in files:
   body=(SITE/source['file']).read_bytes();files[source['file']]=(digest(body),json.loads(body))
  h,obj=files[source['file']];row=pointer(obj,source['pointer'])
  require(h==source['sha256'] and row==j['preservedRow'] and row['talk_id']==tid,'Original argument source changed')
  require(all(str(row[k])==str(j[k if k not in ('hash','speaker_hash') else {'hash':'textHash','speaker_hash':'speakerHash'}[k]]) for k in ('text','speaker','hash','speaker_hash','voice')),'Original argument fields changed')
  joins[str(tid)]={'preservedSource':source,'raw':j['raw'],'text':j['text'],'textHash':str(j['textHash']),'speakerHash':str(j['speakerHash']),'voice':j['voice'],'tableRow':j['tableRow'],'tableRecord':j['tableRecord'],'textRecord':j['textRecord'],'speakerRecord':j['speakerRecord']}
 aliases=read(SITE/'data/aliases.json');scenes={};sources={};used=set()
 for r in audit['readableDelta']:
  require(r['role']=='SCREEN_TEXT','Lua argument classified as speech')
  route=r['route'];key=route['rootContainer']['key'];sid='lua-timeline-'+digest(key.encode())[:16]
  clip=route['clipObject'];track=route['trackObject'];root=route['rootObject'];timing=route['timelineClip'];token=r['uiParamTokenProof'];slot=r['captionSlot'];tid=int(r['joinedTalkID'])
  require(clip['class']=='ShowFateShowCaptionDialogClip' and route['clipEOF']==clip['byteSize'] and route['trackEOF']==track['byteSize'] and route['rootEOF']==root['byteSize'],'Incomplete native clip/track/root')
  require(1<=slot<=4 and r['uiField']==FIELDS[slot-1] and token['tokenIndex']==slot-1,'Unknown screen slot')
  parts=token['raw'].split('|');require(len(parts)==4 and parts[slot-1]==token['token'] and token['token'].isascii() and token['token'].isdigit() and int(token['token'])==tid and str(tid) in joins,'Argument token/domain differs')
  require(token['serializedField']['value']==token['raw'] and route['serializedValues']['UIParam']==token['raw'],'Native parameter differs')
  native=r['nativeConsumerProof'];require(native['lookupClass']=='RPG.GameCore.TalkSentenceConfigExcelTable' and native['lookupMethod']=='GetData' and native['textField']=='TalkSentenceText' and native['runtimeOffset']==40 and native['copyBytes']==16 and native['screenCall']=='SafeSetTextID','Native argument consumer domain differs')
  require(r['luaConsumerProof']['call']['function'][-1]=='SafeSetTextID','Lua screen consumer differs')
  require(timing['m_Asset']['fileID']==0 and str(timing['m_Asset']['pathID'])==clip['pathID'] and route['parentRouteTalkToRoot'][0]==track['pathID'] and route['parentRouteTalkToRoot'][-1]==root['pathID'],'Native object route differs')
  require(all(type(timing[k]) in (int,float) and math.isfinite(timing[k]) for k in ('m_Start','m_Duration')),'Invalid clip time')
  unique=(key,clip['pathID'],slot);require(unique not in used,'Duplicate caption slot');used.add(unique)
  owners=[]
  for mid in r['missions']:
   canonical=aliases.get(mid,mid);doc=read(SITE/'data/documents'/(canonical+'.json'));require(mid in doc.get('missionParts',[doc['id']]),'Argument mission membership changed');owners.append({'mission':mid,'canonicalMission':canonical,'title':doc['title']})
  refs=[]
  for ref in r.get('sourceReferences',[]):
   index=str(ref['sourceIndex']);source=audit['ownerProofs'][index]
   sources[index]={k:source[k] for k in ('mission','logicalJsonPath','nameHash','entrySha256','consumedBytes','ownerChain','ownerSourceChecks','catalogMatches')}
   item={'sourceIndex':index,'pointer':ref['pointer'],'fieldSpan':ref['timelineFieldByteProof'],'context':ref['context']}
   if item not in refs:refs.append(item)
  require(bool(refs)==bool(owners),'Owner/typed call proof completeness differs')
  receipt=r['sourceReceipt'];public_receipt={k:receipt[k] for k in ('blockFile','blockSha256','offset','cab','cabSha256')}
  if sid not in scenes:
   scenes[sid]={'id':sid,'kind':'LUA_ARGUMENT_SCREEN_TEXT','title':joins[str(tid)]['text'],'source':key,'ownerStatus':'ONE_EXPLICIT_OWNER' if len({o['canonicalMission'] for o in owners})==1 else 'MULTIPLE_EXPLICIT_OWNERS' if owners else 'UNOWNED_NATIVE_TIMELINE','owners':owners,'rows':[],'proof':{'receipt':public_receipt,'root':root,'container':route['rootContainer'],'references':refs}}
  scene=scenes[sid];require(scene['owners']==owners and scene['proof']['receipt']==public_receipt,'Argument scene ownership/receipt differs')
  for ref in refs:
   if ref not in scene['proof']['references']:scene['proof']['references'].append(ref)
  scene['rows'].append({'talkId':tid,'role':'SCREEN_TEXT','slot':slot,'uiField':r['uiField'],'anchor':f'lua-screen-{tid}-{slot}','start':timing['m_Start'],'duration':timing['m_Duration'],'object':clip,'track':track,'trackClipIndex':route['trackClipIndex'],'parentRoute':route['parentRouteTalkToRoot'],'argument':token,'luaConsumer':r['luaConsumerProof'],'nativeConsumer':native})
 for scene in scenes.values():require([r['slot'] for r in scene['rows']]==[1,2,3,4],'Incomplete four-field screen')
 result={'schema':SCHEMA,'evidence':{'auditSha256':digest(audit_bytes),'frozenCohortSha256':digest(Path(cohort_path).read_bytes()),'officialKorean':audit['officialKorean'],'sourceGuards':audit['sourceGuards'],'installedVersion':'UNVERIFIED'},'joins':joins,'sourceProofs':sources,'scenes':list(scenes.values()),'counts':{'scenes':len(scenes),'rows':len(used),'distinctTalkIds':len(joins),'frozenIds':len(set(map(int,joins))&frozen),'roles':{'SCREEN_TEXT':len(used)}}}
 body=json.dumps(result,ensure_ascii=False)
 require(not any(v in body for v in ('D:/','D:\\\\','C:/','.codex-work','source_objects_folder','inventory.json')),'Private source path in projection')
 return safe_numbers(result)

def extend_attribution(result,prior_cohort_path=None):
 attr_path=SITE/'data/deep-dialogue-attribution.json';attr=read(attr_path)
 # Only this overlay owns these URLs; retain every predecessor link unchanged.
 for tid,links in attr['readerLinks'].items():attr['readerLinks'][tid]=[r for r in links if not r['url'].startswith('대화/연출-lua-timeline-')]
 for scene in result['scenes']:
  for row in scene['rows']:
   attr['readerLinks'].setdefault(str(row['talkId']),[]).append({'url':'대화/연출-'+scene['id']+'.html#'+row['anchor'],'kind':'연출 화면의 문구','title':scene['title'],'source':scene['source'],'role':'SCREEN_TEXT'})
 attr['timelineReaderIds']=sorted(int(tid) for tid,links in attr['readerLinks'].items() if links)
 attr['counts']['timelineReaderIds']=len(attr['timelineReaderIds']);attr['counts']['links']=sum(len(v) for v in attr['readerLinks'].values())
 attr['counts']['luaScreenReaderIds']=len(result['joins']);attr['counts']['luaFrozenAttributedIds']=result['counts']['frozenIds']
 if prior_cohort_path:
  prior_bytes=Path(prior_cohort_path).read_bytes();require(digest(prior_bytes)==attr['evidence']['frozenCohortSha256'],'Predecessor cohort identity differs')
  prior=set(json.loads(prior_bytes)['starrail']['ids']);attr['counts']['frozenTimelineAttributedIds']=len(prior&set(attr['timelineReaderIds']))
 attr['evidence']['luaTimelineSha256']=digest((SITE/'data/lua-timeline-dialogue.json').read_bytes());write(attr_path,attr)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--audit',required=True,type=Path);p.add_argument('--cohort',required=True,type=Path);p.add_argument('--prior-cohort',type=Path);a=p.parse_args()
 if a.prior_cohort:require(digest(a.prior_cohort.read_bytes())==read(SITE/'data/deep-dialogue-attribution.json')['evidence']['frozenCohortSha256'],'Predecessor cohort identity differs')
 result=project(a.audit,a.cohort);write(SITE/'data/lua-timeline-dialogue.json',result);extend_attribution(result,a.prior_cohort);print(json.dumps(result['counts'],ensure_ascii=False))
