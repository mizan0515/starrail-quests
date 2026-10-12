"""Attach one exact archived caller owner route without changing Fate originals."""
import argparse,copy,hashlib,json,re
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
AUX_SHA='11569c81a83955bcb33316d9231284ad1ab77c3ca347a83555d3d4f7ca4d5526'
BASE_SHA='41d07729414c2ec62d76a5da126886e3a6ac961e28ffd19aca304c32ebd581f0'
KIND='CALLER_SOURCE_PUBLIC_JSON_SNAPSHOT_NATIVE_EOF_BLOCKED'
SCENE='lua-timeline-9192c8b22d0d8304'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def require(ok,msg):
 if not ok:raise ValueError(msg)
def encode(v):return (json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def originals(d):return {'joins':d['joins'],'sceneOriginals':[{'id':s['id'],'title':s['title'],'kind':s['kind'],'source':s['source'],'rows':s['rows'],'root':s['proof']['root'],'container':s['proof']['container'],'receipt':s['proof']['receipt']}for s in d['scenes']]}
def extend(audit):
 raw=Path(audit).read_bytes();require(sha(raw)==AUX_SHA,'Closed auxiliary audit SHA drift');aux=json.loads(raw);path=SITE/'data/lua-timeline-dialogue.json';oldraw=path.read_bytes();data=json.loads(oldraw);before=copy.deepcopy(originals(data));native_sources={k:v for k,v in data['sourceProofs'].items()if v.get('callerSourceKind')!=KIND};native_refs={s['id']:[r for r in s['proof']['references']if r.get('callerSourceKind')!=KIND]for s in data['scenes']}
 if sha(oldraw)!=BASE_SHA:
  existing_raw=(SITE/'data/lua-snapshot-owner-bridges.json').read_bytes();require(sha(existing_raw)==data['evidence'].get('snapshotAuxiliaryOwnerBridgeSha256'),'Existing owner bridge SHA drift');existing=json.loads(existing_raw);require(existing['auditSha256']==AUX_SHA and existing['originalLuaSha256']==BASE_SHA,'Unexpected Lua bridge baseline')
  from verify_timeline_owner_bridges import bridge_public_checks
  bridge_public_checks(data,existing,'lua')
 selected=[r for r in aux['results']if r['status']=='PREEXISTING_EXACT_FATE_SCREEN_CLIP_SNAPSHOT_OWNER_ENRICHMENT'];require(len(selected)==1,'Unexpected Fate auxiliary closure');r=selected[0];require(r['existingSceneId']==SCENE and r['newOriginalRows']==0 and all(r['checks'].values()),'Exact Fate bridge identity drift');s=next(s for s in data['scenes']if s['id']==SCENE);require(s['proof']['root']==r['rootObject']and s['proof']['container']==r['rootContainer'],'Exact installed root/container mismatch');rec=r['sourceReceipt'];require(s['proof']['receipt']['cabSha256']==rec['cabSha256']and s['proof']['receipt']['blockSha256']==rec['blockSha256'],'Actual current source/CAB drift')
 for row in s['rows']:require(row['object']==r['row']['object']and row['track']==r['row']['track']and row['argument']['raw']==r['row']['values']['UIParam']and row['parentRoute']==r['row']['parentRoute']and row['trackClipIndex']==r['row']['trackClipIndex'],'Fate original route/token differs')
 bridge={'schema':'starrail-lua-snapshot-owner-bridges.v1','auditSha256':AUX_SHA,'sourceOwnerReplaySha256':aux['sourceOwnerReplaySha256'],'originalLuaSha256':BASE_SHA,'callerSourceKind':KIND,'nativeCallerWholeEOF':False,'nativeInstalledCallerClaim':False,'scenes':{},'sourceProofs':aux['ownerSourceProofs']};refs=[];owners=[];aliases=read(SITE/'data/aliases.json')
 for ref in r['publicSnapshotReferences']:
  require(ref['kind']==KIND and ref['nativeCallerFieldSpan']is None and ref['nativeCallerWholeEOF']is False and ref['nativeInstalledCallerClaim']is False,'Unsupported native caller claim')
  for owner in ref['owners']:
   rk=(ref['source'],ref['sourceSha256'],owner['mission'],sha(json.dumps(owner['ownerChain'],sort_keys=True).encode()));index='snapshot-'+sha(json.dumps(rk,separators=(',',':')).encode())[:20];proof=bridge['sourceProofs'][index];require(proof['mission']==owner['mission']and proof['sourceSha256']==ref['sourceSha256']and proof['ownerChain']==owner['ownerChain'],'Exact snapshot source proof differs');mid=owner['mission'];canonical=aliases.get(mid,mid);doc=read(SITE/'data/documents'/(canonical+'.json'));require(mid in doc.get('missionParts',[doc['id']]),'Explicit canonical mission membership differs');o={'mission':mid,'canonicalMission':canonical,'title':doc['title']}
   if o not in owners:owners.append(o)
   item={'sourceIndex':index,'pointer':ref['pointer'],'fieldSpan':None,'context':{'typedContainer':{'type':'RPG.GameCore.PlayTimeline','pointer':ref['taskPointer']},'conditions':ref['serializedConditionSnapshot']},'timelineName':ref['timelineName'],'snapshotTask':ref['snapshotTask'],'callerSourceKind':KIND,'nativeCallerWholeEOF':False,'nativeInstalledCallerClaim':False}
   if item not in refs:refs.append(item)
 require([o['mission']for o in owners]==['quest-1040554'],'Unexpected explicit Fate owner');b={'source':s['source'],'root':r['rootObject'],'container':r['rootContainer'],'receipt':s['proof']['receipt'],'row':{k:r['row'][k]for k in('object','track','assetFields','assetEOF','trackClipIndex','timelineClip','parentRoute')},'owners':owners,'references':refs,'callerSourceKind':KIND};bridge['scenes'][SCENE]=b
 s['owners']=owners;s['ownerStatus']='ONE_EXPLICIT_SNAPSHOT_OWNER';s['proof']['references']=refs;s['proof']['ownerBridge']='EXACT_PUBLIC_SNAPSHOT_AUXILIARY_ROOT_AND_CALLER';s['proof']['snapshotAuxiliarySceneId']=SCENE
 for index,p in bridge['sourceProofs'].items():data['sourceProofs'][index]=p
 require(before==originals(data),'Twenty caption originals/native consumers changed');require(native_sources=={k:v for k,v in data['sourceProofs'].items()if v.get('callerSourceKind')!=KIND}and native_refs=={s['id']:[r for r in s['proof']['references']if r.get('callerSourceKind')!=KIND]for s in data['scenes']},'Four original native owners changed');require(not re.search(r'(?:[A-Za-z]:[/\\]|\.codex-work|inventory\.json|objectFolder)',json.dumps(bridge)),'Private bridge path')
 bridgepath=SITE/'data/lua-snapshot-owner-bridges.json';bridgeraw=encode(bridge);data['evidence']['snapshotAuxiliaryOwnerBridgeSha256']=sha(bridgeraw);newraw=encode(data);attrpath=SITE/'data/deep-dialogue-attribution.json';attr=read(attrpath);attr['evidence']['luaTimelineSha256']=sha(newraw)
 # Main invokes this projector; all checks complete before its three writes.
 bridgepath.write_bytes(bridgeraw);path.write_bytes(newraw);attrpath.write_bytes(encode(attr));return {'bridgeSha256':sha(bridgeraw),'luaTimelineSha256':sha(newraw),'originalRows':20,'newOriginalRows':0,'snapshotOwnerScenes':1}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--audit',required=True,type=Path);args=p.parse_args();print(json.dumps(extend(args.audit)))
