"""Project exact native SDF source uses without manufacturing dialogue identities."""
import argparse,hashlib,json
from collections import defaultdict
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
def digest(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(Path(path).read_text('utf8'))
def safe(value):
 if isinstance(value,list):return[safe(x)for x in value]
 if isinstance(value,dict):return{k:str(v)if k.lower()in('pathid','m_pathid','hash','hash64','legacy')else safe(v)for k,v in value.items()if k not in('inventory','outputDirectory','source_objects_folder','pack','path')}
 return value
def receipt(r):return{'blockFile':r['blockFile'],'sourceBlockSha256':r['blockSha256'],'bundleOffset':r['offset'],'cabName':r['cab'],'cabSha256':r['cabSha256']}
def root_identity(scene):
 p=scene['proof'];r=p['root'];return(p['container']['key'],str(r['pathID']),r['sha256'],r['byteStart'],r['byteSize'],p['receipt']['cabSha256'])
def build(audit_path,native_path=None):
 audit_path=Path(audit_path);native_path=Path(native_path or audit_path.with_name('special-native-routes.json'))
 audit=read(audit_path);native=read(native_path)
 assert audit['status']=='CLOSED_EXACT_SDF_NATIVE_DOMAIN_AUDIT'and audit['nativeSourceAuditSha256']==digest(native_path.read_bytes())
 joins={j['sdfTextID']:j for j in audit['joins']if j['status']=='EXACT_NATIVE_SDF_TEXTID_OFFICIAL_KOREAN_PASS'}
 route_index={};roots={}
 for bi,b in enumerate(native['results']):
  for root in b['root_metadata']:roots[(b['source_receipt']['cab'],str(root['object']['pathID']))]=root
  for ri,r in enumerate(b['routes']):route_index[(r['rootContainer']['key'],str(r['clipObject']['pathID']),str(r['trackObject']['pathID']),r['trackClipIndex'])]=(bi,ri,r)
 grouped=defaultdict(list)
 for index,r in enumerate(audit['occurrences']):
  assert r['role']=='SCREEN_TEXT'and r['talkID']is None and r['owners']==[] and r['ownerStatus']=='UNOWNED_NATIVE_TIMELINE'
  key=(r['timelineName'],str(r['clipObject']['pathID']),str(r['trackObject']['pathID']),r['trackClipIndex']);bi,ri,n=route_index[key]
  assert n['assetClass']=='ShowSDFTextClip'and n['serializedValues']['Config.SDFTextID']==r['sdfTextID']
  j=joins[r['sdfTextID']];assert r['textHash']==j['hash']
  fields=n['clipFields'];id_field=next(f for f in fields if f['field']=='ShowSDFTextClip.Config.SDFTextID')
  anchor='sdf-'+digest(json.dumps(key,ensure_ascii=False,separators=(',',':')).encode())[:20]
  grouped[r['timelineName']].append({'anchor':anchor,'role':'SCREEN_TEXT','talkId':None,'sdfTextId':j['sdfTextID'],'textHash':j['hash'],'text':j['text'],'raw':j['raw'],'speaker':None,'voice':j['voice'],'start':n['timelineClip']['m_Start'],'duration':n['timelineClip']['m_Duration'],'proof':{'auditOccurrenceIndex':index,'nativePointer':f'/results/{bi}/routes/{ri}','object':safe(n['clipObject']),'assetEOF':n['clipEOF'],'assetFields':safe(fields),'idField':safe(id_field),'track':safe(n['trackObject']),'trackEOF':n['trackEOF'],'trackFields':safe(n['trackFields']),'trackClipIndex':n['trackClipIndex'],'timelineClip':safe(n['timelineClip']),'parentRoute':list(map(str,n['parentRouteTalkToRoot'])),'tableRow':j['tableRow'],'tableRecord':safe(j['tableRecord']),'publicComparisonChecks':j['publicComparisonChecks'],'publicRow':j['publicRow'],'textRecord':safe(j['textRecord'])}})
 scenes=[]
 for source,rows in sorted(grouped.items()):
  rows.sort(key=lambda r:(r['start'],r['proof']['track']['pathID'],r['proof']['trackClipIndex'],r['proof']['object']['pathID']))
  row=rows[0];bi=int(row['proof']['nativePointer'].split('/')[2]);b=native['results'][bi];root=roots[(b['source_receipt']['cab'],row['proof']['parentRoute'][-1])]
  scenes.append({'id':'timeline-'+digest(('SDF\0'+source).encode())[:16],'title':rows[0]['text'].split('\n')[0][:68],'source':source,'owners':[],'ownerStatus':'UNOWNED_NATIVE_TIMELINE','kind':'HASH_ONLY_SCREEN_TEXT','rows':rows,'proof':{'container':safe(root['container']),'root':safe(root['object']),'rootEOF':root['eof'],'rootFields':safe(root['fields']),'receipt':receipt(b['source_receipt']),'references':[]}})
 deep_path=SITE/'data/deep-timeline-dialogue.json';deep_raw=deep_path.read_bytes();deep=json.loads(deep_raw);deep_index=defaultdict(list);source_proofs={}
 for ds in deep['scenes']:
  if ds['proof'].get('container') and ds['proof'].get('root') and ds['proof'].get('receipt'):deep_index[root_identity(ds)].append(ds)
 for scene in scenes:
  matches=deep_index.get(root_identity(scene),[])
  assert len(matches)<=1,'Ambiguous identical native root in existing typed reader'
  if matches:
   ds=matches[0];scene['owners']=ds['owners'];scene['ownerStatus']=ds['ownerStatus'];scene['proof'].update(deepSourceSceneId=ds['id'],ownerBridge='EXACT_SAME_NATIVE_CONTAINER_ROOT_AND_CAB',references=ds['proof']['references'])
   for ref in scene['proof']['references']:
    key=str(ref['sourceIndex']);assert key in deep['sourceProofs'];source_proofs[key]=deep['sourceProofs'][key]
 domain=audit['nativeDomain'];native_sources={}
 for name in('special-consumers-native.json','special-sdf-table-native.json','special-sdf-lookup-native.json'):
  evidence=read(audit_path.with_name(name));native_sources[name]={'sha256':digest(audit_path.with_name(name).read_bytes()),'functions':[{k:f[k]for k in('requestedVA','fileOffset','runtimeBegin','runtimeEnd','unwindRVA','bytes','sha256','raw')}for f in evidence['functions']]}
 data={'schema':'starrail-sdf-timeline-text.v1','kind':'HASH_ONLY_SCREEN_TEXT','evidence':{'auditSha256':digest(audit_path.read_bytes()),'deepTimelineSha256':digest(deep_raw),'nativeAuditSha256':digest(native_path.read_bytes()),'officialKorean':audit['officialKorean'],'nativeDomain':{**safe(domain),'packFile':Path(domain['pack']).name,'idDomain':'RPG.GameCore.HeartDialSDFRow.ID','textDomain':'RPG.Client.TextID.Hash64 → official Korean TextMap hash'},'nativeFunctions':native_sources,'nativeLiteralProof':safe(read(audit_path.with_name('special-sdf-literals.json'))),'publicComparison':audit['publicComparison'],'versionStatus':'Installed semantic version UNVERIFIED; official Korean OSPRODWin4.6.0'},'sourceProofs':source_proofs,'scenes':scenes,'counts':{'scenes':len(scenes),'rows':sum(len(s['rows'])for s in scenes),'uniqueSdfIds':len({r['sdfTextId']for s in scenes for r in s['rows']}),'uniqueTextHashes':len({r['textHash']for s in scenes for r in s['rows']}),'ownedScenes':sum(bool(s['owners'])for s in scenes),'ownedRows':sum(len(s['rows'])for s in scenes if s['owners'])},'unresolved':[safe(j)for j in audit['joins']if j['status']!='EXACT_NATIVE_SDF_TEXTID_OFFICIAL_KOREAN_PASS']}
 blob=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
 assert not any(t in blob.decode()for t in('D:/','D:\\','C:/','C:\\','.codex-work','inventory.json','outputDirectory'))
 (SITE/'data/sdf-timeline-text.json').write_bytes(blob+b'\n');print(json.dumps(data['counts']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--audit',type=Path,required=True);p.add_argument('--native-audit',type=Path);a=p.parse_args();build(a.audit,a.native_audit)
