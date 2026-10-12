"""Independently read preserved rows, typed raw object bytes and reader HTML."""
import argparse, hashlib, json, math, struct, tarfile
from collections import Counter
from pathlib import Path
from verify_site import Page
SITE=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text('utf8'))
def digest(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def at(o,p):
 for k in p.split('/')[1:]:o=o[int(k)] if isinstance(o,list) else o[k.replace('~1','/').replace('~0','~')]
 return o
def verify(audit_path=None,archive=None,dist=None,delta_paths=()):
 raw=(SITE/'data/deep-timeline-dialogue.json').read_bytes();data=json.loads(raw);attr=read(SITE/'data/deep-dialogue-attribution.json')
 require(data['schema']=='starrail-deep-timeline-dialogue.v1' and attr['schema']=='starrail-deep-dialogue-attribution.v1','Schema drift')
 require(attr['evidence']['deepTimelineSha256']==digest(raw),'Attribution hash drift')
 require(not any(token in raw.decode('utf8') for token in ('D:/','D:\\\\','C:/','C:\\\\','.codex-work/','outputDirectory','inventory.json')),'Private path in public source')
 corpus={};files={};ids=set();scenes=set();roles=Counter();links=Counter();objects={};native_checks=0
 for tid,j in data['joins'].items():
  p=j['preservedSource'];path=(SITE/p['file']).resolve();require(path.is_relative_to(SITE) and p['file'].startswith('data/dialogues/'),'Unsafe Korean source')
  if p['file'] not in files:
   b=path.read_bytes();files[p['file']]=(digest(b),json.loads(b))
  h,o=files[p['file']];r=at(o,p['pointer']);require(h==p['sha256'] and r['talk_id']==int(tid),'Preserved hash/ID drift');corpus[int(tid)]=r
 for s in data['scenes']:
  require(s['id'] not in scenes,'Duplicate scene');scenes.add(s['id']);anchors=set()
  require(bool(s['owners']) or s['ownerStatus']=='UNOWNED_NATIVE_TIMELINE','Scene ownership evidence absent')
  for owner in s['owners']:
   doc=read(SITE/'data/documents'/(owner['canonicalMission']+'.json'));require(owner['mission'] in doc.get('missionParts',[doc['id']]),'Mission membership drift')
  for r in s['rows']:
   require(r['anchor'] not in anchors,'Duplicate occurrence anchor');anchors.add(r['anchor']);tid=r['talkId'];require(tid in corpus,'Missing Korean corpus');ids.add(tid);roles[r['role']]+=1
   url='대화/연출-'+s['id']+'.html#'+r['anchor'];require(any(x['url']==url and x['source']==s['source'] and x['role']==r['role'] for x in attr['readerLinks'].get(str(tid),[])),'Missing exact inverse reader link');links[url]+=1
   if s.get('kind')=='NATIVE_CHOICES':
    require(r['role']=='NATIVE_CHOICE' and r['option']['$type']=='RPG.GameCore.OptionTalkInfo' and r['option']['TalkSentenceID']==tid,'Native option role/domain drift')
    require(r['parentTaskType']=='RPG.GameCore.PlayOptionTalk' and r['proof']['wholeFieldEOF']==s['proof']['wholeFieldEOF'],'Choice source EOF drift')
    require(at(s['proof']['fields'],r['proof']['pointer'])==tid,'Native source choice pointer drift')
    continue
   obj=r['object'];field=r['idField'];a,b=field['span']
   expected={'PlaySimpleTalkClip':('SPOKEN','PlaySimpleTalkClip.Config.TalkSentenceID'),'BPTalkClip':('SPOKEN','BPTalkClip.TalkSentenceID'),'ScreenTransferTextClip':('SCREEN_TEXT','ScreenTransferTextClip.SentenceID'),'SimpleTalkMarkerClip':('NON_SPOKEN_OPTION_REFERENCE','SimpleTalkMarkerClip.ReferenceOptionTalkID')}
   require(expected.get(obj['class'])==(r['role'],field['field']) and field['value']==tid,'Typed class/field/role drift')
   require(0<=a<b<=obj['byteSize'] and b-a==4,'Typed native ID width/bounds drift')
   require(all(type(r[k]) in (int,float) and math.isfinite(r[k]) for k in ('start','duration')) and r['start']>=0 and r['duration']>0,'Invalid clip time')
   require(r['parentRoute'][0]==r['track']['pathID'] and r['parentRoute'][-1]==s['proof']['root']['pathID'],'PPtr route endpoints drift')
   if r['role']=='NON_SPOKEN_OPTION_REFERENCE':require(r['optionReferences'] and all(x['task']['$type']=='RPG.GameCore.OptionTalkInfo' and x['task']['TalkSentenceID']==tid for x in r['optionReferences']),'Option consumer proof missing')
  if dist:
   p=Page();file=dist/'대화'/('연출-'+s['id']+'.html');p.feed(file.read_text('utf8'));require(not p.duplicates,'Duplicate built anchors')
   for r in s['rows']:
    require(p.original.get(r['anchor'])==corpus[r['talkId']]['text'],'Rendered original differs '+s['id']+'/'+r['anchor'])
    source=data['joins'][str(r['talkId'])]['preservedSource']['file'];url='/starrail-quests/대사/'+Path(source).stem+'.html#talk-'+str(r['talkId']);require(url in p.links,'Original return link missing')
   require('verified-sources' in p.ids and 'data-deep-role=' in file.read_text('utf8'),'Built evidence/roles missing')
 require(data['counts']['scenes']==len(scenes) and data['counts']['rows']==sum(roles.values()) and data['counts']['distinctTalkIds']==len(ids) and data['counts']['roles']==dict(roles),'Counts drift')
 if audit_path:
  require(digest(Path(audit_path).read_bytes())==data['evidence']['auditSha256'],'Source audit binding drift');audit=read(audit_path)
  require([digest(Path(p).read_bytes()) for p in delta_paths]==data['evidence'].get('deltaSha256',[]),'Repair delta hash drift')
  for p in delta_paths:
   delta=read(p);require(delta['status'] in ('CLOSED_MINIMUM_CLIP_REPAIR_DELTA','CLOSED_UNOWNED_TYPED_BP_DELTA'),'Unfinished delta');audit['occurrences'].extend(delta['occurrences']);audit['optionReferences'].extend(delta['optionReferences'])
  native={}
  for r in audit['occurrences']+audit['optionReferences']:
   key=(r['timelineName'],str(r['sourceObject']['pathID']),str(r['trackObject']['pathID']),r['trackClipIndex']);native[key]=r
  for s in data['scenes']:
   if s.get('kind')=='NATIVE_CHOICES':continue
   for r in s['rows']:
    key=(s['source'],r['object']['pathID'],r['track']['pathID'],r['trackClipIndex']);n=native[key]
    require(n['talkID']==r['talkId'] and n['role']==r['role'] and n['assetEOF']==r['object']['byteSize'],'Audit occurrence differs')
    directory=Path(n['sourceReceipt']['outputDirectory']);cab=n['sourceReceipt']['cabName'];object_path=directory/(cab+'-'+r['object']['pathID']+'.bin');block=object_path.read_bytes()
    require(len(block)==r['object']['byteSize'] and digest(block)==r['object']['sha256'],'Native object bytes differ');a,b=r['idField']['span'];require(struct.unpack('<I',block[a:b])[0]==r['talkId'],'Native literal ID differs');native_checks+=1
    trackkey=(str(directory),r['track']['pathID'])
    if trackkey not in objects:
     track=(directory/(cab+'-'+r['track']['pathID']+'.bin')).read_bytes();require(len(track)==r['track']['byteSize'] and digest(track)==r['track']['sha256'],'Track bytes differ');objects[trackkey]=True
  required={edge['source'] for p in data['sourceProofs'].values() for edge in p['ownerChain'] if 'source' in edge}|{edge['tableSource'] for p in data['sourceProofs'].values() for edge in p['ownerChain'] if 'tableSource' in edge}
  if archive:
   meta={}
   with tarfile.open(archive,'r|gz') as tar:
    for member in tar:
     name=member.name.split('/',1)[-1]
     if name in required:
      blob=tar.extractfile(member).read();meta[name]=(digest(blob),json.loads(blob));required.remove(name)
      if not required:break
   require(not required,'Missing owner source')
   for proof in data['sourceProofs'].values():
    for edge in proof['ownerChain']:
     if 'source' not in edge:continue
     h,o=meta[edge['source']];require(h==edge['sourceSha256'],'Owner source hash drift');value=at(o,edge['pointer'])
     if edge['kind']=='EXPLICIT_MAIN_MISSION_ID':require(value==edge['missionId'],'Owner ID drift')
     elif edge['kind']=='EXPLICIT_JSON_PATH':require(value==edge['target'],'Owner path drift')
     elif edge['kind']=='EXPLICIT_PERFORMANCE_LOOKUP':
      h,table=meta[edge['tableSource']];require(h==edge['tableSha256'] and at(table,edge['idPointer'])==value and at(table,edge['pathPointer'])==edge['target'],'Typed performance lookup drift')
 print(json.dumps({'status':'PASS','scenes':len(scenes),'rows':sum(roles.values()),'uniqueIds':len(ids),'roles':dict(roles),'nativeLiteralByteChecks':native_checks,'trackByteChecks':len(objects),'originalFiles':len(files),'html':bool(dist),'archive':bool(archive)},ensure_ascii=False),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--audit',type=Path);p.add_argument('--archive',type=Path);p.add_argument('--dist',type=Path);p.add_argument('--delta',type=Path,action='append',default=[]);a=p.parse_args();verify(a.audit,a.archive,a.dist,a.delta)
