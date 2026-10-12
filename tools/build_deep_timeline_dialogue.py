"""Project verified native uses; preserve originals and existing reader URLs."""
import argparse, hashlib, json, math
from collections import Counter, defaultdict
from pathlib import Path

SITE=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf8'))
def require(x,msg):
 if not x:raise ValueError(msg)
def pointer(o,p):
 for k in p.split('/')[1:]:o=o[int(k)] if isinstance(o,list) else o[k.replace('~1','/').replace('~0','~')]
 return o

def project(audit_path,cohort_path,native_path=None,delta_paths=()):
 audit=read(audit_path);cohort=read(cohort_path);frozen=set(cohort['starrail']['ids'])
 for delta_path in delta_paths:
  delta=read(delta_path);require(delta['status'] in ('CLOSED_MINIMUM_CLIP_REPAIR_DELTA','CLOSED_UNOWNED_TYPED_BP_DELTA'),'Incomplete typed delta')
  require(delta['officialKorean']==audit['officialKorean'] and delta['frozenCohortSha256']==audit['frozenCohortSha256'],'Delta input domain drift')
  joins={j['talkID']:j for j in audit['joins']}
  for j in delta['joins']:
   if j['talkID'] in joins:require(j['preservedSource']==joins[j['talkID']]['preservedSource'] and j['status']==joins[j['talkID']]['status'],'Delta Korean join collision')
   else:audit['joins'].append(j)
  indices=(len(audit['occurrences']),len(audit['optionReferences']));audit['occurrences'].extend(delta['occurrences']);audit['optionReferences'].extend(delta['optionReferences'])
  timelines={t['timelineName']:t for t in audit['timelines']}
  for t in delta['timelines']:
   updated={**t,'occurrenceIndices':[i+indices[0] for i in t['occurrenceIndices']],'optionIndices':[i+indices[1] for i in t['optionIndices']]}
   if t['timelineName'] in timelines:
    old=timelines[t['timelineName']];require(old['rootObject']==t['rootObject'] and old['ownerStatus']==t['ownerStatus'],'Delta root/owner differs');old['occurrenceIndices'].extend(updated['occurrenceIndices']);old['optionIndices'].extend(updated['optionIndices'])
   else:audit['timelines'].append(updated)
  for n,proof in delta['sourceProofs'].items():
   if n in audit['sourceProofs']:require(proof==audit['sourceProofs'][n],'Delta source index collision')
   else:audit['sourceProofs'][n]=proof
 require(len(frozen)==80533,'Frozen cohort drift')
 require(audit['status']!='PARTIAL_STREAM_SNAPSHOT','Unfinished audit')
 aliases=read(SITE/'data/aliases.json');joined={};files={}
 for j in audit['joins']:
  if j['status']!='EXACT_OFFICIAL_KOREAN_PRESERVED_AGREEMENT':continue
  p=j['preservedSource'];f=SITE/p['file']
  if p['file'] not in files:files[p['file']]=(sha(f),read(f))
  digest,obj=files[p['file']];r=pointer(obj,p['pointer'])
  require(digest==p['sha256'] and r==j['preservedRow'],'Preserved source drift')
  require(all(j['versionAgreementChecks'].values()),'Version domain disagreement')
  require(r['text']==j['text'] and str(r['hash'])==j['hash'] and str(r['speaker_hash'])==j['speakerHash'] and r.get('voice',0)==j['voice'],'Korean join disagreement')
  joined[str(j['talkID'])]={'preservedSource':p,'raw':j['raw'],'speakerRaw':j['speakerRaw'],
   'tableOffset':j['tableRecord']['_offset'],'tableEnd':j['tableRecord']['_end'],
   'textOffset':j['textRecord']['offset'],'textEnd':j['textRecord']['end']}
 old_objects=set();links=defaultdict(list);seen_old_ids=set()
 for name in ('timeline-mission-dialogue.json','native-timeline-mission-dialogue.json'):
  old=read(SITE/'data'/name)
  for mid,scenes in old['missions'].items():
   for s in scenes:
    for i,r in enumerate(s['rows']):
     if r.get('timelineClip'):old_objects.add((s['source'],str(r['timelineClip']['pathID'])))
     tid=r['talk_id'];seen_old_ids.add(tid)
     links[str(tid)].append({'url':'문서/'+mid+'.html#'+s['anchor']+'-row-'+str(i+1),'kind':'임무의 연출 원문','title':s['title'],'source':s['source'],'role':'NATIVE_CHOICE' if r.get('label')=='선택지' else 'SPOKEN'})
    for r in s.get('optionReferences',[]):
     old_objects.add((s['source'],str(r['pathID'])));seen_old_ids.add(r['talk_id'])
     links[str(r['talk_id'])].append({'url':'문서/'+mid+'.html#'+s['anchor'],'kind':'연출 설정의 선택지 참조','title':s['title'],'source':s['source'],'role':'NON_SPOKEN_OPTION_REFERENCE'})
 scenes=[];used_joins=set();used_sources=set();accepted_keys=set()
 for t in audit['timelines']:
  occurrences=[audit['occurrences'][i] for i in t['occurrenceIndices']]+[audit['optionReferences'][i] for i in t['optionIndices']]
  rows=[];repeat=Counter();source_refs={};receipt=None
  for r in sorted(occurrences,key=lambda r:(r['timelineClip']['m_Start'],r['trackObject']['pathID'],r['trackClipIndex'])):
   key=(t['timelineName'],str(r['sourceObject']['pathID']))
   if key in old_objects:continue
   unique=key+(str(r['trackObject']['pathID']),r['trackClipIndex'])
   require(unique not in accepted_keys,'Duplicate exact native occurrence');accepted_keys.add(unique)
   tid=r['talkID'];require(str(tid) in joined,'Missing exact Korean join')
   obj=r['sourceObject'];require(r['assetEOF']==obj['byteSize'],'Object EOF differs')
   field_name={'PlaySimpleTalkClip':'PlaySimpleTalkClip.Config.TalkSentenceID','BPTalkClip':'BPTalkClip.TalkSentenceID','ScreenTransferTextClip':'ScreenTransferTextClip.SentenceID','SimpleTalkMarkerClip':'SimpleTalkMarkerClip.ReferenceOptionTalkID'}.get(r['assetClass'])
   field=[f for f in r['assetFields'] if f['field']==field_name and f['value']==tid]
   require(len(field)==1,'Typed ID field missing or ambiguous');field=field[0]
   require(0<=field['span'][0]<field['span'][1]<=obj['byteSize'],'ID span outside object')
   clip=r['timelineClip'];require(all(type(clip[k]) in (int,float) and math.isfinite(clip[k]) for k in ('m_Start','m_Duration')) and clip['m_Start']>=0 and clip['m_Duration']>0,'Invalid clip timing')
   require(str(clip['m_Asset']['pathID'])==str(obj['pathID']) and clip['m_Asset']['fileID']==0,'Clip PPtr differs')
   role=r['role'];require(role in ('SPOKEN','SCREEN_TEXT','NON_SPOKEN_OPTION_REFERENCE'),'Unsupported role')
   repeat[tid]+=1;anchor='talk-'+str(tid)+'-'+str(repeat[tid])
   refs=[]
   for ref in r['sourceReferences']:
    n=str(ref['sourceIndex']);used_sources.add(n)
    k=(n,ref['pointer']);source_refs[k]={'sourceIndex':n,'pointer':ref['pointer'],'fieldSpan':ref['timelineFieldByteProof'],'context':ref['context']};refs.append(n)
   rows.append({'talkId':tid,'role':role,'anchor':anchor,'start':clip['m_Start'],'duration':clip['m_Duration'],
    'object':{k:obj[k] for k in ('pathID','class','sha256','byteStart','byteSize')},'idField':field,
    'track':{k:r['trackObject'][k] for k in ('pathID','class','sha256','byteStart','byteSize')},
    'trackClipIndex':r['trackClipIndex'],'parentRoute':r['parentRouteTalkToRoot'],'sourceIndices':refs,
    'optionReferences':r.get('typedSameSourceOptionReferences',[])})
   used_joins.add(str(tid));receipt={k:r['sourceReceipt'][k] for k in ('blockFile','sourceBlockSha256','bundleOffset','bundleBytes','cabName','cabSha256')}
  if not rows:continue
  sid='timeline-'+hashlib.sha256(t['timelineName'].encode()).hexdigest()[:16]
  mids=t.get('missions') or ([t['mission']] if t.get('mission') else [])
  owners=[]
  for mid in mids:
   target=aliases.get(mid,mid);d=read(SITE/'data/documents'/(target+'.json'))
   require(mid in d.get('missionParts',[d['id']]),'Owner is not a preserved mission part')
   owners.append({'mission':mid,'canonicalMission':target,'title':d['title']})
  speakers=[]
  for r in rows:
   p=joined[str(r['talkId'])]['preservedSource'];speaker=pointer(files[p['file']][1],p['pointer'])['speaker']
   if speaker and speaker!='화자 미지정' and speaker not in speakers:speakers.append(speaker)
  title=' · '.join(speakers[:3]) or '화면 문구와 선택지'
  scene={'id':sid,'title':title,'source':t['timelineName'],'ownerStatus':t['ownerStatus'],'owners':owners,'rows':rows,'proof':{'receipt':receipt,'root':t['rootObject'],'container':t['directRootContainer'],'references':list(source_refs.values())}}
  scenes.append(scene)
  for r in rows:links[str(r['talkId'])].append({'url':'대화/연출-'+sid+'.html#'+r['anchor'],'kind':'연출의 대사와 문구','title':title,'source':scene['source'],'role':r['role']})
 if native_path:
  native=read(native_path)
  for tid,j in native['joins'].items():
   p=j['preservedSource'];f=SITE/p['file']
   if p['file'] not in files:files[p['file']]=(sha(f),read(f))
   digest,obj=files[p['file']];r=pointer(obj,p['pointer']);require(digest==p['sha256'] and all(r[k]==j[k] for k in ('talk_id','text','hash','speaker_hash','voice')),'Native choice Korean source drift')
   joined.setdefault(tid,{'preservedSource':p,'raw':r['text'],'edition':'PRESERVED_LOCAL'});used_joins.add(tid)
  for s in native['scenes']:
   owners=[]
   for o in s['owners']:
    require(o['ownerExactValidation']=='PASS','Native choice owner unchecked')
    mid=o['mission'];target=aliases.get(mid,mid);d=read(SITE/'data/documents'/(target+'.json'));require(mid in d.get('missionParts',[d['id']]),'Native choice membership drift')
    owners.append({'mission':mid,'canonicalMission':target,'title':d['title'],'ownerChain':o['ownerChain']})
   proof=s['proof'];descriptor=proof['descriptor'];require(proof['wholeFieldEOF']==descriptor['catalogMatches'][0]['length'],'Native choice EOF incomplete')
   safe_proof={k:proof[k] for k in ('kind','descriptor','entrySha256','wholeFieldEOF','fields','fieldSpans')};safe_proof['pack']={k:v for k,v in proof['pack'].items() if k!='path'}
   scene={**s,'kind':'NATIVE_CHOICES','ownerStatus':'ONE_EXPLICIT_OWNER' if len({o['canonicalMission'] for o in owners})==1 else 'MULTIPLE_EXPLICIT_OWNERS','owners':owners,'proof':safe_proof}
   scenes.append(scene)
   for r in s['rows']:links[str(r['talkId'])].append({'url':'대화/연출-'+s['id']+'.html#'+r['anchor'],'kind':'연출 설정의 선택지','title':s['title'],'source':s['source'],'role':r['role']})
 proofs={n:audit['sourceProofs'][n] for n in sorted(used_sources)}
 result={'schema':'starrail-deep-timeline-dialogue.v1','evidence':{'auditSha256':sha(audit_path),'deltaSha256':[sha(p) for p in delta_paths],'nativeChoiceSha256':sha(native_path) if native_path else None,'frozenCohortSha256':sha(cohort_path),'officialKorean':audit['officialKorean'],'installedVersion':'UNVERIFIED'},'joins':{k:joined[k] for k in sorted(used_joins,key=int)},'sourceProofs':proofs,'scenes':scenes,
  'counts':{'scenes':len(scenes),'rows':sum(len(s['rows']) for s in scenes),'distinctTalkIds':len(used_joins),'roles':dict(Counter(r['role'] for s in scenes for r in s['rows'])),'preexistingTypedReaderIds':len(seen_old_ids)}}
 attribution={'schema':'starrail-deep-dialogue-attribution.v1','evidence':{'frozenCohortSha256':sha(cohort_path),'inputAttributionSha256':cohort['starrail']['sha256'],'deepTimelineSha256':hashlib.sha256((json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n').encode()).hexdigest()},'timelineReaderIds':sorted(map(int,links)), 'readerLinks':dict(links),'counts':{'timelineReaderIds':len(links),'frozenTimelineAttributedIds':len(set(map(int,links))&frozen),'links':sum(map(len,links.values()))}}
 return result,attribution

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--audit',required=True,type=Path);p.add_argument('--cohort',required=True,type=Path);p.add_argument('--native-choices',type=Path);p.add_argument('--delta',type=Path,action='append',default=[]);a=p.parse_args()
 result,attribution=project(a.audit,a.cohort,a.native_choices,a.delta);write(SITE/'data/deep-timeline-dialogue.json',result);write(SITE/'data/deep-dialogue-attribution.json',attribution);print(json.dumps(result['counts'],ensure_ascii=False))
