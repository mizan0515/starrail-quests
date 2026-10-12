"""Append whole native choice sources without rebuilding predecessor readers."""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(b):return hashlib.sha256(b).hexdigest()
def require(v,msg):
 if not v:raise ValueError(msg)
def at(o,p):
 for k in p.split('/')[1:]:o=o[int(k)] if isinstance(o,list) else o[k.replace('~1','/').replace('~0','~')]
 return o
def safe(v):
 if type(v)is int and abs(v)>=2**53:return str(v)
 if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
 if isinstance(v,list):return [safe(x) for x in v]
 return v
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n').encode())
def extend(projection_path,cohort_path,prior_cohort_path):
 delta_bytes=Path(projection_path).read_bytes();delta=json.loads(delta_bytes);dh=sha(delta_bytes)
 require(delta['schema']=='starrail-native-choice-readable-projection.v1' and not delta['unreadableOptions'],'Incomplete native choice delta')
 path=SITE/'data/deep-timeline-dialogue.json';original=path.read_bytes();deep=json.loads(original)
 attr_path=SITE/'data/deep-dialogue-attribution.json';attr=read(attr_path)
 prior_bytes=Path(prior_cohort_path).read_bytes();require(sha(prior_bytes)==attr['evidence']['frozenCohortSha256'],'Predecessor cohort differs');prior=set(json.loads(prior_bytes)['starrail']['ids'])
 if any(item['sha256']==dh for item in deep['evidence'].get('nativeChoiceDeltas',[])):return deep['counts']
 cohort=read(cohort_path);frozen=set(cohort['starrail']['ids']);require(len(frozen)==cohort['starrail']['count'],'Frozen cohort differs')
 require(sha(original)==delta['evidence']['previousDeepArtifactSha256'] or deep['evidence'].get('nativeChoiceDeltas'),'Predecessor native reader changed')
 aliases=read(SITE/'data/aliases.json');known={s['id'] for s in deep['scenes']};files={};new_scenes=[];links=[]
 for tid,j in delta['joins'].items():
  source=j['preservedSource'];require(source['file'].startswith('data/dialogues/') and '..' not in source['file'].split('/'),'Unsafe choice original')
  if source['file']not in files:
   raw=(SITE/source['file']).read_bytes();files[source['file']]=(sha(raw),json.loads(raw))
  h,obj=files[source['file']];row=at(obj,source['pointer']);require(h==source['sha256'] and row['talk_id']==int(tid),'Choice original changed')
  require(all(str(row[k])==str(j[k]) for k in ('text','speaker','hash','speaker_hash','voice')),'Choice Korean fields changed')
  require(tid not in deep['joins'],'New choice overlaps predecessor ID')
  deep['joins'][tid]={'preservedSource':source,'raw':j['raw'],'edition':'PRESERVED_LOCAL','speakerRaw':j.get('speakerRaw',''),'currentOfficialSource':safe(j['currentOfficialSource'])}
 for s in delta['scenes']:
  require(s['id'] not in known and s['owners'],'Missing/duplicate owned choice reader');known.add(s['id']);owners=[]
  proof=s['proof'];descriptor=proof['descriptor'];require(proof['wholeFieldEOF']==descriptor['catalogMatches'][0]['length'],'Whole choice source incomplete')
  for o in s['owners']:
   require(o['ownerExactValidation']=='PASS','Choice owner unchecked');mid=o['mission'];canonical=aliases.get(mid,mid);doc=read(SITE/'data/documents'/(canonical+'.json'));require(mid in doc.get('missionParts',[doc['id']]),'Choice mission membership changed')
   owners.append({'mission':mid,'canonicalMission':canonical,'title':doc['title'],'ownerChain':o['ownerChain']})
  for r in s['rows']:
   require(r['role']=='NATIVE_CHOICE' and r['parentTaskType']=='RPG.GameCore.PlayOptionTalk' and r['option']['$type']=='RPG.GameCore.OptionTalkInfo' and r['option']['TalkSentenceID']==r['talkId'],'Unknown option consumer')
   require(at(proof['fields'],r['proof']['pointer'])==r['talkId'] and r['proof']['wholeFieldEOF']==proof['wholeFieldEOF'],'Choice source pointer/EOF differs')
   require(str(r['talkId'])in deep['joins'],'Choice original missing')
   links.append((str(r['talkId']),{'url':'대화/연출-'+s['id']+'.html#'+r['anchor'],'kind':'연출 설정의 선택지','title':s['title'],'source':s['source'],'role':'NATIVE_CHOICE'}))
  safe_descriptor={k:v for k,v in descriptor.items() if k!='boundary'}
  safe_proof={k:proof[k] for k in ('kind','entrySha256','wholeFieldEOF','fields','fieldSpans')};safe_proof['descriptor']=safe_descriptor;safe_proof['pack']={k:v for k,v in proof['pack'].items() if k!='path'}
  new_scenes.append(safe({**s,'kind':'NATIVE_CHOICES','owners':owners,'ownerStatus':'ONE_EXPLICIT_OWNER' if len({o['canonicalMission'] for o in owners})==1 else 'MULTIPLE_EXPLICIT_OWNERS','proof':safe_proof}))
 require({int(tid) for tid in delta['joins']}==set(delta['newFrozenIds']) and set(delta['newFrozenIds'])<=frozen,'Frozen choice partition differs')
 require(len(new_scenes)==delta['counts']['scenes'] and len(links)==delta['counts']['rows'],'Choice delta count differs')
 deep['scenes'].extend(new_scenes);deep['evidence'].setdefault('nativeChoiceDeltas',[]).append({'sha256':dh,'cohortSha256':sha(Path(cohort_path).read_bytes()),'scenes':len(new_scenes),'rows':len(links)})
 deep['counts'].update(scenes=len(deep['scenes']),rows=sum(len(s['rows']) for s in deep['scenes']),distinctTalkIds=len(deep['joins']),roles=dict(Counter(r['role'] for s in deep['scenes'] for r in s['rows'])))
 require(not any(v in json.dumps(deep,ensure_ascii=False) for v in ('D:/','D:\\\\','C:/','.codex-work/')),'Private choice source path')
 write(path,deep);attr['evidence']['deepTimelineSha256']=sha(path.read_bytes())
 for tid,link in links:attr['readerLinks'].setdefault(tid,[]).append(link)
 attr['timelineReaderIds']=sorted(int(tid) for tid,value in attr['readerLinks'].items() if value)
 attr['counts'].update(timelineReaderIds=len(attr['timelineReaderIds']),links=sum(len(v) for v in attr['readerLinks'].values()),frozenTimelineAttributedIds=len(prior&set(attr['timelineReaderIds'])))
 write(attr_path,attr);return deep['counts']
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--projection',required=True,type=Path);p.add_argument('--cohort',required=True,type=Path);p.add_argument('--prior-cohort',required=True,type=Path);a=p.parse_args();print(json.dumps(extend(a.projection,a.cohort,a.prior_cohort),ensure_ascii=False))
