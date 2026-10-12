"""Independent exact auxiliary owner bridges; caption bodies remain immutable."""
import argparse,copy,hashlib,importlib.util,json,re,struct,sys,tarfile
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
KIND='CALLER_SOURCE_PUBLIC_JSON_SNAPSHOT_NATIVE_EOF_BLOCKED'
SDF_AUX_SHA='f3bc222999a58f44c7cfff0e7aaac2138e64fe923528ffc19c7508cb93aa82a0'
LUA_AUX_SHA='11569c81a83955bcb33316d9231284ad1ab77c3ca347a83555d3d4f7ca4d5526'
SDF_BRIDGE_SHA='93ef6aed303882cba131f871886d97c00743fbc2af5ed8b8b3381d45d9c43033'
LUA_BRIDGE_SHA='4f0e94bb85a96f92618ffa51ef45dbc040819ee34a78bb8a7ce525db12b1c138'
BASE_LUA_SHA='41d07729414c2ec62d76a5da126886e3a6ac961e28ffd19aca304c32ebd581f0'
LUA_ORIGINALS_SHA='57ddf7665ee58e0f7dc74004ec1e712b0d337f061755f6c3912d759e3b1b836e'
SDF_ORIGINALS_SHA='91a1f9944eccfabda4e7da42d499dc4061e10e7480057743f7c67272521a5b1c'
ARCHIVE_SHA='e1eee10139b338e271467e1823cedb0ceba0c5c1c608771f2386639db308f02a'
LUA_SCENE='lua-timeline-9192c8b22d0d8304'
def read(p):return json.loads(Path(p).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def digest(v):return sha(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def pointer(v,p):
 for k in p.split('/')[1:]:v=v[int(k)]if isinstance(v,list)else v[k.replace('~1','/').replace('~0','~')]
 return v
def precision(v):
 if type(v)is int:require(abs(v)<2**53,'Unsafe public number')
 elif isinstance(v,list):
  for x in v:precision(x)
 elif isinstance(v,dict):
  for k,x in v.items():
   if k in('pathID','m_PathID','nameHash'):require(isinstance(x,str),'64-bit identity must remain string')
   precision(x)
def originals_lua(d):return {'joins':d['joins'],'sceneOriginals':[{'id':s['id'],'title':s['title'],'kind':s['kind'],'source':s['source'],'rows':s['rows'],'root':s['proof']['root'],'container':s['proof']['container'],'receipt':s['proof']['receipt']}for s in d['scenes']]}
def originals_sdf(d):return [{'id':s['id'],'source':s['source'],'title':s['title'],'kind':s['kind'],'rows':s['rows'],'root':s['proof']['root'],'container':s['proof']['container'],'receipt':s['proof']['receipt']}for s in d['scenes']]
def bridge_public_checks(data,bridge,lane):
 precision(bridge);require(not re.search(r'(?:[A-Za-z]:[/\\]|\.codex-work|inventory\.json|objectFolder)',json.dumps(bridge)),'Private bridge path')
 snapshot=lane=='lua';require(bridge['schema']==('starrail-lua-snapshot-owner-bridges.v1'if snapshot else'starrail-native-sdf-owner-bridges.v1'),'Owner bridge schema');require(bridge['auditSha256']==(LUA_AUX_SHA if snapshot else SDF_AUX_SHA),'Unclosed owner bridge audit')
 if snapshot:
  require(bridge['originalLuaSha256']==BASE_LUA_SHA and bridge['callerSourceKind']==KIND and bridge['nativeCallerWholeEOF']is False and bridge['nativeInstalledCallerClaim']is False,'Snapshot/native caller distinction');require(set(bridge['scenes'])=={LUA_SCENE},'Unexpected snapshot owner target');require(digest(originals_lua(data))==LUA_ORIGINALS_SHA,'Twenty original captions/order/native Lua consumers changed')
 else:require(len(bridge['scenes'])==2 and sum(len(b['rows'])for b in bridge['scenes'].values())==7,'Unexpected native SDF targets');require(digest(originals_sdf(data))==SDF_ORIGINALS_SHA,'185 original SDF captions/proofs/order changed')
 scenes={s['id']:s for s in data['scenes']};used=set();rows=0
 for sid,b in bridge['scenes'].items():
  s=scenes[sid];require(s['source']==b['source']and s['proof']['root']==b['root']and s['proof']['container']==b['container']and s['proof']['receipt']==b['receipt'],'Exact existing root/CAB/source mismatch');require(s['owners']==b['owners']and s['proof']['references']==b['references'],'Projected owners/references differ from exact bridge');require(s['ownerStatus']==('ONE_EXPLICIT_SNAPSHOT_OWNER'if snapshot else'ONE_EXPLICIT_OWNER'),'Caller owner tier drift')
  for o in b['owners']:
   doc=read(SITE/'data/documents'/(o['canonicalMission']+'.json'));require(o['mission']in doc.get('missionParts',[doc['id']])and o['title']==doc['title'],'Canonical owner membership/title')
  if snapshot:
   require([r['talkId']for r in s['rows']]==[105009001,105009002,105009003,105009004],'Existing Fate slot IDs/order');r=b['row'];require(r['assetEOF']==r['object']['byteSize']and r['object']['class']=='ShowFateShowCaptionDialogClip','Whole existing Fate clip');field=next(f for f in r['assetFields']if f['field']=='ShowFateShowCaptionDialogClip.UIParam');require(field['value']=='105009001|105009002|105009003|105009004'and field['span'][1]==r['assetEOF'],'Exact serialized Fate parameter')
   for old in s['rows']:require(old['object']==r['object']and old['track']==r['track']and old['parentRoute']==r['parentRoute']and old['trackClipIndex']==r['trackClipIndex']and old['argument']['serializedField']==field and old['start']==r['timelineClip']['m_Start']and old['duration']==r['timelineClip']['m_Duration'],'Fate native original route differs')
   require(s['proof']['ownerBridge']=='EXACT_PUBLIC_SNAPSHOT_AUXILIARY_ROOT_AND_CALLER'and s['proof']['snapshotAuxiliarySceneId']==sid,'Snapshot bridge integration marker');rows+=4
  else:
   require(len(s['rows'])==len(b['rows']),'SDF bridge row set/order')
   for old,r in zip(s['rows'],b['rows']):
    p=old['proof'];require(all(p[k]==r[k]for k in('object','track','assetFields','assetEOF','trackClipIndex','timelineClip','parentRoute')),'SDF row original/field/timing differs');require(r['object']['class']=='ShowSDFTextClip'and r['assetEOF']==r['object']['byteSize'],'Typed SDF clip/EOF');rows+=1
   require(s['proof']['ownerBridge']=='EXACT_NATIVE_AUXILIARY_ROOT_AND_CALLER_SNAPSHOT'and s['proof']['nativeAuxiliarySceneId']==sid,'Native SDF bridge integration marker')
  for ref in b['references']:
   index=ref['sourceIndex'];used.add(index);p=bridge['sourceProofs'][index];require(data['sourceProofs'][index]==p and p['mission']in{o['mission']for o in b['owners']},'Exact owner source proof mismatch');require(ref['context']['typedContainer']=={'type':'RPG.GameCore.PlayTimeline','pointer':ref['pointer'].rsplit('/',1)[0]}and('assets/asbres/'+ref['timelineName']).casefold()==b['source'].casefold(),'Exact typed caller/TimelineName mismatch')
   if snapshot:
    require(p['callerSourceKind']==KIND and p['nativeCallerWholeEOF']is False and p['nativeInstalledCallerClaim']is False and p['nativeCallerFieldSpan']is None and p['rawConsumerByteFrontier']['wholeNativeEOF']is False,'Unproved native caller EOF/field span');require(ref['callerSourceKind']==KIND and ref['nativeCallerWholeEOF']is False and ref['nativeInstalledCallerClaim']is False and ref['fieldSpan']is None,'Snapshot reference incorrectly claims native span');require(ref['snapshotTask']['$type']=='RPG.GameCore.PlayTimeline'and ref['snapshotTask']['TimelineName']==ref['timelineName'],'Snapshot task domain/name')
   else:
    span=ref['fieldSpan'];require(span['pointer']==ref['pointer']and 0<=span['start']<span['end']<=p['consumedBytes'],'Actual native field byte boundary');require(p['callerPack']['editionStatus']=='CACHED_SNAPSHOT_CURRENT_INSTALLED_EDITION_UNVERIFIED','Unproved installed native caller edition')
 require(used==set(bridge['sourceProofs']),'Unused/missing owner source proof');return {'sceneCount':len(bridge['scenes']),'originalRows':rows,'sourceProofCount':len(used),'callerTier':KIND if snapshot else'CACHED_NATIVE_FULL_EOF_CALLER'}
def archive_checks(bridge,archive,lane):
 require(sha(archive.read_bytes())==ARCHIVE_SHA,'Archive source SHA drift');need={p['logicalJsonPath']for p in bridge['sourceProofs'].values()}
 for p in bridge['sourceProofs'].values():need.update(e[k]for e in p['ownerChain']for k in('source','tableSource')if k in e)
 loaded={}
 with tarfile.open(archive,'r|gz')as tf:
  for m in tf:
   n=m.name.split('/',1)[-1]
   if n not in need:continue
   raw=tf.extractfile(m).read();loaded[n]=(sha(raw),json.loads(raw));need.remove(n)
   if not need:break
 require(not need,'Missing actual archive owner/caller files');checked=0;terminals=0
 for b in bridge['scenes'].values():
  for ref in b['references']:
   p=bridge['sourceProofs'][ref['sourceIndex']];previous=None;owner=None
   for e in p['ownerChain']:
    h,f=loaded[e['source']];require(h==e['sourceSha256'],'Owner source SHA');require(previous is None or previous==e['source'],'Disconnected exact owner chain');v=pointer(f,e['pointer']);checked+=1
    if e['kind']=='EXPLICIT_MAIN_MISSION_ID':
     require(v==e['missionId']and e['canonicalMissionId']==int(p['mission'].split('-')[1]),'Explicit actual/canonical owner');docpath=SITE/e['membershipSource'];require(sha(docpath.read_bytes())==e['membershipSha256'],'Canonical member source SHA');doc=read(docpath);require(doc['id']==p['mission']and pointer(doc,e['membershipPointer'])=='quest-'+str(e['missionId']),'Canonical mission-part membership');owner=p['mission']
    elif e['kind']=='EXPLICIT_JSON_PATH':require(v==e['target'],'Actual graph path');previous=e['target']
    elif e['kind']=='EXPLICIT_PERFORMANCE_LOOKUP':
     th,t=loaded[e['tableSource']];require(th==e['tableSha256']and v==e['performanceId']==pointer(t,e['idPointer'])and pointer(t,e['pathPointer'])==e['target'],'Performance ID/path/table hash');task=pointer(f,e['pointer'].rsplit('/',1)[0]);require(task['$type']=='RPG.GameCore.TriggerPerformance'and task['PerformanceType']==e['performanceType'],'Typed performance consumer');previous=e['target']
    else:raise ValueError('Unrecognized owner edge')
   require(owner==p['mission']and previous==p['logicalJsonPath'],'Exact owner terminal');h,terminal=loaded[p['logicalJsonPath']];task=pointer(terminal,ref['pointer'].rsplit('/',1)[0]);require(task['$type']=='RPG.GameCore.PlayTimeline'and pointer(terminal,ref['pointer'])==ref['timelineName'],'Actual typed terminal caller');require(('assets/asbres/'+ref['timelineName']).casefold()==b['source'].casefold(),'Actual terminal root identity')
   if lane=='lua':require(h==p['sourceSha256']and task==ref['snapshotTask'],'Snapshot source SHA/task JSON differs')
   terminals+=1
 return {'archiveFiles':len(loaded),'ownerEdges':checked,'typedTerminalCalls':terminals,'nativeCallerWholeEOF':False if lane=='lua'else'NOT_INFERRED_FROM_JSON'}
def aux_checks(bridge,auxdir,lane,installed_asb):
 require(installed_asb is not None and installed_asb.is_dir(),'Explicit installed ASB directory required for actual auxiliary replay')
 name='public-snapshot-auxiliary-review.json'if lane=='lua'else'fresh-native-auxiliary-review.json';blob=(auxdir/name).read_bytes();require(sha(blob)==bridge['auditSha256'],'Closed auxiliary source SHA');audit=json.loads(blob);require(bridge['sourceProofs']==audit['ownerSourceProofs'],'Auxiliary owner proof projection differs');selected=[r for r in audit['results']if r.get('existingSceneId')in bridge['scenes']];expected=1 if lane=='lua'else 7;require(len(selected)==expected,'Exact auxiliary source selection');blocks=set();objects=0
 for r in selected:
  b=bridge['scenes'][r['existingSceneId']];require(b['root']==r['rootObject']and b['container']==r['rootContainer'],'Actual auxiliary root/container');rows=[b['row']]if lane=='lua'else b['rows'];row=next(x for x in rows if x['object']['pathID']==r['row']['object']['pathID']);require(all(row[k]==r['row'][k]for k in row),'Auxiliary actual clip projection changed');rec=r['sourceReceipt'];folder=Path(rec['objectFolder']);invraw=Path(rec['inventory']).read_bytes();require(sha(invraw)==rec['inventorySha256'],'CAB inventory hash');inv=json.loads(invraw);require(inv['sourceSha256']==rec['blockSha256']and inv['cabs'][0]['sha256']==rec['cabSha256'],'CAB/source identity');obs={str(o['pathID']):o for o in inv['cabs'][0]['objects']}
  if rec['blockFile']not in blocks:
   require(re.fullmatch(r'[0-9a-f]{32}\.block',rec['blockFile']),'Installed block path boundary');require(sha((installed_asb/rec['blockFile']).read_bytes())==rec['blockSha256'],'Current installed block SHA');blocks.add(rec['blockFile'])
  for o in(r['rootObject'],row['object'],row['track']):
   raw=(folder/(rec['cabName']+'-'+o['pathID']+'.bin')).read_bytes();require(len(raw)==o['byteSize']and sha(raw)==o['sha256'],'Actual current object bytes');script=obs[o['scriptPointer']['m_PathID']];require(script['classID']==115 and script['script']['m_ClassName']==o['class'],'Inventory-bound MonoScript binding');objects+=1
  raw=(folder/(rec['cabName']+'-'+row['object']['pathID']+'.bin')).read_bytes()
  for field in row['assetFields']:
   a,z=field['span'];require(0<=a<=z<=len(raw),'Actual asset field byte boundary')
   if field['field']=='ShowSDFTextClip.Config.SDFTextID':require(struct.unpack_from('<I',raw,a)[0]==field['value'],'Actual SDF typed ID field')
   if field['field']=='ShowFateShowCaptionDialogClip.UIParam':n=struct.unpack_from('<i',raw,a)[0];require(raw[a+4:a+4+n].decode('utf8')==field['value']and z==len(raw),'Actual UIParam UTF8/full-field EOF')
 if lane=='sdf':
  replayraw=(auxdir/'fresh-native-source-replay.json').read_bytes();require(sha(replayraw)==bridge['sourceReplaySha256'],'Closed native source replay SHA');replay=json.loads(replayraw);decoderpath=auxdir.parent/'star-native/phase5-strict-native-expanded.py';spec=importlib.util.spec_from_file_location('bridge_native_schema',decoderpath);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);decode=module.codec()
  for b in bridge['scenes'].values():
   for ref in b['references']:
    p=bridge['sourceProofs'][ref['sourceIndex']];private=replay['sources'][ref['sourceIndex']];require(private['sourceProof']==p and sha(decoderpath.read_bytes())==p['decoderSha256'],'Native source schema binding');pack=Path(private['packPath']).read_bytes();require(sha(pack)==p['callerPack']['sha256'],'Actual cached native caller pack');cat=p['catalogMatches'][0];raw=pack[cat['offset']:cat['offset']+cat['length']];require(sha(raw)==p['entrySha256'],'Native entry SHA');fields,spans=decode(raw);require(spans[-1]=={'pointer':'','start':0,'end':len(raw)}and pointer(fields,ref['pointer'])==ref['timelineName']and ref['fieldSpan']in spans,'Native complete EOF/actual field');require(pointer(fields,ref['context']['typedContainer']['pointer'])['$type']=='RPG.GameCore.PlayTimeline','Actual native caller class')
 return {'actualInstalledBlocks':len(blocks),'actualObjectByteChecks':objects,'rawMonoScriptBytes':'INVENTORY_BOUND_APPROVED_PROBE_DOES_NOT_EXPORT_115','nativeCallerEOF':lane=='sdf'}
def self_tests(data,bridge,lane):
 rejected=[]
 def change(name,fn):
  d,b=copy.deepcopy(data),copy.deepcopy(bridge);fn(d,b)
  try:bridge_public_checks(d,b,lane)
  except(ValueError,KeyError,IndexError,TypeError,StopIteration):rejected.append(name)
  else:raise ValueError('Bridge mutation accepted: '+name)
 sid=next(iter(bridge['scenes']));index=next(iter(bridge['sourceProofs']))
 change('wrong root',lambda d,b:b['scenes'][sid]['root'].update(sha256='0'*64));change('wrong owner',lambda d,b:b['scenes'][sid]['owners'][0].update(mission='quest-1'));change('wrong source proof',lambda d,b:b['sourceProofs'][index].update(logicalJsonPath='Story/changed.json'));change('wrong TimelineName',lambda d,b:b['scenes'][sid]['references'][0].update(timelineName='Story/changed.playable'));change('private path',lambda d,b:b.update(private='D:/private/input'));change('unsafe identity',lambda d,b:b['scenes'][sid]['root'].update(pathID=2**63-1));change('original row order',lambda d,b:next(s for s in d['scenes']if len(s['rows'])>1)['rows'].reverse())
 if lane=='lua':
  change('native EOF claim',lambda d,b:b.update(nativeCallerWholeEOF=True));change('native installed caller claim',lambda d,b:b['scenes'][sid]['references'][0].update(nativeInstalledCallerClaim=True));change('invented native span',lambda d,b:b['scenes'][sid]['references'][0].update(fieldSpan={'start':0,'end':4}));change('original Korean changed',lambda d,b:d['joins'][next(iter(d['joins']))].update(text='changed'));change('native Lua consumer changed',lambda d,b:next(s for s in d['scenes']if s['id']==sid)['rows'][0]['nativeConsumer'].update(runtimeOffset=24));change('UIParam token changed',lambda d,b:b['scenes'][sid]['row']['assetFields'][-1].update(value='1|2|3|4'))
 else:change('SDF typed class changed',lambda d,b:b['scenes'][sid]['rows'][0]['object'].update(**{'class':'PlaySimpleTalkClip'}))
 return rejected
def verify(args):
 result={'status':'PASS','lanes':{}}
 for lane,filename,bridgefile in [('sdf','sdf-timeline-text.json','native-sdf-owner-bridges.json'),('lua','lua-timeline-dialogue.json','lua-snapshot-owner-bridges.json')]:
  if args.sdf_only and lane=='lua':continue
  data=read(SITE/'data'/filename);raw=(SITE/'data'/bridgefile).read_bytes();bridge=json.loads(raw);key='nativeAuxiliaryOwnerBridgeSha256'if lane=='sdf'else'snapshotAuxiliaryOwnerBridgeSha256';require(data['evidence'][key]==sha(raw),'Published owner bridge SHA')
  require(sha(raw)==(SDF_BRIDGE_SHA if lane=='sdf'else LUA_BRIDGE_SHA),'Frozen exact owner bridge drift')
  report=bridge_public_checks(data,bridge,lane)
  if args.self_test:report['semanticMutationRejections']=self_tests(data,bridge,lane)
  if args.archive:report['archive']=archive_checks(bridge,args.archive,lane)
  if args.aux_dir:report['actualAuxiliary']=aux_checks(bridge,args.aux_dir,lane,args.installed_asb_directory)
  result['lanes'][lane]=report
 print(json.dumps(result,ensure_ascii=False));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');p.add_argument('--archive',type=Path);p.add_argument('--aux-dir',type=Path);p.add_argument('--installed-asb-directory',type=Path);p.add_argument('--sdf-only',action='store_true');verify(p.parse_args())
