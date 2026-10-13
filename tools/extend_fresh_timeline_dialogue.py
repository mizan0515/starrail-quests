"""Bind a closed native Timeline supplement without replacing retained readers."""
import argparse,hashlib,json
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
CLOSED_SHA='cfb05b93a7fbba8057af256dea9da7d49c213b9401eb05b1002d9e6d33d06c9b'
EXTENDED_SHA='b31990792d890bb38c3ecfb674f1cd7faa5f4200d9da9dc1aabc5e312d2094be'
def read(p):return json.loads(Path(p).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def require(v,msg):
 if not v:raise ValueError(msg)
def at(o,p):
 for k in p.split('/')[1:]:o=o[int(k)] if isinstance(o,list)else o[k.replace('~1','/').replace('~0','~')]
 return o
def write(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n').encode())
def bind(cohort_path,prior_path,snapshot=False):
 filename='public-snapshot-timeline-dialogue.json'if snapshot else'native-fresh-timeline-dialogue.json';closed_sha='94bc9b8177a03aa4cc617b026de7e2474217a3b435fe2a55865ba35e66ac0ccc'if snapshot else CLOSED_SHA;prefix='snapshot-timeline-'if snapshot else'fresh-timeline-';key='publicSnapshotTimelineSha256'if snapshot else'freshTimelineSha256'
 p=SITE/'data'/filename;raw=p.read_bytes();require(sha(raw)in ({closed_sha}if snapshot else{closed_sha,EXTENDED_SHA}),'Fresh projection was not closed');data=json.loads(raw);frozen=read(cohort_path)
 require(sha(Path(cohort_path).read_bytes())==data['evidence']['frozenCohortSha256'],'Current frozen cohort drift')
 attr_path=SITE/'data/deep-dialogue-attribution.json';attr=read(attr_path);prior_raw=Path(prior_path).read_bytes();require(sha(prior_raw)==attr['evidence']['frozenCohortSha256'],'Retained cohort drift');prior=set(json.loads(prior_raw)['starrail']['ids'])
 if 'existingDeepTimelineSha256'in data['evidence']:
  from verify_fresh_native_timeline import deep_preservation
  deep_preservation(SITE,data)
 if snapshot:require(all(p['nativeCallerWholeEOF']is False and p['nativeInstalledCallerClaim']is False and p['nativeCallerFieldSpan']is None and p['callerSourceKind']=='CALLER_SOURCE_PUBLIC_JSON_SNAPSHOT_NATIVE_EOF_BLOCKED'for p in data['sourceProofs'].values()),'Snapshot falsely claims native caller proof')
 require(not any(k in raw.decode()for k in ('D:/','D:\\','C:/','.codex-work','inventory.json','source_objects_folder')),'Private source path')
 files={};joins=data['joins']
 for tid,j in joins.items():
  source=j['preservedSource'];require(source['file'].startswith('data/dialogues/') and '..'not in source['file'].split('/'),'Unsafe original source')
  if source['file']not in files:
   body=(SITE/source['file']).read_bytes();files[source['file']]=(sha(body),json.loads(body))
  digest,obj=files[source['file']];row=at(obj,source['pointer']);require(digest==source['sha256'] and row['talk_id']==int(tid),'Original pointer/hash drift')
 expected=[];ids=set();anchors=set();seen=set();roles={'SPOKEN':0,'SCREEN_TEXT':0,'NON_SPOKEN_OPTION_REFERENCE':0}
 for scene in data['scenes']:
  require(scene['id'].startswith(prefix)and scene['id']not in seen,'Fresh scene collision');seen.add(scene['id'])
  require(bool(scene['owners'])or scene['ownerStatus']=='UNOWNED_NATIVE_TIMELINE','Fresh owner proof absent')
  for row in scene['rows']+scene['optionReferences']:
   tid=row['talkId'];role=row['role'];require(str(tid)in joins and role in roles and row['idField']['value']==tid,'Unknown literal role/domain');roles[role]+=1;ids.add(tid)
   url='대화/연출-'+scene['id']+'.html#'+row['anchor'];require(url not in anchors,'Fresh occurrence collision');anchors.add(url)
   expected.append((str(tid),{'url':url,'kind':'연출 설정의 선택지 참조'if role=='NON_SPOKEN_OPTION_REFERENCE'else'연출의 대사와 문구','title':scene['title'],'source':scene['source'],'role':role}))
 combined=data.get('combinedCounts');frozen_ids=data['counts']['includedFrozenUniqueIDs']+sum(d['counts']['includedFrozenUniqueIDs']for d in data['evidence'].get('newFreshDeltas',[]))
 require(len(seen)==(combined['scenes']if combined else data['counts']['sceneCount'])and len(ids)==(combined['distinctTalkIds']if combined else data['counts']['includedUniqueIDs'])and len(ids&set(frozen['starrail']['ids']))==frozen_ids,'Fresh count closure drift')
 require(all(roles[k]==(combined['roles'][k]['occurrences']if combined else data['counts']['occurrences']['included_'+k])for k in roles),'Fresh source roles drift')
 expected_by_id={}
 for tid,link in expected:expected_by_id.setdefault(tid,[]).append(link)
 for tid,links in attr['readerLinks'].items():attr['readerLinks'][tid]=[v for v in links if not v['url'].startswith('대화/연출-'+prefix)or v in expected_by_id.get(tid,[])]
 for tid,link in expected:
  if link not in attr['readerLinks'].get(tid,[]):attr['readerLinks'].setdefault(tid,[]).append(link)
 attr['timelineReaderIds']=sorted(int(tid)for tid,v in attr['readerLinks'].items()if v);attr['evidence'][key]=sha(raw)
 attr['counts'].update(timelineReaderIds=len(attr['timelineReaderIds']),links=sum(len(v)for v in attr['readerLinks'].values()),frozenTimelineAttributedIds=len(prior&set(attr['timelineReaderIds'])),**({'snapshotTimelineReaderIds':len(ids),'snapshotFrozenAttributedIds':frozen_ids}if snapshot else{'freshTimelineReaderIds':len(ids),'freshFrozenAttributedIds':frozen_ids}))
 write(attr_path,attr);return {'scenes':len(seen),'rows':len(expected),'roles':roles,'distinctIds':len(ids),'frozenIds':frozen_ids}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--snapshot',action='store_true');p.add_argument('--cohort',required=True,type=Path);p.add_argument('--prior-cohort',required=True,type=Path);a=p.parse_args();print(json.dumps(bind(a.cohort,a.prior_cohort,a.snapshot)))
