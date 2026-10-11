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

def direct_talk_references(obj,pointer='',typed=None,path=''):
 if isinstance(obj,dict):
  if isinstance(obj.get('$type'),str):typed={'type':obj['$type'],'pointer':pointer}
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
     choice='OptionList' in ref['pointer'].split('/') or ref['typedContainer'] and ref['typedContainer']['type'].endswith('.OptionTalkInfo')
     require(ref['displayKind']==('선택지' if choice else '대사'),'native choice or dialogue role changed')
     if ref.get('kind') in ('NpcBubbleTalkSentenceID','ControlTalkList') or g['source']=='ExcelOutput/HeartDialTalk.json':
      require(ref.get('recordContext') and at(objects[g['source']],ref['recordContext']['pointer'])==ref['recordContext']['fields'],'native table row changed')
      require(ref['recordContext'].get('serialized')==json.dumps(ref['recordContext']['fields'],ensure_ascii=False,indent=2),'native uint64 proof serialization differs')
     expected_usage={'MobileSentenceID':'모바일 안내','PcSentenceID':'PC 안내','PadSentenceID':'패드 안내','LastToBeginTalkSentenceID':'토론 설정 참조'}.get(ref['kind'],'')
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
  for g in groups:
   file=dist/'대화'/f"{g['id']}.html";require(file.exists(),'reader missing')
   page=ContextPage();page.feed(file.read_text('utf8'));require(not page.duplicates,'duplicate HTML anchors')
   require('verified-sources'in page.ids,'missing proof disclosure')
   require([r['talkId'] for r in page.context_rows]==[r['talkId'] for r in g['rows']],'rendered source row order or count differs')
   expected_native=[{'talkId':row['talkId'],'pointer':ref['recordContext']['pointer'],'text':ref['recordContext']['serialized']} for row in g['rows'] for ref in row['references'] if ref.get('recordContext',{}).get('serialized')]
   require(page.native_records==expected_native,'rendered native table proof sequence, uint64 or exact text differs')
   for ref,rendered in zip(g['rows'],page.context_rows):
    tid=ref['talkId'];row=official[tid] if ref['edition']=='official' else rows[tid]
    roles={r['displayKind'] for r in ref['references']};choice='선택지' in roles
    a=rendered['attributes'];role='choice' if choice else 'dialogue'
    require(a.get('data-speaker')==row['speaker'],'rendered source speaker differs')
    require(a.get('data-reading-kind')==role and a.get('data-passage')==role,'rendered source reading role differs')
    label='원문에 수록된 제작 안내' if tid==999999999 and row['text']=='스토리 및 연출 콘텐츠는 제작 중입니다, 기대해주세요!' else '선택지·대사 · '+row['speaker'] if choice and '대사' in roles else '선택지' if choice else '원문' if row['speaker']=='화자 미지정' else row['speaker']
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
