"""Portable, read-only replay of the frozen PlayMissionTalk range references.

Default: closed public proof, original Korean rows and typed interval boundaries.
--archive: whole JSON census and exact source bytes/pointers.
--game-root: current metadata, method pointers and seven whole .pdata extents.
--dist: rendered originals, reference roles, anchors, source notes and return link.
--publication-report: optional actual shared-metadata receipt for packed readers.
No producer modules or third-party packages are imported.
"""
import argparse
import base64
import copy
import gzip
import hashlib
from publication_contract_reader import HTMLParser
import json
import math
import mmap
from pathlib import Path
import re
import struct
import tarfile
from urllib.parse import unquote, urlsplit

ROLE = 'NON_SPOKEN_CONFIGURATION_REFERENCE'
SCHEMA = 'starrail-mission-talk-range-dialogue.v1'
DATA_SHA = '460b8bb84063b154dc64198767c455e43993d874f86011dc3acc8c8c098e61a4'
FROZEN = {
 'mission-talk-consumer-profile.json':'243f756a3760b3e91578c4245d1b46437911c2ddd548a3579764ba268e638816',
 'mission-talk-range-projection.json':'ceaab9844741daeab7c63a3ceacac9d07c22ade08baa9135e00af5dcc39686c6',
 'mission-talk-korean-joins.json':'1367e12520dd6e2b5a9ebdaf4f3c02df4b133ea8d4b6724e94c77c05fac26d5b',
}
PARTS = {
 'nativeProfile':'84d8f291ee4600abf8a2f6aef991b4ba9474d4daabdf0599522943ed3d527987',
 'sourceRecords':'8a89edeed752b79d15729bd21ee4bcba89819c1c95ed686a3b32d0be50c3220c',
 'joins':'8428d375dbf7b4ad58a7f9ebc189cd0ebd8a8350746d4c76204cc571a188e68d',
 'ids':'d1f853905ac129c4c5e2649a21d729a06385c6c5c3a71286c29eeb157f2a4bf7',
 'officialKoreanTextMap':'46e737fe0ec0c0d1ccb63a24890afcc9f0df067b100a49e923fb92994c911e45',
 'officialTalkSentenceTable':'452b4b4d693fac0595fc985dc2ebdd6b3fc383595cc8d790801b3528f5056ac5',
 'sourceCensus':'e1515080de96231f15ba8b9c6119ac17fc684159ea71f069a8706de49a435118',
}
NOTE = '설정 JSON과 현재 설치본의 판본 일치는 미확인이며, 실제 실행 여부와 발화 시점은 확인 중입니다.'

def native_summary(profile):
 return {'inputs':profile['inputs'],'functions':[{'address':f['requestedVA'],'bytes':f['bytes'],'sha256':f['sha256'],'extent':'.pdata'} for f in profile['rawFunctions']['functions']], 'methods':[{'class':m['class'],'methodIndex':m['methodIndex'],'address':m['nativeVA']} for m in profile['methods']['matches']], 'fields':[{'class':c['class'],'fields':[{'name':f['name'],'offset':f['runtimeFieldOffset']} for f in c['fields']]} for c in profile['rawFields']], 'bindings':profile['bindings'],'conditions':profile['conditions'],'limits':profile['limits']}

def require(condition, message):
 if not condition: raise ValueError(message)

def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(obj): return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')
def load(path): return json.loads(Path(path).read_bytes())

def public_safe(obj):
 if isinstance(obj, dict):
  for k,v in obj.items():
   if k in ('Hash','hash','speaker_hash'):
    require(type(v) is str and v.isdecimal() and 0 <= int(v) < 2**64, 'lossless UInt64 hash required')
   public_safe(v)
 elif isinstance(obj, list):
  for v in obj: public_safe(v)
 elif isinstance(obj, str):
  require(not re.search(r'(?:[A-Za-z]:[/\\]|file://|/(?:Users|home)/|\.env\b|codex-home|root_MUST)', obj, re.I), 'private path/process material')

def pointer(obj, ptr):
 require(type(ptr) is str and (ptr == '' or ptr.startswith('/')), 'JSON pointer syntax')
 for key in ptr.split('/')[1:]:
  key=key.replace('~1','/').replace('~0','~')
  if isinstance(obj,list):
   require(key.isdecimal() and (key=='0' or not key.startswith('0')), 'array pointer index')
   obj=obj[int(key)]
  else: obj=obj[key]
 return obj

def number(wrapper):
 if type(wrapper) is not dict or wrapper.get('IsDynamic') is not False: return None
 fixed=wrapper.get('FixedValue')
 value=fixed.get('Value') if type(fixed) is dict else None
 if type(value) not in (int,float) or not math.isfinite(value) or not 0 < value < 2**32 or value != int(value): return None
 return int(value)

def interval(node, frozen):
 if type(node) is not dict or node.get('$type') != 'RPG.GameCore.PlayMissionTalk': return None
 start=number(node.get('StartSentenceID')); end=number(node.get('EndSentenceID'))
 # The native inc edi loop wraps at UINT32_MAX; that boundary has no closed replay.
 if start is None or end is None or start > end or end == 2**32-1: return None
 return start,end,[tid for tid in frozen if start <= tid <= end]

def readable(raw):
 text=raw.replace('\\n','\n').replace('\u00a0',' ')
 text=re.sub(r'\{RUBY_[BE]#[^}]*\}', '', text)
 text=re.sub(r'</?(?:color|size|b|i|u|align|voffset|indent|line-height|unbreak)(?:=[^>]*)?>','',text,flags=re.I)
 return re.sub(r'<br\s*/?>','\n',text,flags=re.I)

def source_flags(obj):
 require(obj['role']==ROLE, 'non-spoken reference role changed')
 require(obj['edition']=='UNKNOWN' and obj['runtimeVerified'] is False and obj['nativeSourceWholeEOF'] is False, 'edition/runtime/native EOF boundary changed')

def profile_check(profile):
 require(profile['rawFunctions']['source']=='GameAssembly.dll', 'native logical source')
 functions=profile['rawFunctions']['functions']
 require(len(functions)==7 and len(profile['methods']['matches'])==7 and sum(len(c['fields']) for c in profile['rawFields'])==11, 'whole function/method/field census')
 for f in functions:
  raw=bytes.fromhex(f['raw']); require(len(raw)==f['bytes'] and sha(raw)==f['sha256'], 'whole function raw hash')
  for i in f['instructions']:
   start=int(i['va'],16)-int(f['requestedVA'],16); ins=bytes.fromhex(i['bytes'])
   require(0<=start<=len(raw)-len(ins) and raw[start:start+len(ins)]==ins, 'instruction raw/function domain')
 opcodes={'0x18e781d92':'48837f1800','0x18e781e09':'488b4710','0x18bfc57db':'ffc7','0x18bfc57dd':'4439ff','0x18bfc57e0':'0f87eb000000','0x18bfc57f8':'e8f314b911','0x18bfc5ce8':'e80310b911'}
 for address,encoded in opcodes.items():
  va=int(address,16); f=next(f for f in functions if int(f['requestedVA'],16)<=va<int(f['requestedVA'],16)+f['bytes'])
  off=va-int(f['requestedVA'],16); raw=bytes.fromhex(f['raw']); expected=bytes.fromhex(encoded)
  require(raw[off:off+len(expected)]==expected, 'static/fixed/unsigned inclusive loop opcode')
  if expected[0]==0xe8: require(va+5+int.from_bytes(expected[1:],'little',signed=True)==0x19db56cf0, 'typed GetData direct call target')
 for row in profile['methods']['matches']:
  require(len(bytes.fromhex(row['metadataRaw']))==26 and int.from_bytes(bytes.fromhex(row['methodPointerRaw']),'little')==int(row['nativeVA'],16), 'method metadata/native pointer identity')
 for cls in profile['rawFields']:
  for field in cls['fields']:
   require(int.from_bytes(bytes.fromhex(field['runtimeFieldOffsetRaw']),'little')==field['runtimeFieldOffset'], 'field offset raw identity')
 bridges=profile['typeBridges']['methodTypeBridges']
 require(any(b['methodIndex']==102308 and b['parameters'][0]['code']==9 and bytes.fromhex(b['parameters'][0]['typeRaw'])[6]==9 and b['returnType']['class']=='RPG.GameCore.TalkSentenceConfigRow' for b in bridges), 'GetData uint32 metadata type')

def source_check(repo, data):
 """Return (hydratedScenes, joins, counts); rows retain original URL and new anchor.

 Each scene has source/sourceSha256/nodePointer/url and exact staticRange/node.
 Each row has talkId/talk_id, text/speaker/hash/speaker_hash/voice, original url,
 anchor, role and isConfigurationReference. A scene URL + '#' + row.anchor is
 the new configuration reference URL. This does not create a spoken owner.
 """
 repo=Path(repo); public_safe(data)
 require(data['schema']==SCHEMA, 'public schema'); source_flags(data)
 require(data['nativeSourceStatus']=='PUBLIC_JSON_SNAPSHOT_NATIVE_EOF_BLOCKED', 'source EOF status')
 require(data['frozenInputs']==FROZEN, 'frozen evidence pins')
 require(data['cohortSha256']=='2b24e7f822e49ecd0dcd130961d59c11290ecb5ffeb15fd82fe1fd651dbd68db' and data['cohortCount']==28059, 'frozen cohort identity')
 require(data['sourceRepository']=='DimbreathBot/TurnBasedGameData' and data['sourceCommit']=='8b178dd48698e5e7b12f0cc319ddab149f2ffc5c', 'public source snapshot identity')
 ids=data['ids']; require(len(ids)==75 and ids==sorted(set(ids)) and all(type(t) is int and 0<t<2**32 for t in ids), 'frozen selected IDs')
 sources=data['sourceRecords']; require(len(sources)==43, 'source node census')
 for src in sources:
  source_flags(src); require(src['sourceUsageKnown'] is True and src['sourceJSONWholeNode'] is True, 'source node extent boundary')
  require(src['nativeSourceStatus']==data['nativeSourceStatus'], 'node EOF status')
  require(not Path(src['source']).is_absolute() and '..' not in Path(src['source']).parts and src['source'].endswith('.json'), 'logical JSON source')
  require(src['archiveMember']=='TurnBasedGameData-'+data['sourceCommit']+'/'+src['source'], 'archive member domain')
  bound=interval(src['node'],ids); require(bound is not None, 'static range is dynamic, malformed, reversed or wraps uint32')
  start,end,selected=bound; span=src['staticRange']; np=src['nodePointer']
  require(span=={'start':start,'end':end,'startPointer':np+'/StartSentenceID/FixedValue/Value','endPointer':np+'/EndSentenceID/FixedValue/Value','inclusive':True,'frozenTalkIds':selected,'status':'SOURCE_STATIC_INTERVAL_REFERENCE','stops':[]}, 'static interval values/pointers/selection')
  endpoints=[{'talkId':v,'field':k,'role':ROLE,'kind':'EXPLICIT_STATIC_ENDPOINT','pointer':np+'/'+k+'/FixedValue/Value'} for k,v in [('StartSentenceID',start),('EndSentenceID',end)] if v in ids]
  require(src['endpoints']==endpoints, 'explicit endpoint domain')
 profile_check(data['nativeProfile'])
 for key,pin in PARTS.items(): require(sha(canonical(data[key]))==pin, 'closed public evidence pin: '+key)
 joins=data['joins']; require(set(joins)=={str(t) for t in ids}, 'Korean join/cohort set')
 docs={}; seen_originals=set()
 for key,j in joins.items():
  tid=int(key); require(j['talk_id']==tid and j['comparisonStatus']=='PASS_PRESERVED_FIELDS_MATCH' and j['differingFields']==[], 'original/current comparison status')
  p=j['preserved']['source']; name=p['file']; require(name.startswith('data/dialogues/') and '..' not in Path(name).parts, 'preserved source domain')
  if name not in docs:
   raw=(repo/name).read_bytes(); require(sha(raw)==p['sha256'], 'preserved Korean file SHA: '+name); docs[name]=json.loads(raw)
  original=pointer(docs[name],p['pointer']); require(original==j['preserved']['row'], 'preserved exact row pointer')
  seen_originals.add((name,p['pointer']))
  for field in ('talk_id','text','speaker','hash','speaker_hash','voice'): require(j[field]==original[field], 'preserved Korean '+field)
  official=j['currentOfficialSource']; table=official['tableRecord']; text=official['textRecord']; speaker=official['speakerRecord']
  require(table['TalkSentenceID']==tid and str(table['TalkSentenceText']['Hash'])==j['hash'] and str(text['hash'])==j['hash'] and table['TalkSentenceText']['Legacy']==text['legacy'] and text['raw']==j['raw'] and readable(j['raw'])==j['text'], 'official text table/hash/legacy/raw boundary')
  require(table.get('VoiceID',0)==j['voice'], 'official voice identity')
  if speaker is None: require(j['speakerRaw'] is None and j['speaker_hash']=='0' and j['speaker']=='화자 미지정' and 'TextmapTalkSentenceName' not in table, 'empty official speaker')
  else: require(str(table['TextmapTalkSentenceName']['Hash'])==j['speaker_hash']==str(speaker['hash']) and table['TextmapTalkSentenceName']['Legacy']==speaker['legacy'] and speaker['raw']==j['speakerRaw'] and readable(speaker['raw'])==j['speaker'], 'official speaker boundary')
  for rec in [table,text]+([speaker] if speaker else []):
   begin=rec.get('_offset',rec.get('offset')); end=rec.get('_end',rec.get('end')); require(type(begin) is int and type(end) is int and 0<=begin<end, 'official record byte bounds')
 records=data['records']; require(len(records)==37 and len({r['source'] for r in records})==37, 'source page census')
 by_scene={s['id']:s for s in data['scenes']}; require(len(by_scene)==len(data['scenes'])==43, 'unique scene IDs')
 hydrated=[]; expected_scenes=[]; expected_records=[]; selected_all=set(); refs=0
 for source in sorted({s['source'] for s in sources}):
  page='range-'+sha(source.encode())[:16]; url='대화/범위-'+page+'.html'; occurrences={}; scene_ids=[]; speakers=[]
  for index,src in enumerate(sources):
   if src['source']!=source: continue
   sid='range-'+sha((source+'\0'+src['nodePointer']).encode())[:16]; rows=[]; hydrated_rows=[]
   for tid in src['staticRange']['frozenTalkIds']:
    occurrences[tid]=occurrences.get(tid,0)+1; anchor=f'talk-{tid}-{occurrences[tid]}'
    row={'talkId':tid,'anchor':anchor,'role':ROLE,'edition':'UNKNOWN','runtimeVerified':False,'nativeSourceWholeEOF':False}; rows.append(row)
    original_url='대사/'+Path(joins[str(tid)]['preserved']['source']['file']).stem+'.html#talk-'+str(tid)
    hydrated_rows.append({**row,**{k:joins[str(tid)][k] for k in ('talk_id','text','speaker','hash','speaker_hash','voice')},'url':original_url,'isConfigurationReference':True})
    speakers.append(joins[str(tid)]['speaker']); selected_all.add(tid); refs+=1
   scene={'id':sid,'recordId':page,'sourceRecordIndex':index,'source':source,'nodePointer':src['nodePointer'],'rows':rows,'url':url}; expected_scenes.append(scene); scene_ids.append(sid)
   hydrated.append({**scene,'sourceSha256':src['sourceSha256'],'staticRange':src['staticRange'],'node':src['node'],'rows':hydrated_rows,'role':ROLE,'edition':'UNKNOWN','runtimeVerified':False,'nativeSourceWholeEOF':False})
  title=' · '.join(list(dict.fromkeys(speakers))[:3]); expected_records.append({'id':page,'title':title,'source':source,'sourceSha256':next(s['sourceSha256'] for s in sources if s['source']==source),'sceneIds':scene_ids,'url':url})
 require(data['scenes']==expected_scenes and records==expected_records, 'derived page/scene/row/anchor/source identity')
 counts={'records':37,'scenes':43,'distinctTalkIds':75,'references':104}; require(data['counts']==counts and refs==104 and selected_all==set(ids) and len(seen_originals)==75, 'complete unique IDs/reference census')
 return hydrated,joins,{**counts,'preservedFiles':len(docs),'wholeNativeFunctions':7,'declaredFields':11}

def walk(obj):
 stack=[('',obj)]
 while stack:
  ptr,x=stack.pop()
  if isinstance(x,dict):
   yield ptr,x
   stack.extend((ptr+'/'+str(k).replace('~','~0').replace('/','~1'),v) for k,v in x.items() if isinstance(v,(dict,list)))
  elif isinstance(x,list): stack.extend((ptr+'/'+str(i),v) for i,v in enumerate(x) if isinstance(v,(dict,list)))

def archive_check(path,data):
 needed={s['source']:s for s in data['sourceRecords']}; docs={}; actual=[]; census={'allJSONFiles':0,'allPlayMissionTalkNodes':0,'validStaticRanges':0,'stoppedRanges':0}
 with tarfile.open(path,'r|gz') as archive:
  for member in archive:
   if not member.isfile() or not member.name.endswith('.json'): continue
   census['allJSONFiles']+=1; raw=archive.extractfile(member).read(); name=member.name.split('/',1)[-1]
   if name in needed:
    src=needed[name]; require(member.name==src['archiveMember'] and len(raw)==src['sourceBytes'] and sha(raw)==src['sourceSha256'], 'archive exact source bytes: '+name); docs[name]=json.loads(raw)
   if b'RPG.GameCore.PlayMissionTalk' not in raw: continue
   for ptr,node in walk(json.loads(raw)):
    if node.get('$type')!='RPG.GameCore.PlayMissionTalk': continue
    census['allPlayMissionTalkNodes']+=1; bound=interval(node,data['ids']); census['validStaticRanges' if bound else 'stoppedRanges']+=1
    if bound and bound[2]: actual.append((name,ptr,bound[2]))
    elif any(number(node.get(k)) in data['ids'] for k in ('StartSentenceID','EndSentenceID')): actual.append((name,ptr,[]))
 require(len(docs)==37, 'archive required sources absent')
 for src in data['sourceRecords']:
  obj=docs[src['source']]; require(pointer(obj,src['nodePointer'])==src['node'], 'archive exact whole node pointer')
  span=src['staticRange']; require(pointer(obj,span['startPointer'])==span['start'] and pointer(obj,span['endPointer'])==span['end'], 'archive exact endpoint pointers')
 expected=[(s['source'],s['nodePointer'],s['staticRange']['frozenTalkIds']) for s in data['sourceRecords']]
 require(sorted(actual)==sorted(expected), 'archive full selected reference coverage')
 for key,value in census.items(): require(value==data['sourceCensus'][key], 'archive census '+key)
 return {**census,'matchedSourceFiles':37,'matchedNodes':43}

def game_check(game_root,profile):
 root=Path(game_root); root=root.parent if root.name=='StarRail_Data' else root
 paths={'GameAssembly.dll':root/'GameAssembly.dll','global-metadata.dat':root/'StarRail_Data/il2cpp_data/Metadata/global-metadata.dat'}
 with paths['GameAssembly.dll'].open('rb') as af, paths['global-metadata.dat'].open('rb') as mf:
  with mmap.mmap(af.fileno(),0,access=mmap.ACCESS_READ) as a, mmap.mmap(mf.fileno(),0,access=mmap.ACCESS_READ) as m:
   for key,raw in [('GameAssembly.dll',a),('global-metadata.dat',m)]: require(sha(raw)==profile['inputs'][key], 'current game input SHA '+key)
   pe=struct.unpack_from('<I',a,0x3c)[0]; nsec=struct.unpack_from('<H',a,pe+6)[0]; optlen=struct.unpack_from('<H',a,pe+20)[0]; opt=pe+24
   require(struct.unpack_from('<H',a,opt)[0]==0x20b,'PE32+'); base=struct.unpack_from('<Q',a,opt+24)[0]; sections=[]
   for i in range(nsec):
    size,va,rawsize,raw=struct.unpack_from('<IIII',a,opt+optlen+40*i+8); sections.append((va,max(size,rawsize),raw))
   def rvaoff(rva): return next(raw+rva-va for va,size,raw in sections if va<=rva<va+size)
   prva,psz=struct.unpack_from('<II',a,opt+112+3*8); po=rvaoff(prva); extents={}
   for i in range(0,psz,12):
    start,end,_=struct.unpack_from('<III',a,po+i); extents[start]=end
   def same(raw,offset,hex_value):
    value=bytes.fromhex(hex_value); require(raw[offset:offset+len(value)]==value, 'current exact raw record offset '+str(offset))
   for f in profile['rawFunctions']['functions']:
    rva=int(f['requestedVA'],16)-base; require(rva in extents and extents[rva]-rva==f['bytes'] and rvaoff(rva)==f['fileOffset'], '.pdata complete function extent'); same(a,f['fileOffset'],f['raw'])
   for row in profile['methods']['matches']: same(m,row['metadataFileOffset'],row['metadataRaw']); same(a,row['methodPointerFileOffset'],row['methodPointerRaw'])
   for cls in profile['rawFields']:
    same(m,cls['metadataFileOffset'],cls['typeDefinitionRaw'])
    for f in cls['fields']: same(m,f['metadataFileOffset'],f['metadataRaw']); same(a,f['typeRecordFileOffset'],f['typeRecordRaw']); same(m,f['runtimeFieldOffsetFile'],f['runtimeFieldOffsetRaw'])
   for bridge in profile['typeBridges']['methodTypeBridges']:
    for p in bridge['parameters']: same(m,p['parameterFileOffset'],p['parameterRaw']); same(a,p['typeFileOffset'],p['typeRaw'])
    p=bridge['returnType']; same(a,p['typeFileOffset'],p['typeRaw'])
 return {'wholePdataFunctions':7,'methods':7,'fields':11,'typedMethodBridges':2}

class Rendered(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True); self.ids=[]; self.rows=[]; self.current=None; self.capture=None; self.depth=0; self.notes=[]; self.proofs={}; self.has_return=False; self.native=False; self.native_table=None
 def handle_starttag(self,tag,pairs):
  attrs=dict(pairs)
  if 'id' in attrs: self.ids.append(attrs['id'])
  if 'data-catalog-return' in attrs: self.has_return=True
  if 'data-range-native-proof' in attrs: self.native=True
  if 'data-range-talk-id' in attrs:
   require(self.current is None, 'nested range row'); self.current={'attrs':attrs,'text':'','speaker':'','links':[]}; self.rows.append(self.current)
  if self.current and tag=='a': self.current['links'].append(attrs.get('href',''))
  if self.capture and tag not in ('br','hr','img','input','meta','link','wbr'): self.depth+=1
  elif self.current and tag=='p' and attrs.get('id')==self.current['attrs']['data-range-anchor']: self.capture=('text',self.current); self.depth=1
  elif self.current and 'data-range-speaker' in attrs: self.capture=('speaker',self.current); self.depth=1
  elif 'data-range-note' in attrs: self.capture=('note',[]); self.depth=1
  elif 'data-range-node' in attrs: self.capture=('proof',(attrs['data-range-node'],[])); self.depth=1
  elif 'data-range-native-table' in attrs: self.capture=('native',[]); self.depth=1
 def handle_endtag(self,tag):
  if self.capture:
   self.depth-=1
   if self.depth==0:
    kind,obj=self.capture
    if kind=='note': self.notes.append(''.join(obj))
    if kind=='proof': self.proofs[obj[0]]=''.join(obj[1])
    if kind=='native': self.native_table=''.join(obj)
    self.capture=None
  if tag=='div' and self.current: self.current=None
 def handle_data(self,text):
  if not self.capture: return
  kind,obj=self.capture
  if kind in ('text','speaker'): obj[kind]+=text
  elif kind in ('note','native'): obj.append(text)
  else: obj[1].append(text)

def ui_wire_rows(text, shard_bodies=None):
 # Decode the actual shared runtime independently of the publication producer.
 sparse=list(re.finditer(r'window\.__starrailPublicationUI=new Array\(([0-9]+)\);',text))
 if sparse:
  require(len(sparse)==1 and shard_bodies is not None,'unique sparse UI declaration and actual shards')
  require(not re.search(r'__starrailPublicationLoadUI\(JSON|window\.__starrailPublicationUI=JSON',text),'mixed UI wire declarations')
  count=int(sparse[0][1]); require(0<count<=2**53-1,'sparse UI total slot count')
  manifests=list(re.finditer(r'window\.__starrailPublicationUIURLs=(\[[^\n;]*\]);',text))
  require(len(manifests)==1,'unique actual UI URL manifest')
  urls=json.loads(manifests[0][1]); require(isinstance(urls,list) and urls and all(isinstance(url,str) for url in urls) and len(urls)==len(set(urls)),'UI URL manifest domain')
  require(set(shard_bodies)==set(urls),'actual UI shards and manifest URL set')
  rows={}
  for identifier,url in enumerate(urls):
   matches=list(re.finditer(r'__starrailPublicationLoadUIShard\(([0-9]+),"([A-Za-z0-9+/=]+)",([0-9]+),([0-9]+)\);',shard_bodies[url]))
   require(len(matches)==1 and shard_bodies[url].strip()==matches[0][0],'unique whole actual UI shard call')
   match=matches[0]; require(int(match[1])==identifier,'actual UI shard identifier/manifest order')
   raw=gzip.decompress(base64.b64decode(match[2],validate=True)); require(len(raw)==int(match[3]) and len(raw)<=2000000,'actual UI shard decoded byte bound')
   values=json.loads(raw.decode('utf8',errors='strict')); require(isinstance(values,list) and len(values)==int(match[4]) and 0<len(values)<=512,'actual UI shard count/bound')
   for pair in values:
    require(isinstance(pair,list) and len(pair)==2 and type(pair[0]) is int and 0<=pair[0]<count and isinstance(pair[1],str) and pair[0] not in rows,'sparse UI wire slot type/range/uniqueness')
    rows[pair[0]]=pair[1]
  require(len(rows)==count,'sparse UI complete original slot census')
  return [rows[i] for i in range(count)]
 indexed_matches=list(re.finditer(r'__starrailPublicationLoadUI\(JSON\.parse\(__starrailPublicationDecode\("([A-Za-z0-9+/=]+)",([0-9]+)\)\),([0-9]+)\);',text))
 dense_matches=list(re.finditer(r'window\.__starrailPublicationUI=JSON\.parse\(__starrailPublicationDecode\("([A-Za-z0-9+/=]+)",([0-9]+)\)\);',text))
 require(len(indexed_matches)+len(dense_matches)==1,'unique supported UI wire declaration')
 indexed=indexed_matches[0] if indexed_matches else None; dense=dense_matches[0] if dense_matches else None
 match=indexed or dense; raw=gzip.decompress(base64.b64decode(match[1],validate=True))
 require(len(raw)==int(match[2]),'UI wire decoded byte length')
 values=json.loads(raw.decode('utf8',errors='strict')); require(isinstance(values,list),'UI wire array')
 if dense:
  require(all(isinstance(row,str) for row in values),'dense UI wire text slots'); return values
 count=int(match[3]); require(len(values)==count,'indexed UI wire slot count')
 rows={}
 for pair in values:
  require(isinstance(pair,list) and len(pair)==2 and type(pair[0]) is int and 0<=pair[0]<count and isinstance(pair[1],str) and pair[0] not in rows,'indexed UI wire slot type/range/uniqueness')
  rows[pair[0]]=pair[1]
 return [rows[i] for i in range(count)]

def publication_metadata_expander(dist,report_path):
 from verify_versioned_timeline_text import expand_proof_slots,relative
 report=load(report_path); require(report['schema']=='starrail-publication-dedup.v3','publication metadata receipt schema')
 runtimes=[]; runtime_assets=[]; actual_assets={}
 for name,record in report['assets'].items():
  require(re.fullmatch(r'[0-9a-f]{20}\.(?:js|css)',name),'shared metadata asset path')
  raw=(Path(dist)/'_shared'/name).read_bytes(); require(sha(raw)==record['sha256'],'actual shared metadata asset SHA')
  actual_assets[name]=raw
  if record['kind']=='proof-runtime': runtimes.append(raw.decode('utf8',errors='strict')); runtime_assets.append((name,raw))
 require(len(runtimes)==1,'one actual publication UI runtime')
 ui_shards=report.get('uiShards'); shard_bodies=None; slot_shards={}
 if ui_shards is not None:
  require(isinstance(ui_shards,dict) and ui_shards,'publication UI shard receipt domain')
  shard_bodies={}
  for key,record in ui_shards.items():
   require(re.fullmatch(r'0|[1-9][0-9]*',key) and type(record['id']) is int and record['id']==int(key),'UI shard receipt identifier')
   url=record['url']; require(re.fullmatch(r'/starrail-quests/_shared/[0-9a-f]{20}\.js',url),'actual UI shard path')
   name=url.rsplit('/',1)[1]; require(name in actual_assets,'UI shard absent from actual asset census')
   raw=actual_assets[name]; require(len(raw)==record['assetBytes'] and sha(raw)==record['assetSha256'],'actual UI shard receipt asset SHA/size')
   body=raw.decode('utf8',errors='strict'); shard_bodies[url]=body
   match=re.fullmatch(r'__starrailPublicationLoadUIShard\(([0-9]+),"([A-Za-z0-9+/=]+)",([0-9]+),([0-9]+)\);\s*',body)
   require(match is not None and int(match[1])==int(key),'UI shard receipt actual call')
   decoded=gzip.decompress(base64.b64decode(match[2],validate=True)); pairs=json.loads(decoded.decode('utf8',errors='strict'))
   require(len(decoded)==record['rawBytes']==int(match[3]) and sha(decoded)==record['rawSha256'] and match[2]==record['payload'],'UI shard receipt actual payload')
   require(isinstance(pairs,list) and all(isinstance(pair,list) and len(pair)==2 for pair in pairs) and len(pairs)==record['count']==int(match[4]) and [pair[0] for pair in pairs]==record['slots'],'UI shard receipt actual original slots')
   for pair in pairs:
    require(type(pair[0]) is int and pair[0] not in slot_shards,'UI shard receipt duplicate original slot'); slot_shards[pair[0]]=int(key)
 rows=ui_wire_rows(runtimes[0],shard_bodies); require(rows==report['uiPool'],'actual UI wire differs from receipt slots')
 if ui_shards is not None:
  runtime=report['uiRuntime']; name,raw=runtime_assets[0]
  require(runtime['url']=='/starrail-quests/_shared/'+name and runtime['sha256']==sha(raw) and runtime['bytes']==len(raw),'actual sparse UI runtime receipt')
  require(runtime['totalSlots']==len(rows) and runtime['maxSlots']==512 and runtime['maxRawBytes']==2000000 and runtime['loader']=='indexed-local-ui.v1','UI runtime original census and bounds')
 for shard in report['proofShards'].values():
  url=unquote(shard['url']); require(url.startswith('/starrail-quests/'),'actual metadata shard base')
  raw=(Path(dist)/relative(url[len('/starrail-quests/'):])).read_bytes()
  require(sha(raw)==shard['assetSha256'],'actual metadata shard SHA')
 for name,record in report['proofCodecFiles'].items():
  raw=(Path(dist)/'_publication'/relative(name)).read_bytes()
  require(len(raw)==record['bytes'] and sha(raw)==record['sha256'],'actual publication codec SHA/size')
 pattern=re.compile(r'<script>__sp\(([0-9]+)\);</script>')
 def slot(match):
  index=int(match[1]); require(0<=index<len(rows),'publication UI slot bounds'); return rows[index]
 def expand(text):
  if ui_shards is not None:
   selected=list(re.finditer(r'<script\b[^>]*\bdata-pc-runtime="([^"]*)"[^>]*></script>',text))
   require(len(selected)==1,'unique page UI shard selector')
   value=selected[0][1]; require(value=='' or re.fullmatch(r'(?:0|[1-9][0-9]*)(?:,(?:0|[1-9][0-9]*))*',value),'page UI shard selector grammar')
   identifiers=[] if not value else list(map(int,value.split(',')))
   require(identifiers==sorted(set(identifiers)) and all(str(i) in ui_shards for i in identifiers),'page UI shard selector identifier domain')
   required=set(); visiting=set()
   def visit(index):
    require(0<=index<len(rows),'page UI closure slot bounds')
    require(index not in visiting,'cyclic page UI closure')
    require(len(visiting)<15,'excessive page UI closure nesting')
    if index in required:return
    visiting.add(index)
    for nested in pattern.finditer(rows[index]):visit(int(nested[1]))
    visiting.remove(index); required.add(index)
   for match in pattern.finditer(text):visit(int(match[1]))
   require(identifiers==sorted({slot_shards[index] for index in required}),'page UI shard selector misses or substitutes required closure')
   runtime=report['uiRuntime']; require(selected[0][0]==f'<script src="{runtime["url"]}" data-pc-runtime="{value}"></script>','page UI selector runtime URL and exact bootstrap')
   heads=list(re.finditer(r'<head\b[^>]*>[\s\S]*?</head>',text,re.I)); require(len(heads)==1 and heads[0].start()<=selected[0].start()<selected[0].end()<=heads[0].end(),'page UI bootstrap inside single head')
   first=pattern.search(text); require(first is None or selected[0].end()<=first.start(),'page UI bootstrap precedes first UI call')
  for _ in range(16):
   updated=pattern.sub(slot,text)
   if updated==text:
    require(not pattern.search(text),'cyclic publication UI metadata'); break
   text=updated
  else: raise ValueError('cyclic or excessive publication UI metadata nesting')
  return expand_proof_slots(text,report)
 return expand

def dist_check(dist,data,scenes,report_path=None):
 count=0; checked_ids=set(); pages=0
 expand=None
 for record in data['records']:
  path=Path(dist)/record['url']; require(path.is_file(), 'rendered range page absent: '+record['url']); static=path.read_text(encoding='utf8'); page=Rendered(); page.feed(static); page.close()
  require(len(page.ids)==len(set(page.ids)), 'duplicate page anchors')
  require(page.native and NOTE in page.notes,'static range native disclosure/unknown edition note')
  subset=[s for s in scenes if s['recordId']==record['id']]; expected=[r for s in subset for r in s['rows']]
  require(len(page.rows)==len(expected), 'rendered reference census')
  for observed,row in zip(page.rows,expected):
   attrs=observed['attrs']; require(attrs['data-range-talk-id']==str(row['talk_id']) and attrs['data-range-role']==ROLE and attrs['data-reading-kind']=='original' and attrs['data-range-anchor']==row['anchor'] and page.ids.count(row['anchor'])==1, 'rendered original role/ID/anchor')
   require(observed['text']==row['text'] and observed['speaker']=='설정 참조 · '+row['speaker'], 'rendered exact original/speaker')
   require(any(unquote(urlsplit(link).path).endswith('/'+row['url'].split('#')[0]) and unquote(urlsplit(link).fragment)==row['url'].split('#')[1] for link in observed['links']), 'original return link')
   checked_ids.add(row['talk_id']); count+=1
  expanded=static
  if re.search(r'__sp\(|__spr\(|__starrailPublicationWrite\(',static):
   if expand is None: expand=publication_metadata_expander(dist,report_path or Path(dist).resolve().parent/'.codex-work/publication-build-report.json')
   expanded=expand(static)
  proof=Rendered(); proof.feed(expanded); proof.close()
  require(proof.rows==page.rows,'publication metadata expansion changed static originals')
  require(len(proof.ids)==len(set(proof.ids)),'expanded range duplicate anchors')
  require(proof.has_return and proof.native and NOTE in proof.notes,'range return/native proof/unknown edition note')
  require(proof.native_table is not None and json.loads(proof.native_table)==native_summary(data['nativeProfile']),'rendered native function/field proof table')
  for scene in subset: require(json.loads(proof.proofs[scene['id']])==scene['node'], 'rendered exact whole source node')
  pages+=1
 require(checked_ids==set(data['ids']) and count==104, 'rendered all75 originals')
 return {'pages':pages,'references':count,'distinctTalkIds':len(checked_ids),'sourceNodes':43,'staticOriginalsCheckedBeforeMetadataExpansion':True,'actualUIWireVerified':expand is not None}

def selftest(repo,data):
 tid=data['ids'][0]; sample={'$type':'RPG.GameCore.PlayMissionTalk','StartSentenceID':{'IsDynamic':False,'FixedValue':{'Value':tid}},'EndSentenceID':{'IsDynamic':False,'FixedValue':{'Value':tid}}}
 require(interval(sample,[tid])==(tid,tid,[tid]), 'single inclusive positive canary')
 cases=[('wrong-type',lambda n:n.update({'$type':'RPG.GameCore.SharedInt'})),('dynamic',lambda n:n['StartSentenceID'].update(IsDynamic=True)),('nonboolean-mode',lambda n:n['StartSentenceID'].update(IsDynamic=0)),('implicit-mode',lambda n:n['StartSentenceID'].pop('IsDynamic')),('missing-fixed',lambda n:n['StartSentenceID'].pop('FixedValue')),('boolean-ID',lambda n:n['StartSentenceID']['FixedValue'].update(Value=True)),('fraction-ID',lambda n:n['StartSentenceID']['FixedValue'].update(Value=tid+0.5)),('zero-ID',lambda n:n['StartSentenceID']['FixedValue'].update(Value=0)),('overflow-ID',lambda n:n['StartSentenceID']['FixedValue'].update(Value=2**32)),('nonfinite-ID',lambda n:n['StartSentenceID']['FixedValue'].update(Value=float('nan'))),('reversed',lambda n:n['StartSentenceID']['FixedValue'].update(Value=tid+1)),('uint32-wrap',lambda n:n['EndSentenceID']['FixedValue'].update(Value=2**32-1)),('endpoint-only',lambda n:n.pop('EndSentenceID'))]
 passed=[]
 for label,change in cases:
  node=copy.deepcopy(sample); change(node); require(interval(node,[tid]) is None,'accepted semantic negative '+label); passed.append(label)
 mutations=[('spoken-role',lambda d:d.update(role='DIALOGUE')),('edition-inference',lambda d:d.update(edition='official')),('execution-inference',lambda d:d.update(runtimeVerified=True)),('native-EOF-inference',lambda d:d.update(nativeSourceWholeEOF=True)),('interval-pointer-domain',lambda d:d['sourceRecords'][0]['staticRange'].update(startPointer='/TalkSentenceID')),('row-anchor-domain',lambda d:d['scenes'][0]['rows'][0].update(anchor='talk-0-1')),('Korean-body-corruption',lambda d:d['joins'][str(tid)].update(text='changed')),('profile-opcode-corruption',lambda d:d['nativeProfile']['rawFunctions']['functions'][0].update(raw='00'))]
 for label,change in mutations:
  altered=copy.deepcopy(data); change(altered)
  try: source_check(repo,altered)
  except (ValueError,KeyError,IndexError): passed.append(label)
  else: raise ValueError('accepted public proof mutation '+label)
 return passed

def main():
 ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]); ap.add_argument('--data',type=Path); ap.add_argument('--archive',type=Path); ap.add_argument('--game-root',type=Path); ap.add_argument('--dist',type=Path); ap.add_argument('--publication-report',type=Path); ap.add_argument('--selftest',action='store_true'); ap.add_argument('--report',type=Path); args=ap.parse_args()
 path=args.data or args.repo/'data/mission-talk-range-dialogue.json'; raw=path.read_bytes(); require(b'\r' not in raw and sha(raw)==DATA_SHA,'public file exact LF SHA'); data=json.loads(raw); scenes,joins,counts=source_check(args.repo,data)
 report={'schema':'starrail-mission-talk-range-replay.v1','status':'PASS','publicDataSha256':sha(raw),'counts':counts,'sourceCheck':'PASS_CLOSED_PUBLIC_PROOF_AND_PRESERVED_KOREAN','archive':'NOT_REQUESTED','currentNative':'NOT_REQUESTED','rendered':'NOT_REQUESTED','role':ROLE,'edition':'UNKNOWN','runtimeVerified':False,'nativeSourceWholeEOF':False}
 if args.archive: report['archive']=archive_check(args.archive,data)
 if args.game_root: report['currentNative']=game_check(args.game_root,data['nativeProfile'])
 if args.dist: report['rendered']=dist_check(args.dist,data,scenes,args.publication_report)
 if args.selftest: report['semanticNegativeCases']=selftest(args.repo,data)
 if args.report: args.report.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
 print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__': main()
