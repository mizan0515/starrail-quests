"""Attribute every preserved unbound Talk ID through exact structure references.

Scene use, geographic placement and mission ownership are distinct facts.
Preserved Korean rows are never rewritten; the overlay contains ID references.
"""
import sys
sys.dont_write_bytecode = True
import argparse, hashlib, json, re, tarfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from build_mission_dialogue_supplements import refs, path_refs, objects, performance_matches
from build_official_talk_library import reference_context
from build_official_universe_texts import official_input
from multivoice_configuration_refs import PROOF as MULTIVOICE_PROOF, SOURCE as MULTIVOICE_SOURCE, KIND as MULTIVOICE_KIND, references as multivoice_refs, source_record as multivoice_record
from music_rhythm_text_refs import KIND as MUSIC_KIND, SOURCES as MUSIC_SOURCES, references as music_refs, source_record as music_record, public_proof as music_proof

SITE = Path(__file__).resolve().parents[1]
SCHEMA = 'starrail-dialogue-contexts.v1'
def read(p): return json.loads(p.read_text('utf8'))
def sha(b): return hashlib.sha256(b).hexdigest()
def write(p, value): p.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), 'utf8')

KINDS = {'Mission':'임무에 함께 수록된 대화', 'MunicipalChatConfig':'거리의 대화', 'NPCDialogue':'인물과의 대화',
 'NPC':'인물 주변의 대화', 'PropDialogue':'사물 조사와 상호작용', 'GroupGraph':'현장의 대화와 상호작용',
 'RogueDialogue':'시뮬레이션 우주의 사건', 'Rogue':'시뮬레이션 우주의 사건', 'SubLevelGraph':'전투와 연출',
 'LINews':'소식과 방송', 'CrowdBubble':'거리의 목소리', 'TarotBook':'기록과 상호작용',
 'LevelInstanceGraph':'현장의 대화와 상호작용', 'GameplayMission':'콘텐츠의 대화', 'Maze':'콘텐츠의 대화',
 'LittleGame':'미니게임의 대화', 'AetherDivide':'에테르 배틀', 'EventMission':'현장의 사건',
 'Props':'사물 주변의 대화', 'SummonUnitGraph':'동행하는 존재의 대화', 'Raid':'도전과 전투',
 'GroupTemplateGraph':'현장의 대화와 상호작용', 'Tutorial':'진행 안내', 'Track':'현장의 대화와 상호작용'}
def kind(path):
 if path in ('ExcelOutput/CakeConfig.json',MULTIVOICE_SOURCE):return '콘텐츠 설정의 대사 참조'
 if path=='ExcelOutput/VisitorBehaviorConfig.json':return '방문객의 말풍선'
 if path=='ExcelOutput/HeartDialDialogue.json':return '마음의 시계 대화'
 if path=='ExcelOutput/HeartDialTalk.json':return '감정 조율의 표시 문구'
 if path.startswith('Config/Level/'): return KINDS.get(path.split('/')[2], '콘텐츠의 대화')
 if path.startswith('Story/'): return '연출과 선택지'
 if path.startswith('ExcelOutput/'): return '콘텐츠 기록의 대화'
 if path.startswith('Config/ConfigAbility/'): return '전투와 능력의 대화'
 if path.startswith('Config/ConfigAnimEvents/'): return '동행하는 존재의 대화'
 return '콘텐츠의 대화'
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

def cake_config_refs(obj,path,pointer):
 # Only top-level table rows and complete positive UInt32 arrays are admitted.
 if path!='ExcelOutput/CakeConfig.json' or not re.fullmatch(r'/\d+',pointer):return
 if type(obj.get('ID')) is not int or not 0<obj['ID']<2**32:return
 for field in ('CatCaughtLines','CatMissedLines'):
  values=obj.get(field)
  if isinstance(values,list) and all(type(v) is int and 0<v<2**32 for v in values):
   for index,value in enumerate(values):yield value,pointer+'/'+field+'/'+str(index),'CAKE_CONFIG_TALK_SENTENCE_ID'

def cake_record_fields(value):
 if isinstance(value,dict):return {key:str(item) if key=='Hash' and type(item) is int else cake_record_fields(item) for key,item in value.items()}
 if isinstance(value,list):return [cake_record_fields(item) for item in value]
 return value

def playable_reference(path):
 return path.startswith(('Config/', 'Story/')) or path in ('ExcelOutput/InclinationText.json', 'ExcelOutput/ChimeraDuelMaster.json', 'ExcelOutput/MazePuzzleOrigamiColony.json','ExcelOutput/VisitorBehaviorConfig.json','ExcelOutput/HeartDialDialogue.json','ExcelOutput/HeartDialTalk.json','ExcelOutput/CakeConfig.json',MULTIVOICE_SOURCE)
def fixed_npc_bubble_talk(obj):
 """Accept a literal fixed TalkSentence value only in its actual consumer task."""
 if not isinstance(obj,dict) or obj.get('$type')!='RPG.GameCore.PlayNPCSingleBubbleTalk':return None
 wrapper=obj.get('TalkSentenceID')
 if not isinstance(wrapper,dict) or set(wrapper)!={'IsDynamic','FixedValue'} or wrapper['IsDynamic'] is not False:return None
 fixed=wrapper['FixedValue']
 if not isinstance(fixed,dict) or set(fixed)!={'Value'}:return None
 value=fixed['Value']
 return value if type(value) is int and 0<value<2**32 else None
def content_refs(obj,path,pointer='',typed=''):
 if isinstance(obj,dict):
  typed=obj.get('$type',typed)
  yield from cake_config_refs(obj,path,pointer)
  yield from multivoice_refs(obj,path,pointer)
  yield from music_refs(obj,path,pointer)
  literal=fixed_npc_bubble_talk(obj)
  if literal is not None:yield literal,pointer+'/TalkSentenceID/FixedValue/Value','FIXED_NPC_BUBBLE_TALK_SENTENCE_ID'
  for key,value in obj.items():
   p=pointer+'/'+key
   direct=(key=='TalkSentenceID' and path!=MULTIVOICE_SOURCE) or (key=='NpcBubbleTalkSentenceID' and path=='ExcelOutput/VisitorBehaviorConfig.json')
   if path=='ExcelOutput/HeartDialTalk.json' and key=='ID' and type(value) is int and ('VoiceID' not in obj or obj['VoiceID']==value) and isinstance(obj.get('SDFText'),dict):direct=True
   device=key in ('MobileSentenceID','PcSentenceID','PadSentenceID') and typed=='RPG.GameCore.PlayMusicRhythmTalk' and 'SimpleTalkList' in pointer.split('/') and obj.get('IsMultiPlatform') is True
   sentence=key=='SentenceID' and typed=='RPG.GameCore.PlayPenaconyEndmostSimpleTalk' and 'SimpleTalkList' in pointer.split('/')
   setting=key=='LastToBeginTalkSentenceID' and typed=='RPG.GameCore.DebateInitialize' and 'TestimonySettingList' in pointer.split('/')
   if (direct or device or sentence or setting) and type(value) is int:yield value,p,key
   elif (key=='TalkSentenceIDList' or key=='ControlTalkList' and path=='ExcelOutput/HeartDialDialogue.json') and isinstance(value,list):
    for i,v in enumerate(value):
     if type(v) is int:yield v,p+'/'+str(i),key
   elif isinstance(value,str) and re.fullmatch(r'TalkSentence_\d+',value):yield int(value.split('_')[1]),p,'TalkSentence event reference'
   yield from content_refs(value,path,p,typed)
 elif isinstance(obj,list):
  for i,v in enumerate(obj):yield from content_refs(v,path,pointer+'/'+str(i),typed)
def internal(path): return any(part.startswith('Test') or part=='MissionBeta' for part in path.split('/'))

def corpus():
 rows = {}; hashes = {}
 for p in sorted((SITE/'data/dialogues').glob('*.json')):
  hashes[p.relative_to(SITE).as_posix()] = sha(p.read_bytes())
  for r in read(p)['section']['rows']:
   assert r['talk_id'] not in rows
   rows[r['talk_id']] = {**r, 'url':'대사/'+p.stem+'.html#talk-'+str(r['talk_id'])}
 return rows, hashes

def load(archive):
 metadata={}; hashes={}; performance=defaultdict(list); scanned=0
 with tarfile.open(archive,'r:gz') as tf:
  for m in tf:
   n=m.name.split('/',1)[-1]
   if not m.isfile() or not n.endswith('.json') or n.startswith('TextMap'): continue
   raw=tf.extractfile(m).read();o=json.loads(raw);scanned+=1
   relevant=n.startswith(('Config/','Story/')) or n.startswith('ExcelOutput/Performance') or n in ('ExcelOutput/MazePlane.json','ExcelOutput/WorldDataConfig.json','ExcelOutput/MazeFloor.json','ExcelOutput/DialogueNPC.json','ExcelOutput/DialogueProp.json') or playable_reference(n)
   if not relevant: continue
   metadata[n]=o;hashes[n]=sha(raw)
   if re.fullmatch(r'ExcelOutput/Performance(?:A|C|D|E|DS|CG|CLD|DLD|DSLD|Video|VideoLD)\.json',n):
    for i,r in enumerate(o):
     if type(r.get('PerformanceID')) is int and isinstance(r.get('PerformancePath'),str):performance[r['PerformanceID']].append({'target':r['PerformancePath'],'source':n,'idPointer':f'/{i}/PerformanceID','pathPointer':f'/{i}/PerformancePath'})
 return metadata,hashes,performance,scanned

def geography(metadata, hashes, performance, texts, project):
 """An explicit RuntimeFloor FloorID and paths establish geographic use only."""
 planes=metadata['ExcelOutput/MazePlane.json'];worlds={r['ID']:(i,r) for i,r in enumerate(metadata['ExcelOutput/WorldDataConfig.json'])}
 dialogue_tables={domain:defaultdict(list) for domain in ('NPCList','PropList')}
 for domain,table in (('NPCList','ExcelOutput/DialogueNPC.json'),('PropList','ExcelOutput/DialogueProp.json')):
  for i,row in enumerate(metadata[table]):
   if type(row.get('GroupID')) is int and isinstance(row.get('ActPath'),str):dialogue_tables[domain][row['GroupID']].append({'source':table,'idPointer':f'/{i}/GroupID','pathPointer':f'/{i}/ActPath','target':row['ActPath']})
 labels={};reachable=defaultdict(dict)
 for path,obj in metadata.items():
  if not path.startswith('Config/LevelOutput/RuntimeFloor/') or type(obj.get('FloorID')) is not int:continue
  fid=obj['FloorID'];matches=[(i,r) for i,r in enumerate(planes) if fid in r.get('FloorIDList',[])]
  if len(matches)!=1:continue
  pi,plane=matches[0];wi,world=worlds[plane['WorldID']]
  def text(v):return project(texts[str(v['Hash'])]['raw']) if isinstance(v,dict) and str(v.get('Hash')) in texts else ''
  name=text(plane.get('PlaneName'));world_name=text(world.get('WorldName'))
  labels[fid]={'name':name or '지역 이름 미확인','world':world_name or '세계 이름 미확인','floorId':fid,
   'proof':[{'source':path,'pointer':'/FloorID','value':fid},{'source':'ExcelOutput/MazePlane.json','pointer':f'/{pi}/FloorIDList/{plane["FloorIDList"].index(fid)}','value':fid},
    {'source':'ExcelOutput/MazePlane.json','pointer':f'/{pi}/WorldID','value':plane['WorldID']}, {'source':'ExcelOutput/MazePlane.json','pointer':f'/{pi}/PlaneName/Hash','value':str(plane.get('PlaneName',{}).get('Hash',0))},
    {'source':'ExcelOutput/WorldDataConfig.json','pointer':f'/{wi}/WorldName/Hash','value':str(world.get('WorldName',{}).get('Hash',0))}]}
  queue=deque([(path,[])])
  while queue:
   source,chain=queue.popleft()
   if source in reachable[fid] or source not in metadata:continue
   reachable[fid][source]=chain
   obj=metadata[source]
   for target,ptr in path_refs(obj):
    if target in metadata and target not in reachable[fid]:queue.append((target,chain+[{'source':source,'pointer':ptr,'target':target}]))
   for task,ptr in objects(obj):
    domains=[domain for domain in dialogue_tables if domain in ptr.split('/')]
    if len(domains)==1:
     for field in ('DialogueGroups','TalkDialogGroupIDList','FirstDialogueGroupID'):
      value=task.get(field);ids=[(v,ptr+'/'+field+'/'+str(i)) for i,v in enumerate(value)] if isinstance(value,list) else [(value,ptr+'/'+field)]
      for gid,idptr in ids:
       matches=dialogue_tables[domains[0]].get(gid,[]) if type(gid) is int else []
       if len({r['target'] for r in matches})==1:
        r=matches[0]
        if r['target'] in metadata:queue.append((r['target'],chain+[{'source':source,'pointer':idptr,'target':r['target'],'tableSource':r['source'],'idPointer':r['idPointer'],'pathPointer':r['pathPointer'],'domain':domains[0]}]))
    if task.get('$type','').endswith('.TriggerPerformance') and type(task.get('PerformanceID')) is int:
     matches,scope=performance_matches(performance,task['PerformanceID'],task.get('PerformanceType',''))
     if len({r['target'] for r in matches})==1:
      r=matches[0]
      if r['target'] in metadata:queue.append((r['target'],chain+[{'source':source,'pointer':ptr+'/PerformanceID','target':r['target'],'tableSource':r['source'],'idPointer':r['idPointer'],'pathPointer':r['pathPointer']}]))
 for label in labels.values():
  for edge in label['proof']:edge['sourceSha256']=hashes[edge['source']]
 reverse=defaultdict(list)
 for fid,paths in reachable.items():
  for path,chain in paths.items():reverse[path].append({'floorId':fid,'chain':[{**e,'sourceSha256':hashes[e['source']],**({'tableSha256':hashes[e['tableSource']]} if 'tableSource'in e else {})} for e in chain]})
 return labels,reverse

def build(archive, official_root, skill):
 previous_context=read(SITE/'public/dialogue-contexts.json')
 previous_order={g['id']:i for i,g in enumerate(previous_context['groups'])}
 local,local_hashes=corpus();official=read(SITE/'data/official-talk-library.json');supp=read(SITE/'data/mission-dialogue-supplements.json')
 assigned=set();strict=set();documents={}
 for p in sorted((SITE/'data/documents').glob('quest-*.json')):
  d=read(p);documents[d['id']]=sha(p.read_bytes());coverage=supp['coverage'][d['id']]
  for s in d['sections']:
   ids={r['talk_id'] for r in s['rows'] if r.get('talk_id')};assigned.update(ids)
   chain=coverage.get('sourceOwnership',{}).get(s.get('source'),[])
   if chain and chain[0]['kind']=='EXPLICIT_MAIN_MISSION_ID':strict.update(ids)
 for scenes in supp['missions'].values():
  for s in scenes:
   ids={r['talk_id'] for r in s['rows']};assigned.update(ids)
   if s['ownership'][0]['kind']=='EXPLICIT_MAIN_MISSION_ID':strict.update(ids)
 baseline=set(local)-assigned;current={r['talk_id']:r for r in official['rows']};delta={tid:r for tid,r in current.items() if not r['missionLinks']};target=baseline|set(delta)
 metadata,hashes,performance,scanned=load(archive)
 assert hashes.get('ExcelOutput/CakeConfig.json')==CAKE_CONFIG_PROOF['tableSha256'],'Cake configuration snapshot differs from native proof'
 assert hashes.get(MULTIVOICE_SOURCE)==MULTIVOICE_PROOF['tableSha256'],'Alternative-voice configuration differs from native proof'
 texts,text_evidence,project=official_input(official_root,skill)
 labels,regions=geography(metadata,hashes,performance,texts,project)
 groups=[];classification=defaultdict(set);ref_types=Counter();all_sources={}
 for path,obj in sorted(metadata.items()):
  if not playable_reference(path):continue
  found=defaultdict(list);unavailable=set()
  for tid,ptr,k in content_refs(obj,path):
   if path=='ExcelOutput/HeartDialTalk.json':
    native=obj[int(ptr.split('/')[1])];source=texts.get(str(native['SDFText']['Hash']));row=current.get(tid) or local.get(tid)
    if not source or not row or project(source['raw'])!=row['text']:continue
   if tid in target:ref_types[k]+=1
   if k=='TalkSentence event reference':
    if tid in target:classification['EVENT_ONLY'].add(tid)
    continue
   context=reference_context(obj,ptr,k)
   if not context['typedContainer'] and not path.startswith('ExcelOutput/') and k!=MUSIC_KIND:continue
   if tid not in local and tid not in current:unavailable.add(tid);continue
   ancestors=ptr.split('/')
   choice=k!='FIXED_NPC_BUBBLE_TALK_SENTENCE_ID' and ('OptionList' in ancestors or context['typedContainer'] and context['typedContainer']['type'].endswith('.OptionTalkInfo'))
   record={}
   if k=='FIXED_NPC_BUBBLE_TALK_SENTENCE_ID':
    wrapper_pointer=ptr.rsplit('/FixedValue/Value',1)[0];wrapper=obj
    for part in wrapper_pointer.strip('/').split('/'):wrapper=wrapper[int(part)] if isinstance(wrapper,list) else wrapper[part]
    record={'sourceRole':'SPOKEN_BUBBLE_LITERAL','recordContext':{'pointer':wrapper_pointer,'fields':wrapper,'serialized':json.dumps(wrapper,ensure_ascii=False,indent=2)}}
   if k in ('NpcBubbleTalkSentenceID','ControlTalkList') or path=='ExcelOutput/HeartDialTalk.json':
    parent_pointer=ptr.rsplit('/',2)[0] if k=='ControlTalkList' else ptr.rsplit('/',1)[0];native=obj[int(parent_pointer.strip('/'))]
    record={'recordContext':{'pointer':parent_pointer,'fields':native,'serialized':json.dumps(native,ensure_ascii=False,indent=2)}}
   if k=='CAKE_CONFIG_TALK_SENTENCE_ID':
    row_pointer,field,index=ptr.rsplit('/',2);native=obj[int(row_pointer.strip('/'))]
    record={'sourceRole':'NON_SPOKEN_CONFIGURATION_REFERENCE','recordContext':{'pointer':row_pointer,'fields':cake_record_fields(native),'serialized':json.dumps(native,ensure_ascii=False,indent=2)},'configurationReference':{'tableRowId':native['ID'],'field':field,'index':int(index),'proof':{key:value for key,value in CAKE_CONFIG_PROOF.items() if key!='bridges'},'fieldBridge':CAKE_CONFIG_PROOF['bridges'][field]}}
   if k==MULTIVOICE_KIND:
    row_pointer=ptr.rsplit('/',1)[0];native=obj[int(row_pointer.strip('/'))]
    record=multivoice_record(native,row_pointer)
   if k==MUSIC_KIND:record=music_record(obj,ptr)
   usage={'MobileSentenceID' :'모바일 안내','PcSentenceID':'PC 안내','PadSentenceID':'패드 안내','LastToBeginTalkSentenceID':'토론 설정 참조'}.get(k,'')
   if k=='FIXED_NPC_BUBBLE_TALK_SENTENCE_ID':usage='말풍선'
   if k=='CAKE_CONFIG_TALK_SENTENCE_ID':usage='콘텐츠 설정의 대사 참조'
   if k==MULTIVOICE_KIND:usage='대사의 대체 음성 설정'
   if k==MUSIC_KIND:usage=record.pop('usageLabel')
   if path=='ExcelOutput/HeartDialTalk.json':usage='감정 조율의 표시 문구'
   if k=='TalkSentenceID':
    parent=obj
    for part in ptr.strip('/').split('/')[:-1]:parent=parent[int(part)] if isinstance(parent,list) else parent[part]
    if isinstance(parent,dict) and parent.get('IsMultiPlatform') is True:usage='기본 안내'
   found[tid].append({'pointer':ptr,'kind':k,'displayKind':'화면 문구' if k==MUSIC_KIND else '설정 참조' if k in ('CAKE_CONFIG_TALK_SENTENCE_ID',MULTIVOICE_KIND) else '선택지' if choice else '대사','usageLabel':usage,**context,**record})
  audited=set(found)&target
  if not audited:continue
  internal_source=internal(path)
  for tid in audited:classification['INTERNAL_REFERENCE' if internal_source else 'EXACT_READABLE_SOURCE_REFERENCE'].add(tid)
  if internal_source:continue
  source_id='context-'+sha(path.encode())[:16]
  people=list(dict.fromkeys((current.get(tid) or local[tid])['speaker'] for tid in found))
  people=[s for s in people if s!='화자 미지정']
  first=(current.get(next(iter(found))) or local[next(iter(found))])['text'].replace('\n',' ')
  title=' · '.join(people[:2]) if people else first[:36]+('…' if len(first)>36 else '')
  if path=='ExcelOutput/VisitorBehaviorConfig.json':title='열차 방문객의 말풍선'
  if path=='ExcelOutput/HeartDialDialogue.json':title='마음의 시계에 연결된 대화'
  if path=='ExcelOutput/HeartDialTalk.json':title='감정 조율에 표시되는 문구'
  if path=='ExcelOutput/CakeConfig.json':title='케이크 설정에 연결된 대사'
  if path==MULTIVOICE_SOURCE:title='대체 음성 설정에 연결된 대사'
  if path in MUSIC_SOURCES:title='리듬 게임의 화면 문구 · '+first[:28]+('…'if len(first)>28 else '')
  if not title:title=kind(path)
  group={'id':source_id,'title':title,'kind':kind(path),'source':path,'sourceSha256':hashes[path],
   'rows':[{'talkId':tid,'edition':'official' if tid in current else 'preserved','references':records} for tid,records in found.items()],
   'auditedTalkIds':sorted(audited),'unavailableTalkIds':sorted(unavailable),'regions':regions.get(path,[])}
  if path==MULTIVOICE_SOURCE:group['configurationProof']=MULTIVOICE_PROOF
  if path in MUSIC_SOURCES:
   assert hashes[path]==MUSIC_SOURCES[path],'Music configuration snapshot differs from native consumer profile'
   group['screenReferenceProof']=music_proof()
  groups.append(group);all_sources[path]=hashes[path]
 groups.sort(key=lambda g:(0,previous_order[g['id']])if g['id']in previous_order else(1,g['source']))
 classification['EVENT_ONLY']-=classification['EXACT_READABLE_SOURCE_REFERENCE']|classification['INTERNAL_REFERENCE']
 classification['INTERNAL_REFERENCE']-=classification['EXACT_READABLE_SOURCE_REFERENCE']
 deep_path=SITE/'data/deep-dialogue-attribution.json';deep=None
 if deep_path.exists():
  deep_raw=deep_path.read_bytes();deep=json.loads(deep_raw);assert deep['schema']=='starrail-deep-dialogue-attribution.v1'
  timeline_ids=deep['timelineReaderIds'];assert all(type(tid) is int and 0<tid<2**32 for tid in timeline_ids) and len(set(timeline_ids))==len(timeline_ids)
  assert all(str(tid) in deep['readerLinks'] and deep['readerLinks'][str(tid)] for tid in timeline_ids)
  classification['EXACT_TIMELINE_READER_REFERENCE']=(set(timeline_ids)&target)-classification['EXACT_READABLE_SOURCE_REFERENCE']
  classification['EVENT_ONLY']-=classification['EXACT_TIMELINE_READER_REFERENCE']
  classification['INTERNAL_REFERENCE']-=classification['EXACT_TIMELINE_READER_REFERENCE']
 classification['NO_EXACT_USAGE_REFERENCE']=target-set().union(*classification.values())
 assert set().union(*classification.values())==target
 assert sum(len(v) for v in classification.values())==len(target)
 counts={'preservedKoreanRows':len(local),'previousMissionBodyRows':len(set(local)&assigned),'explicitMissionOwnerRows':len(set(local)&strict),
  'baselineUnboundRows':len(baseline),'officialUnboundRows':len(delta),'distinctAuditIds':len(target),'scannedJsonFiles':scanned,
  'sourceGroups':len(groups),'sourceRowMemberships':sum(len(g['rows']) for g in groups),'auditedSourceRowMemberships':sum(len(g['auditedTalkIds']) for g in groups),'readerDistinctTalkIds':len({r['talkId'] for g in groups for r in g['rows']}),'readableAttributedIds':len(classification['EXACT_READABLE_SOURCE_REFERENCE']),
  'geographicSourceGroups':sum(bool(g['regions']) for g in groups),'geographicTalkIds':len({tid for g in groups if g['regions'] for tid in g['auditedTalkIds']}),
  'classification':{k:len(v) for k,v in sorted(classification.items())},'baselineClassification':{k:len(v&baseline) for k,v in sorted(classification.items())},
  'officialClassification':{k:len(v&set(delta)) for k,v in sorted(classification.items())}}
 if deep is not None:
  counts['timelineReaderAttributedIds']=len(classification['EXACT_TIMELINE_READER_REFERENCE'])
  counts['timelineReaderLinks']=sum(len(deep['readerLinks'][str(tid)]) for tid in classification['EXACT_TIMELINE_READER_REFERENCE'])
 result={'schema':SCHEMA,'evidence':{'archiveSha256':sha(archive.read_bytes()),'commit':supp['evidence']['commit'],'repository':supp['evidence']['repository'],
  'baselineFiles':local_hashes,'missionDocumentFiles':documents,'supplementsSha256':sha((SITE/'data/mission-dialogue-supplements.json').read_bytes()),
  'officialTalkLibrarySha256':sha((SITE/'data/official-talk-library.json').read_bytes()),'regionKoreanSource':text_evidence},
  'counts':counts,'audit':{k:sorted(v) for k,v in sorted(classification.items())},'regions':{str(k):v for k,v in labels.items()},'groups':groups}
 if deep is not None:
  assert deep_path.read_bytes()==deep_raw,'deep attribution changed during source regeneration'
  result['evidence']['deepAttributionSha256']=sha(deep_raw)
 body=json.dumps(result,ensure_ascii=False,separators=(',',':')).encode()
 (SITE/'data/dialogue-contexts.json').write_bytes(body);(SITE/'public/dialogue-contexts.json').write_bytes(body)
 write(SITE/'editorial/dialogue-contexts-manifest.json',{'schema':SCHEMA,'path':'public/dialogue-contexts.json','target':'data/dialogue-contexts.json','size':len(body),'sha256':sha(body)})
 assert corpus()[1]==local_hashes
 print(json.dumps(counts,ensure_ascii=False),flush=True)
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--official-root',type=Path,required=True);p.add_argument('--skill',type=Path,required=True);a=p.parse_args();build(a.archive,a.official_root,a.skill)
