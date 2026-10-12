"""Verify the independent SDF ID/hash domain, original bytes and static reader."""
import argparse,copy,hashlib,json,math,re,struct
from collections import Counter
from pathlib import Path
from verify_site import Page
SITE=Path(__file__).resolve().parents[1]
BRIDGE_SHA='93ef6aed303882cba131f871886d97c00743fbc2af5ed8b8b3381d45d9c43033'
def digest(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_text('utf8'))
def require(ok,msg):
 if not ok:raise ValueError(msg)
def pointer(o,p):
 for k in p.split('/')[1:]:o=o[int(k)]if isinstance(o,list)else o[k.replace('~1','/').replace('~0','~')]
 return o
def canonical(value):
 if isinstance(value,list):return[canonical(v)for v in value]
 if isinstance(value,dict):return{k:str(v)if k.lower()in('pathid','m_pathid','hash','hash64','legacy')else canonical(v)for k,v in value.items()}
 return value
def root_identity(scene):
 p=scene['proof'];r=p['root'];return(p['container']['key'],str(r['pathID']),r['sha256'],r['byteStart'],r['byteSize'],p['receipt']['cabSha256'])
def public_checks(data,deep):
 require(data['schema']=='starrail-sdf-timeline-text.v1'and data['kind']=='HASH_ONLY_SCREEN_TEXT','SDF schema drift')
 require(data['evidence']['nativeDomain']['idDomain']=='RPG.GameCore.HeartDialSDFRow.ID','SDF ID domain drift')
 require(data['evidence']['nativeDomain']['nativePath']=='BakedConfig/ExcelOutput/HeartDialTalk.bytes'and data['evidence']['nativeDomain']['nameHash']=='8873531181615768250','SDF native table alias drift')
 encoded=json.dumps(data,ensure_ascii=False)
 require(not re.search(r'(?:[A-Za-z]:[/\\]|\.codex-work|inventory\.json|outputDirectory|source_objects_folder)',encoded),'Private source path')
 scenes=set();sdfids=set();hashes=set();count=0;owned_scenes=owned_rows=0;needed_proofs={}
 require(data['evidence']['deepTimelineSha256']==digest((SITE/'data/deep-timeline-dialogue.json').read_bytes()),'Existing typed reader SHA drift')
 bridge_path=SITE/'data/native-sdf-owner-bridges.json'
 bridge=None
 if data['evidence'].get('nativeAuxiliaryOwnerBridgeSha256'):
  bridge_raw=bridge_path.read_bytes();require(digest(bridge_raw)==data['evidence']['nativeAuxiliaryOwnerBridgeSha256']==BRIDGE_SHA,'Native SDF bridge identity differs')
  bridge=json.loads(bridge_raw);require(bridge['schema']=='starrail-native-sdf-owner-bridges.v1'and bridge['auditSha256']=='f3bc222999a58f44c7cfff0e7aaac2138e64fe923528ffc19c7508cb93aa82a0','SDF auxiliary source closure drift')
 deep_by_id={s['id']:s for s in deep['scenes']}
 for s in data['scenes']:
  require(s['id']not in scenes and re.fullmatch(r'timeline-[0-9a-f]{16}',s['id'])and s['kind']=='HASH_ONLY_SCREEN_TEXT','Scene identity/kind drift');scenes.add(s['id'])
  if s['proof'].get('deepSourceSceneId'):
   ds=deep_by_id[s['proof']['deepSourceSceneId']];require(root_identity(s)==root_identity(ds),'Copied owner actual native root/CAB differs');require(s['owners']==ds['owners']and s['ownerStatus']==ds['ownerStatus']and s['proof']['references']==ds['proof']['references'],'Copied owner/reference differs')
   require(s['proof']['ownerBridge']=='EXACT_SAME_NATIVE_CONTAINER_ROOT_AND_CAB','Owner bridge kind drift')
   for ref in s['proof']['references']:
    key=str(ref['sourceIndex']);require(data['sourceProofs'][key]==deep['sourceProofs'][key],'Copied whole owner source proof differs');needed_proofs[key]=data['sourceProofs'][key]
  elif s['proof'].get('nativeAuxiliarySceneId'):
   require(bridge is not None and s['proof']['nativeAuxiliarySceneId']==s['id']and s['proof']['ownerBridge']=='EXACT_NATIVE_AUXILIARY_ROOT_AND_CALLER_SNAPSHOT','SDF auxiliary bridge domain')
   b=bridge['scenes'][s['id']];require(s['source']==b['source']and s['proof']['root']==b['root']and s['proof']['container']==b['container']and s['proof']['receipt']==b['receipt'],'Auxiliary source/root/CAB identity drift')
   require(s['owners']==b['owners']and s['proof']['references']==b['references']and s['ownerStatus']=='ONE_EXPLICIT_OWNER','Auxiliary owner/source reference drift')
   for row,expected in zip(s['rows'],b['rows']):
    p=row['proof'];require(p['object']==expected['object']and p['track']==expected['track']and p['assetFields']==expected['assetFields']and p['assetEOF']==expected['assetEOF'],'Auxiliary current native clip/track differs')
    require(p['trackClipIndex']==expected['trackClipIndex']and p['timelineClip']==expected['timelineClip']and p['parentRoute']==expected['parentRoute'],'Auxiliary exact current route/timing differs')
   require(len(s['rows'])==len(b['rows']),'Auxiliary original row count differs')
   for owner in s['owners']:
    doc=read(SITE/'data/documents'/(owner['canonicalMission']+'.json'));require(owner['mission']in doc.get('missionParts',[doc['id']])and owner['title']==doc['title'],'Auxiliary mission membership differs')
   for ref in s['proof']['references']:
    key=ref['sourceIndex'];source=bridge['sourceProofs'][key];require(data['sourceProofs'][key]==source,'Auxiliary whole caller source differs');needed_proofs[key]=source
    require(ref['context']['typedContainer']['type']=='RPG.GameCore.PlayTimeline'and ref['pointer']==ref['context']['typedContainer']['pointer']+'/TimelineName','Auxiliary typed caller domain')
    require(ref['timelineName'].casefold()==s['source'].casefold().removeprefix('assets/asbres/')and ref['fieldSpan']['pointer']==ref['pointer']and 0<=ref['fieldSpan']['start']<ref['fieldSpan']['end']<=source['consumedBytes'],'Auxiliary exact caller name/byte span differs')
  else:require(s['owners']==[]and s['ownerStatus']=='UNOWNED_NATIVE_TIMELINE'and s['proof']['references']==[],'Unsupported SDF owner')
  if s['owners']:owned_scenes+=1;owned_rows+=len(s['rows'])
  require(s['proof']['container']['key']==s['source']and str(s['proof']['container']['pathID'])==s['proof']['root']['pathID']and s['proof']['rootEOF']==s['proof']['root']['byteSize'],'Direct native root drift')
  anchors=set()
  for r in s['rows']:
   require(r['talkId']is None and r['speaker']is None and r['role']=='SCREEN_TEXT','Manufactured dialogue/speaker identity')
   require(type(r['sdfTextId'])is int and r['sdfTextId']>0 and r['anchor']not in anchors,'Duplicate/invalid SDF ID or anchor');anchors.add(r['anchor']);sdfids.add(r['sdfTextId']);hashes.add(r['textHash']);count+=1
   p=r['proof'];f=p['idField'];a,b=f['span'];record=p['tableRecord'];text=p['textRecord']
   require(f['field']=='ShowSDFTextClip.Config.SDFTextID'and f['value']==r['sdfTextId']and b-a==4 and 0<=a<b<=p['object']['byteSize'],'Typed SDF source field drift')
   require(record['ID']==r['sdfTextId']and str(record['SDFText']['Hash'])==r['textHash']==str(text['hash'])and text['raw']==r['raw'],'Table/TextMap/raw join drift')
   require(record.get('VoiceID',0)==r['voice']and all(p['publicComparisonChecks'].values()),'SDF voice/public comparison drift')
   require(p['assetEOF']==p['object']['byteSize']and p['trackEOF']==p['track']['byteSize'],'Whole native object EOF drift')
   require(p['parentRoute'][0]==p['track']['pathID']and p['parentRoute'][-1]==s['proof']['root']['pathID'],'PPtr root endpoint drift')
   require(p['timelineClip']['m_Asset']=={'fileID':0,'pathID':p['object']['pathID']},'PPtr asset identity drift')
   require(all(type(r[k])in(int,float)and math.isfinite(r[k])for k in('start','duration'))and r['start']>=0 and r['duration']>0,'Invalid clip time')
 require(data['counts']=={'scenes':len(scenes),'rows':count,'uniqueSdfIds':len(sdfids),'uniqueTextHashes':len(hashes),'ownedScenes':owned_scenes,'ownedRows':owned_rows},'SDF count drift')
 require(needed_proofs==data['sourceProofs'],'Extra or missing owner proof')
 return count
class Clip:
 def __init__(self,b):self.b=b;self.at=0
 def take(self,n):
  require(0<=n and self.at+n<=len(self.b),'Native clip truncated');v=self.b[self.at:self.at+n];self.at+=n;return v
 def num(self,t):return struct.unpack('<'+t,self.take(struct.calcsize('<'+t)))[0]
 def align(self):
  n=(-self.at)%4;require(self.take(n)==bytes(n),'Nonzero native alignment')
 def string(self):
  n=self.num('i');require(0<=n<=4096,'Native string length');s=self.take(n).decode('utf8');self.align();return s
 def boolean(self):
  v=self.num('B');require(v in(0,1),'Native bool domain');self.align();return bool(v)
 def ptr(self):return{'fileID':self.num('i'),'pathID':str(self.num('q'))}
def sdf_clip(raw,obj,script,name,expected):
 r=Clip(raw);require(r.ptr()=={'fileID':0,'pathID':'0'},'Unity base game object');r.boolean();require(r.ptr()==script,'MonoScript PPtr');require(r.string()==name,'Native object name')
 values={'CharacterUniqueName':r.string(),'Config.SDFTextID':r.num('I'),'Config.AnimatorParamName':r.string(),'Config.AnimatorParam':r.num('i'),'Config.IsSetScale':r.boolean()}
 for k in('DenseTypeScale','TallTypeScale','EnglishLikeScale','OverrallScale'):values['Config.'+k]=r.num('f')
 values['Config.OverrideRenderQueue']=r.boolean();values['Config.RenderQueue']=r.num('i');values['Config.AlignType']=r.num('i')
 require(r.at==len(raw)==obj['byteSize']and values==expected,'Native full SDF fields/EOF drift');return values
def selftest(data,deep):
 attempts=0
 changes=(('talkId',123),('speaker','추정 화자'),('role','SPOKEN'),('sdfTextId',0),('textHash','1'),('raw','잘못된 원문'))
 for key,value in changes:
  altered=copy.deepcopy(data);altered['scenes'][0]['rows'][0][key]=value
  try:public_checks(altered,deep)
  except(ValueError,KeyError):attempts+=1
  else:raise ValueError('Mutated public SDF source accepted: '+key)
 altered=copy.deepcopy(data);altered['scenes'][0]['owners']=[{'mission':'quest-1'}]
 try:public_checks(altered,deep)
 except ValueError:attempts+=1
 else:raise ValueError('Invented SDF owner accepted')
 owned=next(i for i,s in enumerate(data['scenes'])if s['owners'])
 mutations=(('root','pathID','1'),('root','sha256','0'*64),('root','byteStart',-1),('root','byteSize',1),('receipt','cabSha256','0'*64))
 for part,key,value in mutations:
  altered=copy.deepcopy(data);altered['scenes'][owned]['proof'][part][key]=value
  try:public_checks(altered,deep)
  except(ValueError,KeyError):attempts+=1
  else:raise ValueError('Wrong shared native root accepted: '+key)
 altered=copy.deepcopy(data);source=next(iter(altered['sourceProofs']));altered['sourceProofs'][source]['entrySha256']='0'*64
 try:public_checks(altered,deep)
 except ValueError:attempts+=1
 else:raise ValueError('Changed copied owner source proof accepted')
 return attempts
def verify(args):
 data=read(SITE/'data/sdf-timeline-text.json');deep=read(SITE/'data/deep-timeline-dialogue.json');count=public_checks(data,deep);tests=selftest(data,deep)if args.selftest else 0;nativechecks=0;badbytes=0
 if args.audit:
  audit=read(args.audit);require(digest(args.audit.read_bytes())==data['evidence']['auditSha256'],'Private audit hash drift');nativepath=args.native_audit or args.audit.with_name('special-native-routes.json');native=read(nativepath);require(digest(nativepath.read_bytes())==data['evidence']['nativeAuditSha256'],'Native source audit hash drift')
  require(args.official_root and args.skill,'Native verification requires approved official-root and skill')
  import sys
  sys.dont_write_bytecode=True;sys.path.insert(0,str(args.skill/'scripts'))
  from binary import decode_table,read_catalog
  from export_library import readable
  domain=data['evidence']['nativeDomain'];root=args.official_root.resolve();packpath=root/domain['packFile'];pack=packpath.read_bytes();require(digest(pack)==domain['packSha256'],'Official SDF pack hash drift');entry=pack[domain['offset']:domain['offset']+domain['length']];require(digest(entry)==domain['entrySha256'],'SDF table entry hash drift')
  catalog=read_catalog((root/data['evidence']['officialKorean']['catalogFile']).read_bytes());matches=[(f,e)for f in catalog if not f['language']for e in f['entries']if str(e[0])==domain['nameHash']];require(len(matches)==1 and matches[0][0]['file']==domain['packFile']and matches[0][1][1:]==(domain['length'],domain['offset']),'Exact SDF catalog identity drift')
  rows=decode_table(entry,domain['schemaSlots']);require(len(rows)==domain['tableRows']and domain['fullEOF']==len(entry),'Whole SDF table EOF drift')
  official=data['evidence']['officialKorean'];kr=(root/'kr'/official['koreanPack']['file']).read_bytes();require(digest(kr)==official['koreanPack']['sha256'],'Official Korean pack hash drift')
  from binary import decode_textmap
  te=official['entry'];textentry=kr[te['offset']:te['offset']+te['length']];require(digest(textentry)==te['sha256'],'Korean entry hash drift');texts={str(t['hash']):t for t in decode_textmap(textentry)}
  checked=set()
  for s in data['scenes']:
   for row in s['rows']:
    p=row['proof'];n=pointer(native,p['nativePointer']);ref=audit['occurrences'][p['auditOccurrenceIndex']];require(canonical(n['clipObject'])==ref['clipObject']==p['object'] and canonical(n['trackObject'])==p['track'] and canonical(n['rootObject'])==s['proof']['root']and n['serializedValues']['Config.SDFTextID']==row['sdfTextId'],'Exact private pointer drift')
    actual=rows[p['tableRow']];require(actual['ID']==row['sdfTextId']and str(actual['SDFText']['Hash'])==row['textHash'],'Native row ID/hash drift');text=texts[row['textHash']];require(text['raw']==row['raw']and readable(text['raw'])==row['text'],'Raw/readable Korean drift')
    directory=Path(ref['sourceReceipt']['source_objects_folder']).resolve();require(directory.is_relative_to(args.audit.parent.resolve()/'special-cabs'),'Private object directory containment');cab=ref['sourceReceipt']['cab'];inventory=read(directory/'inventory.json');obj=next(o for o in inventory['cabs'][0]['objects']if str(o['pathID'])==p['object']['pathID']);script=next(o['script']for o in inventory['cabs'][0]['objects']if str(o['pathID'])==str(obj['scriptPointer']['m_PathID']));require(script['m_ClassName']=='ShowSDFTextClip'and script['m_Namespace']=='RPGTools.Timeline','Native class domain drift')
    blob=(directory/(cab+'-'+p['object']['pathID']+'.bin')).read_bytes();require(digest(blob)==p['object']['sha256'],'Native clip SHA drift');expected={f['field'][len('ShowSDFTextClip.'):]:f['value']for f in p['assetFields']if f['field'].startswith('ShowSDFTextClip.')};sdf_clip(blob,p['object'],{'fileID':0,'pathID':str(obj['scriptPointer']['m_PathID'])},obj['name'],expected);nativechecks+=1
    for item in(p['track'],s['proof']['root']):
     b=(directory/(cab+'-'+item['pathID']+'.bin')).read_bytes();require(len(b)==item['byteSize']and digest(b)==item['sha256'],'Track/root raw source drift')
    token=(cab,p['object']['pathID'])
    if args.selftest and token not in checked:
     checked.add(token)
     for mutant in[blob[:i]for i in range(len(blob))]+[blob+b'\0',blob+b'\xff']:
      try:sdf_clip(mutant,p['object'],{'fileID':0,'pathID':str(obj['scriptPointer']['m_PathID'])},obj['name'],expected)
      except(ValueError,struct.error,UnicodeError):badbytes+=1
      else:raise ValueError('Truncated/trailing native SDF clip accepted')
     a,b=p['idField']['span'];mutant=blob[:a]+struct.pack('<I',0)+blob[b:]
     try:sdf_clip(mutant,p['object'],{'fileID':0,'pathID':str(obj['scriptPointer']['m_PathID'])},obj['name'],expected)
     except ValueError:badbytes+=1
     else:raise ValueError('Mutated SDF ID accepted')
  if args.game_root:
   assembly=args.game_root/'GameAssembly.dll'
   with assembly.open('rb')as stream:
    for proof in data['evidence']['nativeFunctions'].values():
     for f in proof['functions']:
      stream.seek(f['fileOffset']);body=stream.read(f['bytes']);require(body.hex()==f['raw']and digest(body)==f['sha256'],'Installed native consumer/row body drift')
   blocks={r['sourceReceipt']['blockFile']:r['sourceReceipt']['blockSha256']for r in audit['occurrences']}
   for file,h in blocks.items():require(digest((args.game_root/'StarRail_Data/StreamingAssets/Asb/Windows'/file).read_bytes())==h,'Installed native source block drift')
 if args.dist:
  publication_expand=None
  if (args.dist/'_shared').is_dir():
   from optimize_publication import expansion_function
   publication_expand=expansion_function(read(SITE/'.codex-work/publication-build-report.json'))
  for s in data['scenes']:
   raw=(args.dist/'대화'/('연출-'+s['id']+'.html')).read_text('utf8');page=Page();page.feed(raw);require(not page.duplicates and 'verified-sources'in page.ids and 'data-sdf-role="SCREEN_TEXT"'in raw,'Built SDF reader evidence/anchors')
   proof_html=raw
   if publication_expand:proof_html=publication_expand(raw)
   for r in s['rows']:require(page.original.get(r['anchor'])==r['text']and 'data-sdf-clip-proof="'+r['anchor']+'"'in proof_html,'Built SDF original/proof anchor drift')
   for owner in s['owners']:require('/starrail-quests/문서/'+owner['canonicalMission']+'.html#deep-timeline-originals'in page.links,'SDF exact owner return link missing')
   # Owner proof belongs to technical metadata; originals and return links above stay static.
   for ref in s['proof']['references']:require('data-sdf-owner-proof="'+str(ref['sourceIndex'])+'"'in proof_html,'Built whole owner source proof missing')
 print(json.dumps({'status':'PASS','scenes':len(data['scenes']),'rows':count,'nativeClipChecks':nativechecks,'malformedNativeClipRejections':badbytes,'publicMutationRejections':tests,'sourceVerified':bool(args.audit),'dist':bool(args.dist)},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--audit',type=Path);p.add_argument('--native-audit',type=Path);p.add_argument('--official-root',type=Path);p.add_argument('--skill',type=Path);p.add_argument('--game-root',type=Path);p.add_argument('--dist',type=Path);p.add_argument('--selftest','--self-test',dest='selftest',action='store_true');verify(p.parse_args())
