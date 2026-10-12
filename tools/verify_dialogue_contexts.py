"""Independently replay attribution, frozen row references and every new HTML."""
import argparse, hashlib, json, tarfile
from collections import Counter, defaultdict
from pathlib import Path
from verify_site import Page

SITE=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text('utf8'))
def sha(b):return hashlib.sha256(b).hexdigest()
def at(obj,pointer):
 for part in pointer.strip('/').split('/'):
  key=part.replace('~1','/').replace('~0','~');obj=obj[int(key)] if isinstance(obj,list) else obj[key]
 return obj
def require(condition,message):
 if not condition:raise AssertionError(message)

def row_targets(group,row,payload):
 if group['source']!='ExcelOutput/HeartDialTalk.json':return []
 ids=dict.fromkeys(f for ref in row['references'] for f in ref['recordContext']['fields'].get('FloorIDList',[]))
 return [payload['regions'][str(f)] for f in ids if str(f) in payload['regions'] and payload['regions'][str(f)]['name']!='지역 이름 미확인']

def verify_deep_reader_links(deep,rows,official):
 """Resolve links to exact retained mission or dedicated scene occurrences."""
 require(deep['schema']=='starrail-deep-dialogue-attribution.v1','deep attribution schema')
 ids=deep['timelineReaderIds'];require(all(type(tid) is int and 0<tid<2**32 for tid in ids) and len(ids)==len(set(ids)),'deep reader ID domain')
 targets={}
 for filename in ('timeline-mission-dialogue.json','native-timeline-mission-dialogue.json'):
  for mid,scenes in read(SITE/'data'/filename)['missions'].items():
   for scene in scenes:
    for index,row in enumerate(scene['rows'],1):
     url='문서/'+mid+'.html#'+scene['anchor']+'-row-'+str(index)
     role='NATIVE_CHOICE' if scene.get('recordType')=='NATIVE_TIMELINE_CHOICES' else 'NON_SPOKEN_OPTION_REFERENCE' if row.get('label')=='선택지' else 'SPOKEN'
     targets[(url,row['talk_id'])]={'talkId':row['talk_id'],'role':role,'source':scene['source'],'korean':row,'proof':row.get('choiceSource') or row.get('timelineClip')}
    for option in scene.get('optionReferences',[]):
     tid=option['talk_id'];original=rows.get(tid) or official.get(tid)
     require(original and option['text']==original['text'] and str(option['hash'])==str(original['hash']),'retained Timeline option Korean reference differs')
     require(option.get('role')=='NON_SPOKEN_OPTION_REFERENCE' and option.get('references') and option.get('objectSha256'),'retained Timeline option source proof absent')
     url='문서/'+mid+'.html#'+scene['anchor']
     targets[(url,tid)]={'talkId':tid,'role':'NON_SPOKEN_OPTION_REFERENCE','source':scene['source'],'korean':original,'proof':option}
 scene_path=SITE/'data/deep-timeline-dialogue.json'
 require(scene_path.is_file(),'deep scene reader source absent')
 require(sha(scene_path.read_bytes())==deep['evidence']['deepTimelineSha256'],'deep scene input identity differs')
 scenes=read(scene_path);require(scenes['schema']=='starrail-deep-timeline-dialogue.v1','deep scene schema')
 source_cache={}
 def hydrate(tid):
  join=scenes['joins'][str(tid)];source=join['preservedSource'];file=source['file']
  require(file.startswith('data/dialogues/') and file.endswith('.json') or file=='data/official-talk-library.json','deep Korean source domain')
  require('..' not in file.split('/') and '\\' not in file,'deep Korean source path')
  if file not in source_cache:
   raw=(SITE/file).read_bytes();source_cache[file]=(sha(raw),json.loads(raw))
  digest,document=source_cache[file];require(digest==source['sha256'],'deep Korean source hash changed')
  row=at(document,source['pointer']);require(row['talk_id']==tid,'deep Korean source pointer differs')
  expected=rows[tid] if file.startswith('data/dialogues/') else official[tid]
  for field in ('text','speaker','hash','speaker_hash','voice'):require(str(row[field])==str(expected[field]),'deep Korean preserved field differs')
  return row
 for scene in scenes['scenes']:
  anchors=set()
  for row in scene['rows']:
   require(row['anchor'] not in anchors,'duplicate deep occurrence anchor');anchors.add(row['anchor'])
   require(row['role'] in ('SPOKEN','SCREEN_TEXT','NON_SPOKEN_OPTION_REFERENCE','NATIVE_CHOICE'),'unknown deep source role')
   url='대화/연출-'+scene['id']+'.html#'+row['anchor'];require((url,row['talkId']) not in targets,'duplicate deep reader target')
   require(str(row['talkId']) in scenes['joins'],'deep Korean join absent')
   if row['role']=='NATIVE_CHOICE':
    require(row.get('parentTaskType')=='RPG.GameCore.PlayOptionTalk' and row.get('option',{}).get('$type')=='RPG.GameCore.OptionTalkInfo' and row['option'].get('TalkSentenceID')==row['talkId'],'deep native choice consumer differs')
   else:
    expected_role={'PlaySimpleTalkClip':'SPOKEN','BPTalkClip':'SPOKEN','ScreenTransferTextClip':'SCREEN_TEXT','SimpleTalkMarkerClip':'NON_SPOKEN_OPTION_REFERENCE'}
    require(expected_role.get(row.get('object',{}).get('class'))==row['role'],'deep native clip role differs')
    require(row.get('idField',{}).get('value')==row['talkId'],'deep native clip Talk field differs')
    if row['object']['class']=='BPTalkClip':
     span=row['idField'].get('span');require(row['idField'].get('field')=='BPTalkClip.TalkSentenceID' and isinstance(span,list) and len(span)==2 and all(type(value) is int for value in span) and 0<=span[0]<span[1]<=row['object']['byteSize'] and span[1]-span[0]==4,'deep BP exact native field differs')
   targets[(url,row['talkId'])]={'talkId':row['talkId'],'role':row['role'],'source':scene['source'],'korean':hydrate(row['talkId']),'proof':row.get('proof') or scene.get('proof')}
 for tid in ids:
  links=deep['readerLinks'].get(str(tid));require(isinstance(links,list) and links,'deep reader links absent')
  require(tid in rows or tid in official,'deep reader Korean ID absent')
  for link in links:
   require((link['url'],tid) in targets,'deep reader URL/occurrence absent '+link['url'])
   target=targets[(link['url'],tid)];require(target['talkId']==tid and target['source']==link['source'] and target['role']==link['role'],'deep reader ID/source/role mismatch')
   require(target['proof'],'deep reader source proof absent')
   native=target['korean'];original=rows.get(tid) or official[tid]
   for field in ('text','speaker','hash','speaker_hash','voice'):
    require(field in native and str(native[field])==str(original[field]),'deep reader Korean '+field+' differs')
 return set(ids)

class ContextPage(Page):
 def __init__(self):
  super().__init__();self.context_rows=[];self.div_depth=0;self.row_depth=None;self.current_row=None;self.span_depth=0;self.label_depth=None;self.native_records=[];self.current_native=None;self.directory_records=[];self.target_active=False
 def handle_starttag(self,tag,attrs):
  super().handle_starttag(tag,attrs);a=dict(attrs)
  if tag=='a' and 'data-source-record' in a:self.directory_records.append(a)
  if tag=='pre' and 'data-native-source-record' in a:
   self.current_native={'talkId':int(a['data-native-talk-id']),'pointer':a['data-native-source-record'],'text':''};self.native_records.append(self.current_native)
  if self.current_row and 'data-context-usage' in a:self.current_row['usage']=a['data-context-usage']
  if self.current_row and 'data-context-target-regions' in a:
   self.current_row.update(targets=a['data-context-target-regions'],targetLabel='');self.target_active=True
  if tag=='div':
   self.div_depth+=1
   if 'data-context-talk' in a:
    require(self.current_row is None,'nested context row')
    self.current_row={'talkId':int(a['data-context-talk']),'attributes':a,'label':''};self.context_rows.append(self.current_row);self.row_depth=self.div_depth
  if tag=='span':
   self.span_depth+=1
   if self.current_row and 'rw-source-speaker' in a.get('class','').split():self.label_depth=self.span_depth
 def handle_endtag(self,tag):
  super().handle_endtag(tag)
  if tag=='pre':self.current_native=None
  if tag=='p':self.target_active=False
  if tag=='span':
   if self.label_depth==self.span_depth:self.label_depth=None
   self.span_depth-=1
  if tag=='div':
   if self.row_depth==self.div_depth:self.row_depth=None;self.current_row=None
   self.div_depth-=1
 def handle_data(self,data):
  super().handle_data(data)
  if self.current_native is not None:self.current_native['text']+=data
  if self.current_row and self.target_active:self.current_row['targetLabel']+=data
  if self.current_row and self.label_depth is not None:self.current_row['label']+=data

CAKE_CONFIG_PROOF = {'schema': 'starrail-cake-configured-talk-domain.v1',
 'role': 'NON_SPOKEN_CONFIGURATION_REFERENCE',
 'tableSha256': '16f6e2c4aef193c77b488aeb76719c7b18245dec16a65d2b967a045b4bda7a51',
 'nativeSource': {'literal': 'ExcelOutput/CakeConfig.json',
                  'nativePath': 'BakedConfig/ExcelOutput/CakeConfig.bytes',
                  'nameHash': '10210098847508089820',
                  'catalogSha256': '0b983e2c487a21dd0074c4bec24ac5fc46531eb650a97c22279cb2188f522027',
                  'pack': '1efaad7a4e7c92a8a12c66cffbe3b50a.bytes',
                  'packSha256': 'ae6cc8e41213ccecc430a346909daf38ff4013d6b1441ddba384032d77b3ffd4',
                  'offset': 755732,
                  'length': 11677,
                  'entrySha256': 'efd312eddd9711633fcb8a9270abe46bdeabaf29df0869aa2545b4c6e47868be',
                  'fullFieldEOF': 11677,
                  'tableRows': 27,
                  'schema': [['ID', 'int'],
                             ['NPCID', 'int'],
                             ['RuanMadeCakeName', 'hash'],
                             ['CatCakeHeadIcon', 'str'],
                             ['CatCakeMiniIcon', 'str'],
                             ['CatCakeTailPath', 'str'],
                             ['CatCaughtLines', ['int']],
                             ['CatMissedLines', ['int']],
                             ['CatTailColour', 'int'],
                             ['RuanMadeCakeStory', 'hash'],
                             ['CatMatPath', 'str'],
                             ['CakeDarkMatPath', 'str']]},
 'metadataSha256': '66502e9b7b44686829a53715e05c50d72d354fe3007e4c65dc7430f8f73d7a22',
 'assemblySha256': '9b75ecd0b1eb44b238a040e556c09ba26d293a524953f85bffd9f78d799a5f41',
 'bridges': {'CatCaughtLines': {'field': 'CatCaughtLines',
                                'typedProperty': 'CaughtTalkSentenceIDs',
                                'metadata': {'fieldIndex': 59628,
                                             'name': 'CatCaughtLines',
                                             'typeIndex': 465134,
                                             'metadataFileOffset': 795808,
                                             'metadataRaw': 'aa7d507b351d4089',
                                             'typeRecordFileOffset': 87594736,
                                             'typeRecordRaw': '7e00000006001d00',
                                             'candidateTypeData': 126,
                                             'candidateTypeCode': 29,
                                             'candidateTypeTarget': None,
                                             'candidateFieldAttrs': 6,
                                             'candidateNonSerialized': False,
                                             'candidatePublic': True,
                                             'candidateStatic': False,
                                             'candidateInitOnly': False,
                                             'candidateLiteral': False,
                                             'candidateBitFlags': 0,
                                             'runtimeFieldOffset': 32,
                                             'runtimeFieldOffsetFile': 83730384,
                                             'runtimeFieldOffsetRaw': '20000000',
                                             'primitiveIntegerDefault': None,
                                             'fieldRecordSource': 'global-metadata.dat',
                                             'runtimeFieldOffsetSource': 'global-metadata.dat',
                                             'typeRecordSource': 'GameAssembly.dll'},
                                'getter': {'va': '0x18c8dfec0',
                                           'sha256': '8bbc497fa1dcc1c6e555287f52929e4dc37b1e68d82729ae4c0a70124e814731',
                                           'getDataCall': {'va': '0x18c8dfeef',
                                                           'bytes': 'e82c628710',
                                                           'mnemonic': 'call',
                                                           'operands': '0x19d156120',
                                                           'directTarget': '0x19d156120'},
                                           'fieldLoad': {'va': '0x18c8dfef9',
                                                         'bytes': '488b4020',
                                                         'mnemonic': 'mov',
                                                         'operands': 'rax, qword ptr [rax + 0x20]'}},
                                'getDataReturn': {'class': 'MENPOEFIHBO',
                                                  'method': {'methodIndex': 88036,
                                                             'name': 'LMBKNCAIDLC',
                                                             'declaringTypeIndex': 12929,
                                                             'parameterCount': 1,
                                                             'returnTypeIndex': 56436,
                                                             'metadataFileOffset': 64997564,
                                                             'metadataRaw': 'bc749f6d9991a675bdc27ddadc9d715cbdf2605f2e0d3f887dc3',
                                                             'pointerTableFileOffset': 77449024,
                                                             'nativePointerVA': 6930391328,
                                                             'nativeRVA': 487940384,
                                                             'nativeFileOffset': 477963040,
                                                             'nativeFirst64': '564883ec6089ce803d10846bec000f84fb000000488b0d4d4424ec80b9b7000000000f840c010000803d01e81fec007519488b0d304424ec80b9b7000000000f',
                                                             'nativeFirst64Sha256': '95befebf4a746d25a7cefed51f5c603da814396ad9d6a0528c9bbf4d5d2e166b',
                                                             'metadataSource': 'global-metadata.dat'},
                                                  'returnType': {'typeIndex': 56436,
                                                                 'offset': 84325152,
                                                                 'raw': '8032000000001200',
                                                                 'data': 12928,
                                                                 'code': 18,
                                                                 'class': 'RPG.GameCore.CakeConfigRow',
                                                                 'source': 'GameAssembly.dll'}},
                                'nativeRowPresenceSlot': 6,
                                'nativeRowPresenceInstruction': {'va': '0x19d546667',
                                                                 'bytes': 'f6c340',
                                                                 'mnemonic': 'test',
                                                                 'operands': 'bl, 0x40'},
                                'nativeRowDestinationInstruction': {'va': '0x19d54667f',
                                                                    'bytes': '4883c720',
                                                                    'mnemonic': 'add',
                                                                    'operands': 'rdi, 0x20'}},
             'CatMissedLines': {'field': 'CatMissedLines',
                                'typedProperty': 'FinishedTalkSentenceIDs',
                                'metadata': {'fieldIndex': 59630,
                                             'name': 'CatMissedLines',
                                             'typeIndex': 465134,
                                             'metadataFileOffset': 795824,
                                             'metadataRaw': 'b8130cd435b3fbe1',
                                             'typeRecordFileOffset': 87594736,
                                             'typeRecordRaw': '7e00000006001d00',
                                             'candidateTypeData': 126,
                                             'candidateTypeCode': 29,
                                             'candidateTypeTarget': None,
                                             'candidateFieldAttrs': 6,
                                             'candidateNonSerialized': False,
                                             'candidatePublic': True,
                                             'candidateStatic': False,
                                             'candidateInitOnly': False,
                                             'candidateLiteral': False,
                                             'candidateBitFlags': 0,
                                             'runtimeFieldOffset': 48,
                                             'runtimeFieldOffsetFile': 83730392,
                                             'runtimeFieldOffsetRaw': '30000000',
                                             'primitiveIntegerDefault': None,
                                             'fieldRecordSource': 'global-metadata.dat',
                                             'runtimeFieldOffsetSource': 'global-metadata.dat',
                                             'typeRecordSource': 'GameAssembly.dll'},
                                'getter': {'va': '0x18c8dff70',
                                           'sha256': 'b45ba8be474bd22df93154901565c2fbd769019d3bd68421fb78f4a1e23a8212',
                                           'getDataCall': {'va': '0x18c8dff9f',
                                                           'bytes': 'e87c618710',
                                                           'mnemonic': 'call',
                                                           'operands': '0x19d156120',
                                                           'directTarget': '0x19d156120'},
                                           'fieldLoad': {'va': '0x18c8dffa9',
                                                         'bytes': '488b4030',
                                                         'mnemonic': 'mov',
                                                         'operands': 'rax, qword ptr [rax + 0x30]'}},
                                'getDataReturn': {'class': 'MENPOEFIHBO',
                                                  'method': {'methodIndex': 88036,
                                                             'name': 'LMBKNCAIDLC',
                                                             'declaringTypeIndex': 12929,
                                                             'parameterCount': 1,
                                                             'returnTypeIndex': 56436,
                                                             'metadataFileOffset': 64997564,
                                                             'metadataRaw': 'bc749f6d9991a675bdc27ddadc9d715cbdf2605f2e0d3f887dc3',
                                                             'pointerTableFileOffset': 77449024,
                                                             'nativePointerVA': 6930391328,
                                                             'nativeRVA': 487940384,
                                                             'nativeFileOffset': 477963040,
                                                             'nativeFirst64': '564883ec6089ce803d10846bec000f84fb000000488b0d4d4424ec80b9b7000000000f840c010000803d01e81fec007519488b0d304424ec80b9b7000000000f',
                                                             'nativeFirst64Sha256': '95befebf4a746d25a7cefed51f5c603da814396ad9d6a0528c9bbf4d5d2e166b',
                                                             'metadataSource': 'global-metadata.dat'},
                                                  'returnType': {'typeIndex': 56436,
                                                                 'offset': 84325152,
                                                                 'raw': '8032000000001200',
                                                                 'data': 12928,
                                                                 'code': 18,
                                                                 'class': 'RPG.GameCore.CakeConfigRow',
                                                                 'source': 'GameAssembly.dll'}},
                                'nativeRowPresenceSlot': 7,
                                'nativeRowPresenceInstruction': {'va': '0x19d5466a8',
                                                                 'bytes': 'f6c380',
                                                                 'mnemonic': 'test',
                                                                 'operands': 'bl, 0x80'},
                                'nativeRowDestinationInstruction': {'va': '0x19d5466c0',
                                                                    'bytes': '4883c730',
                                                                    'mnemonic': 'add',
                                                                    'operands': 'rdi, 0x30'}}}}

def normalized_cake_record(value):
 if isinstance(value,list):return [normalized_cake_record(item) for item in value]
 if isinstance(value,dict):
  result={}
  for key,item in value.items():result[key]=str(item) if key=='Hash' and type(item) is int else normalized_cake_record(item)
  return result
 return value

def direct_talk_references(obj,pointer='',typed=None,path=''):
 if isinstance(obj,dict):
  if isinstance(obj.get('$type'),str):typed={'type':obj['$type'],'pointer':pointer}
  if obj.get('$type')=='RPG.GameCore.PlayNPCSingleBubbleTalk':
   wrapper=obj.get('TalkSentenceID')
   if isinstance(wrapper,dict) and len(wrapper)==2 and wrapper.get('IsDynamic') is False and isinstance(wrapper.get('FixedValue'),dict) and list(wrapper['FixedValue'])==['Value']:
    value=wrapper['FixedValue']['Value']
    if type(value) is int and 0<value<2**32:yield value,pointer+'/TalkSentenceID/FixedValue/Value',typed
  if path=='ExcelOutput/CakeConfig.json' and pointer.startswith('/') and pointer[1:].isdigit() and type(obj.get('ID')) is int and 0<obj['ID']<2**32:
   for field in ('CatCaughtLines','CatMissedLines'):
    values=obj.get(field)
    if type(values) is list and not any(type(value) is not int or value<=0 or value>=4294967296 for value in values):
     for index,value in enumerate(values):yield value,pointer+'/'+field+'/'+str(index),typed
  for key,value in obj.items():
   p=pointer+'/'+key
   if key=='TalkSentenceID' and type(value) is int:yield value,p,typed
   if path=='ExcelOutput/HeartDialTalk.json' and key=='ID' and type(value) is int and ('VoiceID' not in obj or obj['VoiceID']==value) and isinstance(obj.get('SDFText'),dict):yield value,p,typed
   if path=='ExcelOutput/VisitorBehaviorConfig.json' and key=='NpcBubbleTalkSentenceID' and type(value) is int:yield value,p,typed
   task=typed['type'] if typed else ''
   if key in ('MobileSentenceID','PcSentenceID','PadSentenceID') and type(value) is int and task=='RPG.GameCore.PlayMusicRhythmTalk' and 'SimpleTalkList' in pointer.split('/') and obj.get('IsMultiPlatform') is True:yield value,p,typed
   if key=='SentenceID' and type(value) is int and task=='RPG.GameCore.PlayPenaconyEndmostSimpleTalk' and 'SimpleTalkList' in pointer.split('/'):yield value,p,typed
   if key=='LastToBeginTalkSentenceID' and type(value) is int and task=='RPG.GameCore.DebateInitialize' and 'TestimonySettingList' in pointer.split('/'):yield value,p,typed
   if (key=='TalkSentenceIDList' or key=='ControlTalkList' and path=='ExcelOutput/HeartDialDialogue.json') and isinstance(value,list):
    for i,v in enumerate(value):
     if type(v) is int:yield v,p+'/'+str(i),typed
   yield from direct_talk_references(value,p,typed,path)
 elif isinstance(obj,list):
  for i,value in enumerate(obj):yield from direct_talk_references(value,pointer+'/'+str(i),typed,path)

def verify(archive=None,dist=None,official_root=None,skill=None):
 payload=read(SITE/'data/dialogue-contexts.json');e=payload['evidence'];counts=payload['counts']
 require(payload['schema']=='starrail-dialogue-contexts.v1','schema')
 raw=(SITE/'data/dialogue-contexts.json').read_bytes();manifest=read(SITE/'editorial/dialogue-contexts-manifest.json')
 require((SITE/'public/dialogue-contexts.json').read_bytes()==raw,'public overlay differs')
 require(manifest['sha256']==sha(raw) and manifest['size']==len(raw),'overlay manifest')
 rows={};official={r['talk_id']:r for r in read(SITE/'data/official-talk-library.json')['rows']}
 for file,h in e['baselineFiles'].items():
  require(sha((SITE/file).read_bytes())==h,'preserved baseline altered '+file)
  d=read(SITE/file)
  for r in d['section']['rows']:require(r['talk_id'] not in rows,'duplicate preserved ID');rows[r['talk_id']]={**r,'url':'대사/'+d['id']+'.html#talk-'+str(r['talk_id'])}
 require(len(rows)==240078,'baseline corpus size changed')
 supp=read(SITE/'data/mission-dialogue-supplements.json')
 require(sha((SITE/'data/mission-dialogue-supplements.json').read_bytes())==e['supplementsSha256'],'mission source changed')
 require(sha((SITE/'data/official-talk-library.json').read_bytes())==e['officialTalkLibrarySha256'],'official corpus changed')
 assigned=set()
 for id,h in e['missionDocumentFiles'].items():
  file=SITE/'data/documents'/f'{id}.json';require(sha(file.read_bytes())==h,'preserved mission altered')
  for s in read(file)['sections']:assigned.update(r['talk_id'] for r in s['rows'] if r.get('talk_id'))
 for scenes in supp['missions'].values():
  for scene in scenes:assigned.update(r['talk_id'] for r in scene['rows'])
 baseline=set(rows)-assigned;delta={tid for tid,r in official.items() if not r['missionLinks']};target=baseline|delta
 categories={k:set(v) for k,v in payload['audit'].items()}
 require(all(len(v)==len(payload['audit'][k]) for k,v in categories.items()),'duplicate audit IDs')
 require(set().union(*categories.values())==target and sum(map(len,categories.values()))==len(target),'audit does not partition entire cohort')
 if 'deepAttributionSha256' in e:
  deep_path=SITE/'data/deep-dialogue-attribution.json';require(deep_path.is_file() and sha(deep_path.read_bytes())==e['deepAttributionSha256'],'deep attribution input changed')
  deep=read(deep_path);timeline_ids=verify_deep_reader_links(deep,rows,official)
  exact_timeline=(timeline_ids&target)-categories['EXACT_READABLE_SOURCE_REFERENCE']
  require(categories.get('EXACT_TIMELINE_READER_REFERENCE')==exact_timeline,'exact Timeline reader classification differs')
  require(counts['timelineReaderAttributedIds']==len(exact_timeline) and counts['timelineReaderLinks']==sum(len(deep['readerLinks'][str(tid)]) for tid in exact_timeline),'Timeline reader counts differ')
 actual=Counter();reader_ids=set();used_sources={};required=defaultdict(set);memberships=0
 groups=payload['groups'];require(len({g['id'] for g in groups})==len(groups),'duplicate context URL')
 for g in groups:
  require(g['id']=='context-'+sha(g['source'].encode())[:16],'unstable URL')
  require(len({r['talkId'] for r in g['rows']})==len(g['rows']),'duplicate source row')
  used_sources[g['source']]=g['sourceSha256'];required[g['source']].add('reader')
  for ref in g['rows']:
   tid=ref['talkId'];memberships+=1
   if tid in target:reader_ids.add(tid)
   require(tid in rows or tid in official,'row has no readable source')
   require(ref['edition']==('official' if tid in official else 'preserved'),'mixed snapshot identity')
   row=official[tid] if ref['edition']=='official' else rows[tid]
   require(row['text'].strip() and row['speaker'],'unreadable row')
   for r in ref['references']:require(r['kind']!='TalkSentence event reference','event promoted as spoken text');require(r['pointer'],'missing exact pointer')
   for label in row_targets(g,ref,payload):
    for edge in label['proof']:used_sources[edge['source']]=edge['sourceSha256'];required[edge['source']].add('row target label')
  require(set(g['auditedTalkIds'])=={r['talkId'] for r in g['rows'] if r['talkId'] in target},'source audit membership')
  for location in g['regions']:
   label=payload['regions'][str(location['floorId'])]
   require(label['floorId']==location['floorId'] and label['name'] and label['world'],'bad regional label')
   chain=location['chain'];require(chain and chain[-1]['target']==g['source'],'region chain target differs')
   require(chain[0]['source']==label['proof'][0]['source'],'region origin differs')
   require(all(a['target']==b['source'] for a,b in zip(chain,chain[1:])),'broken geographic chain')
   for edge in chain+label['proof']:
    used_sources[edge['source']]=edge['sourceSha256'];required[edge['source']].add('region')
    if 'tableSource'in edge:used_sources[edge['tableSource']]=edge['tableSha256'];required[edge['tableSource']].add('lookup')
 require(reader_ids==categories['EXACT_READABLE_SOURCE_REFERENCE'],'reader/audit mismatch')
 require(counts['readableAttributedIds']==len(reader_ids) and counts['sourceRowMemberships']==memberships and counts['sourceGroups']==len(groups),'counts')
 require(counts['baselineUnboundRows']==len(baseline) and counts['officialUnboundRows']==len(delta),'audited cohort counts')
 if archive:
  from build_official_universe_texts import official_input
  require(official_root and skill,'official Korean pack required for native display-text equality replay')
  texts,text_evidence,project=official_input(official_root,skill)
  require(text_evidence==e['regionKoreanSource'],'official Korean provenance differs')
  require(sha(archive.read_bytes())==e['archiveSha256'],'archive identity')
  objects={}
  with tarfile.open(archive,'r:gz') as tf:
   for member in tf:
    path=member.name.split('/',1)[-1]
    if path not in used_sources:continue
    body=tf.extractfile(member).read();require(sha(body)==used_sources[path],'structure changed '+path);objects[path]=json.loads(body)
  require(set(objects)==set(used_sources),'proof source absent')
  for g in groups:
   expected_refs=defaultdict(set)
   for tid,ptr,typed in direct_talk_references(objects[g['source']],path=g['source']):
    if g['source']=='ExcelOutput/HeartDialTalk.json':
     native=at(objects[g['source']],ptr.rsplit('/',1)[0]);text=texts.get(str(native['SDFText']['Hash']));row=official.get(tid) or rows.get(tid)
     if not text or not row or project(text['raw'])!=row['text']:continue
    if (typed or g['source'].startswith('ExcelOutput/')) and (tid in rows or tid in official):expected_refs[tid].add(ptr)
   require(set(expected_refs)=={r['talkId'] for r in g['rows']},'readable surrounding source row omitted')
   require(list(expected_refs)==[r['talkId'] for r in g['rows']],'structure reference row order changed')
   for row in g['rows']:
    require(expected_refs[row['talkId']]=={ref['pointer'] for ref in row['references']},'source reference occurrence omitted')
    for ref in row['references']:
     require(at(objects[g['source']],ref['pointer'])==row['talkId'],'exact Talk pointer changed')
     if ref['typedContainer']:require(at(objects[g['source']],ref['typedContainer']['pointer'])['$type']==ref['typedContainer']['type'],'typed container changed')
     configured=ref['kind']=='CAKE_CONFIG_TALK_SENTENCE_ID'
     fixed_bubble=ref['kind']=='FIXED_NPC_BUBBLE_TALK_SENTENCE_ID'
     choice=not fixed_bubble and ('OptionList' in ref['pointer'].split('/') or ref['typedContainer'] and ref['typedContainer']['type'].endswith('.OptionTalkInfo'))
     require(ref['displayKind']==('설정 참조' if configured else '선택지' if choice else '대사'),'native choice or dialogue role changed')
     if fixed_bubble:
      container=ref['typedContainer'];require(container and container['type']=='RPG.GameCore.PlayNPCSingleBubbleTalk','fixed bubble consumer type differs')
      require(ref['pointer']==container['pointer']+'/TalkSentenceID/FixedValue/Value','fixed bubble pointer differs')
      wrapper=at(objects[g['source']],container['pointer']+'/TalkSentenceID')
      require(isinstance(wrapper,dict) and set(wrapper)=={'IsDynamic','FixedValue'} and wrapper['IsDynamic'] is False and isinstance(wrapper['FixedValue'],dict) and set(wrapper['FixedValue'])=={'Value'} and type(wrapper['FixedValue']['Value']) is int and 0<wrapper['FixedValue']['Value']<2**32,'dynamic or nonliteral bubble wrapper accepted')
      require(ref.get('sourceRole')=='SPOKEN_BUBBLE_LITERAL','fixed bubble role differs')
      require(ref.get('recordContext') and ref['recordContext']['pointer']==container['pointer']+'/TalkSentenceID' and ref['recordContext']['fields']==wrapper,'original bubble wrapper changed')
      require(ref['recordContext'].get('serialized')==json.dumps(wrapper,ensure_ascii=False,indent=2),'original bubble wrapper serialization changed')
     if ref.get('kind') in ('NpcBubbleTalkSentenceID','ControlTalkList') or g['source']=='ExcelOutput/HeartDialTalk.json':
      require(ref.get('recordContext') and at(objects[g['source']],ref['recordContext']['pointer'])==ref['recordContext']['fields'],'native table row changed')
      require(ref['recordContext'].get('serialized')==json.dumps(ref['recordContext']['fields'],ensure_ascii=False,indent=2),'native uint64 proof serialization differs')
     if configured:
      require(g['source']=='ExcelOutput/CakeConfig.json' and g['sourceSha256']==CAKE_CONFIG_PROOF['tableSha256'],'Cake table/native snapshot differs')
      row_pointer,field,index=ref['pointer'].rsplit('/',2);native=at(objects[g['source']],row_pointer)
      require(field in ('CatCaughtLines','CatMissedLines') and type(native['ID']) is int and 0<native['ID']<2**32,'Cake row/field domain differs')
      require(isinstance(native[field],list) and all(type(value) is int and 0<value<2**32 for value in native[field]),'Cake array domain differs')
      require(ref.get('sourceRole')=='NON_SPOKEN_CONFIGURATION_REFERENCE','Cake source role differs')
      require(ref.get('recordContext')=={'pointer':row_pointer,'fields':normalized_cake_record(native),'serialized':json.dumps(native,ensure_ascii=False,indent=2)},'Cake original whole row/hash digits differ')
      require(ref.get('configurationReference')=={'tableRowId':native['ID'],'field':field,'index':int(index),'proof':{key:value for key,value in CAKE_CONFIG_PROOF.items() if key!='bridges'},'fieldBridge':CAKE_CONFIG_PROOF['bridges'][field]},'Cake exact native accessor bridge differs')
     expected_usage={'MobileSentenceID' :'모바일 안내','PcSentenceID':'PC 안내','PadSentenceID':'패드 안내','LastToBeginTalkSentenceID':'토론 설정 참조'}.get(ref['kind'],'')
     if fixed_bubble:expected_usage='말풍선'
     if configured:expected_usage='콘텐츠 설정의 대사 참조'
     if g['source']=='ExcelOutput/HeartDialTalk.json':expected_usage='감정 조율의 표시 문구'
     if ref['kind']=='TalkSentenceID' and isinstance(at(objects[g['source']],ref['pointer'].rsplit('/',1)[0]),dict) and at(objects[g['source']],ref['pointer'].rsplit('/',1)[0]).get('IsMultiPlatform') is True:expected_usage='기본 안내'
     require(ref.get('usageLabel','')==expected_usage,'native platform or setting role differs')
    for label in row_targets(g,row,payload):
     for edge in label['proof']:require(str(at(objects[edge['source']],edge['pointer']))==str(edge['value']),'row target regional identity changed')
     floor_edge=next(edge for edge in label['proof'] if '/FloorIDList/' in edge['pointer'])
     require(floor_edge['value']==label['floorId'],'row target Floor ID mapping differs')
     plane_pointer=floor_edge['pointer'].rsplit('/FloorIDList/',1)[0]
     plane=at(objects[floor_edge['source']],plane_pointer)
     world_edge=next(edge for edge in label['proof'] if edge['pointer'].endswith('/WorldName/Hash'))
     world=at(objects[world_edge['source']],world_edge['pointer'].rsplit('/WorldName/Hash',1)[0])
     require(plane['WorldID']==world['ID'],'row target world domain differs')
   for location in g['regions']:
    label=payload['regions'][str(location['floorId'])]
    for edge in label['proof']:require(str(at(objects[edge['source']],edge['pointer']))==str(edge['value']),'regional identity changed')
    for edge in location['chain']:
     if 'tableSource'in edge:
      if edge['tableSource'] in ('ExcelOutput/DialogueNPC.json','ExcelOutput/DialogueProp.json'):
       domain='NPCList' if edge['tableSource']=='ExcelOutput/DialogueNPC.json' else 'PropList'
       require(edge.get('domain')==domain and domain in edge['pointer'].split('/'),'dialogue group entity domain differs')
       require(edge['idPointer'].endswith('/GroupID') and edge['pathPointer'].endswith('/ActPath'),'dialogue group lookup fields differ')
       gid=at(objects[edge['source']],edge['pointer'])
       require({r['ActPath'] for r in objects[edge['tableSource']] if r.get('GroupID')==gid and isinstance(r.get('ActPath'),str)}=={edge['target']},'dialogue group lookup target ambiguous')
      require(at(objects[edge['source']],edge['pointer'])==at(objects[edge['tableSource']],edge['idPointer']),'performance ID changed')
      require(at(objects[edge['tableSource']],edge['pathPointer'])==edge['target'],'performance path changed')
     else:require(at(objects[edge['source']],edge['pointer'])==edge['target'],'geographic path changed')
  if official_root:
   for label in payload['regions'].values():
    plane_hash=next(edge['value'] for edge in label['proof'] if edge['pointer'].endswith('/PlaneName/Hash'))
    world_hash=next(edge['value'] for edge in label['proof'] if edge['pointer'].endswith('/WorldName/Hash'))
    expected_name=project(texts[str(plane_hash)]['raw']) if str(plane_hash) in texts else '지역 이름 미확인'
    expected_world=project(texts[str(world_hash)]['raw']) if str(world_hash) in texts else '세계 이름 미확인'
    require(label['name']==(expected_name or '지역 이름 미확인') and label['world']==(expected_world or '세계 이름 미확인'),'regional Korean label differs')
 if dist:
  publication_expand=None
  if (dist/'_shared').is_dir():
   from optimize_publication import expansion_function
   publication_expand=expansion_function(read(SITE/'.codex-work/publication-build-report.json'))
  for g in groups:
   file=dist/'대화'/f"{g['id']}.html";require(file.exists(),'reader missing')
   page=ContextPage();page.feed(file.read_text('utf8'));require(not page.duplicates,'duplicate HTML anchors')
   require('verified-sources'in page.ids,'missing proof disclosure')
   require([r['talkId'] for r in page.context_rows]==[r['talkId'] for r in g['rows']],'rendered source row order or count differs')
   expected_native=[{'talkId':row['talkId'],'pointer':ref['recordContext']['pointer'],'text':ref['recordContext']['serialized']} for row in g['rows'] for ref in row['references'] if ref.get('recordContext',{}).get('serialized')]
   native_records=page.native_records
   if publication_expand and expected_native:
    restored=ContextPage();restored.feed(publication_expand(file.read_text('utf8')))
    native_records=restored.native_records
   require(native_records==expected_native,'rendered native table proof sequence, uint64 or exact text differs')
   for ref,rendered in zip(g['rows'],page.context_rows):
    tid=ref['talkId'];row=official[tid] if ref['edition']=='official' else rows[tid]
    roles={r['displayKind'] for r in ref['references']};choice='선택지' in roles
    a=rendered['attributes'];role='choice' if choice else 'dialogue'
    require(a.get('data-speaker')==row['speaker'],'rendered source speaker differs')
    require(a.get('data-reading-kind')==role and a.get('data-passage')==role,'rendered source reading role differs')
    configured='설정 참조' in roles
    label=('설정 참조' if row['speaker']=='화자 미지정' else '설정 참조 · '+row['speaker']) if configured else '원문에 수록된 제작 안내' if tid==999999999 and row['text']=='스토리 및 연출 콘텐츠는 제작 중입니다, 기대해주세요!' else '선택지·대사 · '+row['speaker'] if choice and '대사' in roles else '선택지' if choice else '원문' if row['speaker']=='화자 미지정' else row['speaker']
    require(rendered['label']==label,'rendered source speaker/choice display label differs '+g['id']+'/'+str(tid))
    usages=list(dict.fromkeys(r.get('usageLabel','') for r in ref['references'] if r.get('usageLabel')))
    require(rendered.get('usage','')==' · '.join(usages),'rendered platform or setting role differs')
    targets=row_targets(g,ref,payload)
    require(rendered.get('targets','')==','.join(str(r['floorId']) for r in targets),'rendered native row target Floor IDs differ')
    expected_target='설정표의 대상 지역: '+' / '.join(r['world']+' · '+r['name'] for r in targets) if targets else ''
    require(rendered.get('targetLabel','')==expected_target,'rendered native row target region label differs')
    require(page.original.get('talk-'+str(tid))==row['text'],'original HTML text differs '+g['id']+'/'+str(tid))
    url='대사/official-4.6-'+str(tid)+'.html#talk-'+str(tid) if ref['edition']=='official' else row['url']
    require('/starrail-quests/'+url in page.links,'original return link absent')
   require('data-dialogue-context="'+g['id']+'"' in file.read_text('utf8'),'reader ID absent')
  for kind_id,kind in enumerate(dict.fromkeys(g['kind'] for g in groups)):
   members=[g for g in groups if g['kind']==kind]
   for part,start in enumerate(range(0,len(members),120)):
    file=dist/'대화'/f"목록-{kind_id}{'-'+str(part) if part else ''}.html"
    require(file.is_file(),'source directory missing')
    page=ContextPage();page.feed(file.read_text('utf8'))
    expected=members[start:start+120]
    require(not page.duplicates,'duplicate directory anchors')
    require([r['data-source-record'] for r in page.directory_records]==[g['id'] for g in expected],'directory source sequence differs')
    for index,(g,record) in enumerate(zip(expected,page.directory_records)):
     worlds=list(dict.fromkeys(payload['regions'][str(r['floorId'])]['world'] for r in g['regions']))
     label=' · '.join(worlds) or '지역 연결 확인 중'
     require(record.get('data-source-kind-value')==label,'directory world labels differ or duplicate')
     require(record.get('href')=='/starrail-quests/대화/'+g['id']+'.html','directory source URL differs')
     require(record.get('id')=='universe-source-'+g['id'] and 'data-reading-link' in record,'directory return anchor differs')
     require(('hidden' in record)==(index>=12),'directory initial display limit differs')
 print(json.dumps({'status':'PASS','archiveReplay':bool(archive),'html':bool(dist),**counts},ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);p.add_argument('--dist',type=Path);p.add_argument('--official-root',type=Path);p.add_argument('--skill',type=Path);a=p.parse_args();verify(a.archive,a.dist,a.official_root,a.skill)
