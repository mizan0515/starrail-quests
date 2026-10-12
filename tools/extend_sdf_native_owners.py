"""Enrich exact existing SDF roots; preserve all caption bodies and anchors."""
import argparse,copy,hashlib,json
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
AUX_SHA='f3bc222999a58f44c7cfff0e7aaac2138e64fe923528ffc19c7508cb93aa82a0'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def at(o,p):
 for k in p.split('/')[1:]:o=o[int(k)]if isinstance(o,list)else o[k.replace('~1','/').replace('~0','~')]
 return o
def require(v,msg):
 if not v:raise ValueError(msg)
def write(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n').encode())
def extend(audit):
 raw=Path(audit).read_bytes();require(sha(raw)==AUX_SHA,'Auxiliary source closure drift');aux=json.loads(raw);p=SITE/'data/sdf-timeline-text.json';data=read(p);before={s['id']:copy.deepcopy(s['rows'])for s in data['scenes']};scenes={s['id']:s for s in data['scenes']};bridge={'schema':'starrail-native-sdf-owner-bridges.v1','auditSha256':AUX_SHA,'sourceReplaySha256':aux['sourceReplaySha256'],'scenes':{},'sourceProofs':aux['ownerSourceProofs']};aliases=read(SITE/'data/aliases.json')
 for r in aux['results']:
  if r['status']!='PREEXISTING_EXACT_SDF_TYPED_CLIP_OWNER_ROUTE_ENRICHMENT':continue
  require(all(r['checks'].values()),'Native auxiliary identity mismatch');s=scenes[r['existingSceneId']];require(s['proof']['root']==r['rootObject']and s['proof']['container']==r['rootContainer'],'SDF native root differs')
  require(s['proof']['receipt']['cabSha256']==r['sourceReceipt']['cabSha256']and s['proof']['receipt']['sourceBlockSha256']==r['sourceReceipt']['blockSha256'],'SDF current CAB/block differs')
  row=next(x for x in s['rows']if x['proof']['object']['pathID']==r['row']['object']['pathID']);require(row['proof']['object']==r['row']['object']and row['proof']['track']==r['row']['track'],'SDF exact object/track differs')
  require(row['proof']['assetFields']==r['row']['assetFields']and row['proof']['assetEOF']==r['row']['assetEOF'],'SDF native original fields drift')
  b=bridge['scenes'].setdefault(s['id'],{'source':s['source'],'root':r['rootObject'],'container':r['rootContainer'],'receipt':s['proof']['receipt'],'rows':[],'owners':[],'references':[]})
  b['rows'].append({'object':r['row']['object'],'track':r['row']['track'],'assetFields':r['row']['assetFields'],'assetEOF':r['row']['assetEOF'],'trackClipIndex':r['row']['trackClipIndex'],'timelineClip':r['row']['timelineClip'],'parentRoute':r['row']['parentRoute']})
  for ref,index in zip(r['nativeReferences'],r['ownerSourceIndices']):
   source=aux['ownerSourceProofs'][index];mid=source['mission'];canonical=aliases.get(mid,mid);doc=read(SITE/'data/documents'/(canonical+'.json'));require(mid in doc.get('missionParts',[doc['id']]),'SDF owner membership drift')
   owner={'mission':mid,'canonicalMission':canonical,'title':doc['title']};item={'sourceIndex':index,'pointer':ref['pointer'],'fieldSpan':ref['fieldSpan'],'context':{'typedContainer':{'type':'RPG.GameCore.PlayTimeline','pointer':ref['pointer'].rsplit('/',1)[0]},'conditions':[]},'timelineName':ref['timelineName']}
   if owner not in b['owners']:b['owners'].append(owner)
   if item not in b['references']:b['references'].append(item)
 require(len(bridge['scenes'])==2,'Unexpected SDF owner closure size')
 for sid,b in bridge['scenes'].items():
  s=scenes[sid];by_object={(v['object']['pathID'],v['track']['pathID'],v['trackClipIndex']):v for v in b['rows']};b['rows']=[by_object[(v['proof']['object']['pathID'],v['proof']['track']['pathID'],v['proof']['trackClipIndex'])]for v in s['rows']];s['owners']=b['owners'];s['ownerStatus']='ONE_EXPLICIT_OWNER';s['proof']['references']=b['references'];s['proof']['ownerBridge']='EXACT_NATIVE_AUXILIARY_ROOT_AND_CALLER_SNAPSHOT';s['proof']['nativeAuxiliarySceneId']=sid
  for ref in b['references']:data['sourceProofs'][ref['sourceIndex']]=bridge['sourceProofs'][ref['sourceIndex']]
 require(before=={s['id']:s['rows']for s in data['scenes']},'SDF caption original changed')
 bridge_path=SITE/'data/native-sdf-owner-bridges.json';require(not any(v in json.dumps(bridge)for v in ('D:/','D:\\','C:/','.codex-work','inventory.json','objectFolder')),'Private bridge path');write(bridge_path,bridge)
 data['evidence']['nativeAuxiliaryOwnerBridgeSha256']=sha(bridge_path.read_bytes());data['evidence']['deepTimelineSha256']=sha((SITE/'data/deep-timeline-dialogue.json').read_bytes());data['counts']['ownedScenes']=sum(bool(s['owners'])for s in data['scenes']);data['counts']['ownedRows']=sum(len(s['rows'])for s in data['scenes']if s['owners']);write(p,data);return data['counts']
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--audit',required=True,type=Path);a=p.parse_args();print(json.dumps(extend(a.audit)))
