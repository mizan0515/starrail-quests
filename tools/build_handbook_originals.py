"""Preserved originals overlay: observed native tables and pinned hash references.

Game/cache inputs and the original catalog/documents/explorer stay read-only.
Pinned metadata membership is separate from the official Korean observation.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import re
from pathlib import Path
import sys
import tarfile

from build_official_universe_texts import official_input, corpus_digest, COMMIT

SITE = Path(__file__).resolve().parents[1]
ARCHIVE_SHA = 'e1eee10139b338e271467e1823cedb0ceba0c5c1c608771f2386639db308f02a'
MEMBERS = {
 'AchievementData':'d3df64f75ba8d0fcd761a707cf9bc632777632b81f36bbe0c87bca348ca089d1',
 'AchievementSeries':'fbc533005b526945523ffdfb6d79485db2c83517d6e08b92f9cb4268ee8c929f',
 'MonsterConfig':'b7ddb5557a0f4d9ef0f39711523d337532d1b8c3ba83fc375946dcf2a586787c',
 'MonsterTemplateConfig':'b79658284559a78ffe5d0166986c367e8ae12f4ea3b5bd78af0f12e6408a99ca',
 'RogueBuff':'2612352f58089bb09bac7821eb38ed281445d9ce3bf1d8e8e1849e5cbffd0c90',
 'RogueMazeBuff':'98a9582465268f93d3cc5e2fdb67ecaac39861a23f3fdaefd5a6e5a7725be6c1',
 'RogueTournBuff':'4bcf0b062941400a7aa4a530b57a5e9e42e4a0a1d8b4a67e90c7886214c27cb7',
 'AvatarConfig':'9e57b5e3700b525a3f7097895d34177f769012034ac9bd0428318c3ff47f889e'}
EXPECTED_NATIVE = {
 'pack':'ae6cc8e41213ccecc430a346909daf38ff4013d6b1441ddba384032d77b3ffd4',
 'schemas':'210f3a8c7ba399ccec0de6c0cd29a494994fc64d8098e59725876c9dae4bf56f',
 'reader':'aca04ef159de976590afa49b39fbab39ba1c69348f4c7e72f488cb18f0a838a1'}
GROUPS = [('books','서적·문서'),('characters','캐릭터 이야기'),('knowledge','세계관·용어'),
          ('light-cones','광추 이야기'),('items','아이템 설정'),('monsters','적 기록'),
          ('achievements','업적 기록'),('blessings','축복·메아리 원문'),('instructions','시점·장면 안내')]

def read(p): return json.loads(Path(p).read_text('utf8'))
def sha(raw): return hashlib.sha256(raw).hexdigest()
def digest(value): return sha(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def hashes(value):
 if isinstance(value,dict):
  if 'Hash' in value and 'Legacy' in value: return [str(value['Hash'])] if value['Hash'] else []
  return [h for v in value.values() for h in hashes(v)]
 if isinstance(value,list): return [h for v in value for h in hashes(v)]
 return []

def public_value(value):
 if isinstance(value,dict):return {k:public_value(v) for k,v in value.items()}
 if isinstance(value,list):return [public_value(v) for v in value]
 if type(value) is int and abs(value)>9007199254740991:return str(value)
 return value

def project_strikes(raw,projection):
 """Keep strike meaning as character intervals, never execute source markup."""
 marked=projection(raw);pieces=[];ranges=[];cursor=position=depth=0;start=None
 for match in re.finditer(r'</?s>',marked,re.I):
  part=marked[cursor:match.start()];pieces.append(part);position+=len(part)
  if match.group().lower()=='<s>':
   if depth==0:start=position
   depth+=1
  elif depth:
   depth-=1
   if depth==0 and start<position:ranges.append([start,position])
  cursor=match.end()
 tail=marked[cursor:];pieces.append(tail);position+=len(tail)
 if depth and start<position:ranges.append([start,position])
 return ''.join(pieces),ranges

def build(root, archive, skill):
 before=corpus_digest(); preserved_files={n:sha((SITE/n).read_bytes()) for n in ('data/catalog.json','data/explorer.json','data/aliases.json','data/universe-source-records.json')}; base_catalog=read(SITE/'data/catalog.json'); base_ids={d['id'] for d in base_catalog}
 base_hashes=set(); base_texts=set(); books={}; old_stories={}; original_documents={}
 for d in base_catalog:
  doc=read(SITE/'data/documents'/(d['id']+'.json')); original_documents[d['id']]=doc
  for section in doc['sections']:
   for row in section['rows']:
    if row.get('hash'): base_hashes.add(str(row['hash']))
    if row.get('text'): base_texts.add(row['text'].strip())
    if 'book_id' in row: books[row['book_id']]=row
 explorer=read(SITE/'data/explorer.json')
 for e in explorer['entries']:
  for s in e.get('stories',[]): old_stories[(int(e['id'].removeprefix('person-')),s['story_id'])]=s
 for name in ('official-universe-texts.json','relic-backgrounds.json'):
  def existing(x):
   if isinstance(x,dict):
    for k,v in x.items():
     if k in ('hash','textmapHash') and isinstance(v,(str,int)): base_hashes.add(str(v))
     elif k=='text' and isinstance(v,str): base_texts.add(v.strip())
     else: existing(v)
   elif isinstance(x,list):
    for v in x: existing(v)
  existing(read(SITE/'data'/name))
 texts,official,projection=official_input(root,skill)
 assert sha((skill/'scripts/binary.py').read_bytes())==EXPECTED_NATIVE['reader']
 assert sha((skill/'assets/schemas-v4.json').read_bytes())==EXPECTED_NATIVE['schemas']
 from binary import decode_table, read_catalog
 schemas=read(skill/'assets/schemas-v4.json'); catalog=read_catalog((root/official['catalogFile']).read_bytes())
 pack=(root/'1efaad7a4e7c92a8a12c66cffbe3b50a.bytes').read_bytes(); assert sha(pack)==EXPECTED_NATIVE['pack']
 tables={}; table_proofs={}; audit=[]
 for name,spec in schemas.items():
  key=int(spec['entry_hash']); matches=[(f,n,o) for f in catalog for h,n,o in f['entries'] if h==key]
  assert len(matches)==1; f,n,o=matches[0]; assert f['file']=='1efaad7a4e7c92a8a12c66cffbe3b50a.bytes'
  raw=pack[o:o+n]; rows=decode_table(raw,spec['schema']); tables[name]=rows
  table_proofs[name]={'file':f['file'],'entryKey':str(key),'offset':o,'length':n,'sha256':sha(raw),'rows':len(rows),'fullEofVerified':True}
  hs=[h for r in rows for h in hashes(r)]
  audit.append({'table':name,'rows':len(rows),'hashReferences':len(hs),'koreanJoinedReferences':sum(h in texts for h in hs),'unjoinedUniqueHashes':len(set(hs)-texts.keys()),'fullEofVerified':True})
 assert sha(archive.read_bytes())==ARCHIVE_SHA
 metadata={}
 with tarfile.open(archive,'r:gz') as source:
  for item in source:
   name=item.name.split('/',1)[-1]
   if not name.startswith('ExcelOutput/') or not name.endswith('.json'): continue
   stem=Path(name).stem
   if stem in MEMBERS:
    raw=source.extractfile(item).read(); assert sha(raw)==MEMBERS[stem]; metadata[stem]=json.loads(raw)
 assert set(metadata)==set(MEMBERS)
 for name,rows in metadata.items(): assert isinstance(rows,list),(name,'expected exact array metadata')
 documents={}; extensions=defaultdict(list); unresolved=[]; suppressed=[]; field_count=0
 def proof(name,index,row,native):
  source_row={k:v for k,v in row.items() if not k.startswith('_')};public_row=public_value(source_row)
  p={'kind':'OBSERVED_NATIVE_TABLE' if native else 'PINNED_METADATA_HASH_REFERENCE','table':name,'row':index,'pointer':'/'+str(index),'record':public_row,'recordProjectionSha256':digest(public_row),'sourceRecordSha256':digest(source_row)}
  if native: p.update({'tableStart':row['_offset'],'tableEnd':row['_end']})
  else: p.update({'sourceSha256':MEMBERS[name]})
  return p
 def field(name,index,row,key,native,label):
  nonlocal field_count
  value=row.get(key); h=str(value.get('Hash',0)) if isinstance(value,dict) else '0'
  if h=='0': return None
  ko=texts.get(h)
  if not ko:
   unresolved.append({'table':name,'row':index,'field':key,'pointer':f'/{index}/{key}','hash':h,'status':'NO_OFFICIAL_4_6_KOREAN_HASH_JOIN'});return None
  field_count+=1
  display,strikes=project_strikes(ko['raw'],projection)
  return {'label':label,'text':display,'strikeRanges':strikes,'raw':ko['raw'],'hash':h,'source':f'{name}:{index}.{key}',
    'handbookSource':{'table':name,'row':index,'field':key,'pointer':f'/{index}/{key}','kind':'OBSERVED_NATIVE_TABLE' if native else 'PINNED_METADATA_HASH_REFERENCE',
      'koreanOffset':ko['offset'],'koreanEnd':ko['end'],'legacy':str(ko['legacy']),'hasParams':ko['has_params'],**({'tableStart':row['_offset'],'tableEnd':row['_end']} if native else {})}}
 def document(ident,title,category,group,title_proof=None):
  if ident in documents:return documents[ident]
  assert ident not in base_ids,('existing document must use section extension',ident)
  d={'id':ident,'title':title,'category':category,'handbookGroup':group,'world':'분류 미확인','kind':'','source':'별도 관찰 원문','sections':[],'count':0,'url':'문서/'+ident+'.html','topics':[],'stages':[],'aliases':[],'rank':0,'chapter':'','chapterRank':0,'worldRank':0,'collection':'','titleProof':title_proof}
  documents[ident]=d;return d
 def section(ident,title,rows,source_proof,relations=None,anchor=None):
  rows=[r for r in rows if r is not None]
  if not rows:return
  sec={'title':title,'rows':rows,'source':source_proof['table'],'mapping':'EXACT_HANDBOOK_HASH_REFERENCE','anchor':anchor or 'official46-'+str(source_proof['row']),
    'handbookProof':source_proof,'handbookRelations':relations or []}
  if ident in base_ids:extensions[ident].append(sec)
  else:documents[ident]['sections'].append(sec);documents[ident]['count']+=len(rows)
 def new_body(rows):return any(r and r['text'].strip() and r['text'].strip() not in base_texts for r in rows)
 series={r['BookSeriesID']:(i,r) for i,r in enumerate(tables['BookSeriesConfig'])}
 for i,row in enumerate(tables['LocalbookConfig']):
  if row['BookID'] in books:continue
  sid=row.get('BookSeriesID',0); si,sr=series[sid]; title=field('BookSeriesConfig',si,sr,'BookSeries',True,'자료명'); inside=field('LocalbookConfig',i,row,'BookInsideName',True,'권명'); body=field('LocalbookConfig',i,row,'BookContent',True,'본문')
  assert title and inside and body
  ident='book-'+str(sid)
  if ident not in base_ids:
   document(ident,title['text'],'서적·문서','books',title)
   comment=field('BookSeriesConfig',si,sr,'BookSeriesComments',True,'자료 설명')
   if comment:section(ident,'자료 설명',[comment],proof('BookSeriesConfig',si,sr,True))
  body.update({'book_id':row['BookID'],'title_hash':inside['hash'],'bookOrder':row.get('BookSeriesInsideID',0)})
  section(ident,inside['text'],[body],proof('LocalbookConfig',i,row,True),[{'kind':'EXPLICIT_BOOK_SERIES_ID','sourceTable':'LocalbookConfig','sourcePointer':f'/{i}/BookSeriesID','value':sid,'targetTable':'BookSeriesConfig','targetPointer':f'/{si}/BookSeriesID'}],anchor='official46-book-'+str(row['BookID']))
 avatars={r['AvatarID']:(i,r) for i,r in enumerate(metadata['AvatarConfig'])}
 for i,row in enumerate(tables['StoryAtlas']):
  aid=row['AvatarID']; story=row['StoryID']
  if (aid,story) in old_stories:continue
  body=field('StoryAtlas',i,row,'Story',True,'본문'); assert body
  ni,nr=avatars[aid]; name=field('AvatarConfig',ni,nr,'AvatarName',False,'이름'); assert name
  ident='avatar-'+str(aid);document(ident,name['text'],'캐릭터 이야기','characters',name);body.update({'avatar_id':aid,'story_id':story})
  section(ident,'이야기 '+str(story),[body],proof('StoryAtlas',i,row,True),[{'kind':'EXPLICIT_AVATAR_ID_NAME_ANNOTATION','sourceTable':'StoryAtlas','sourcePointer':f'/{i}/AvatarID','value':aid,'targetTable':'AvatarConfig','targetPointer':f'/{ni}/AvatarID'}],anchor='official46-story-'+str(story))
 for i,row in enumerate(tables['LoadingDesc']):
  ident='lore-'+str(row['ID'])
  if ident in base_ids:continue
  title=field('LoadingDesc',i,row,'TitleTextmapID',True,'제목');body=field('LoadingDesc',i,row,'DescTextmapID',True,'본문');assert title and body
  group='instructions' if '시점으로 전환' in title['text'] else 'knowledge'
  document(ident,title['text'],'시점·장면 안내' if group=='instructions' else '세계관·용어',group,title)
  section(ident,'기록',[body],proof('LoadingDesc',i,row,True))
 for name,category,group in [('ItemConfigEquipment','광추 이야기','light-cones'),('ItemConfig','아이템 설정','items'),('ItemConfigBook','아이템 설정','items'),('ItemConfigRelic','유물 이야기','items')]:
  for i,row in enumerate(tables[name]):
   ident='item-'+name+'-'+str(row['ID'])
   if ident in base_ids:continue
   title=field(name,i,row,'ItemName',True,'명칭'); bodies=[field(name,i,row,k,True,label) for k,label in [('ItemDesc','설명'),('ItemBGDesc','배경 이야기')]]
   if not title or not new_body([r for r in bodies if r and r['text'].strip()!=title['text'].strip()]):
    suppressed.append({'table':name,'row':i,'id':ident,'reason':'NO_NEW_NON_NAME_BODY','proof':proof(name,i,row,True),'title':title,'fields':[b for b in bodies if b]});continue
   document(ident,title['text'],category,group,title);section(ident,'설정 기록',bodies,proof(name,i,row,True))
 achievement_series={r['SeriesID']:(i,r) for i,r in enumerate(metadata['AchievementSeries'])}
 for i,row in enumerate(metadata['AchievementData']):
  title=field('AchievementData',i,row,'AchievementTitle',False,'명칭'); assert title
  ident='handbook-achievement-'+str(row['AchievementID']);d=document(ident,title['text'],'업적 기록','achievements',title)
  si,sr=achievement_series[row['SeriesID']];series_title=field('AchievementSeries',si,sr,'SeriesTitle',False,'자료 분류');assert series_title;d['collection']=series_title['text']
  bodies=[field('AchievementData',i,row,k,False,label) for k,label in [('AchievementDesc','설명'),('AchievementDescPS','설명 보충'),('HideAchievementDesc','숨겨진 업적 설명'),('RecordText','기록 문구'),('AchievementTitlePS','명칭 보충')]]
  section(ident,'원문 기록',bodies,proof('AchievementData',i,row,False),[{'kind':'EXPLICIT_ACHIEVEMENT_SERIES_ID','sourceTable':'AchievementData','sourcePointer':f'/{i}/SeriesID','value':row['SeriesID'],'targetTable':'AchievementSeries','targetPointer':f'/{si}/SeriesID'}])
 templates={r['MonsterTemplateID']:(i,r) for i,r in enumerate(metadata['MonsterTemplateConfig'])}
 for i,row in enumerate(metadata['MonsterConfig']):
  title=field('MonsterConfig',i,row,'MonsterName',False,'명칭');body=field('MonsterConfig',i,row,'MonsterIntroduction',False,'설명')
  if not title or not body:continue
  ti,tr=templates[row['MonsterTemplateID']];ident='handbook-monster-'+str(row['MonsterID']);document(ident,title['text'],'적 기록','monsters',title)
  section(ident,'원문 기록',[body],proof('MonsterConfig',i,row,False),[{'kind':'EXPLICIT_MONSTER_TEMPLATE_ID','sourceTable':'MonsterConfig','sourcePointer':f'/{i}/MonsterTemplateID','value':row['MonsterTemplateID'],'targetTable':'MonsterTemplateConfig','targetPointer':f'/{ti}/MonsterTemplateID'}])
 buff_index={}; memberships=defaultdict(list)
 for i,row in enumerate(metadata['RogueMazeBuff']):
  if 'Lv' not in row:
   unresolved.append({'table':'RogueMazeBuff','row':i,'id':row.get('ID'),'status':'LEVEL_NOT_EXPLICIT_NO_DEFAULT_INFERRED'});continue
  key=(row['ID'],row['Lv']);assert key not in buff_index;buff_index[key]=(i,row)
 for name in ('RogueBuff','RogueTournBuff'):
  for i,row in enumerate(metadata[name]):
   if 'MazeBuffID' not in row or 'MazeBuffLevel' not in row:continue
   key=(row['MazeBuffID'],row['MazeBuffLevel'])
   if key not in buff_index:
    unresolved.append({'table':name,'row':i,'id':list(key),'status':'NO_EXPLICIT_ID_LEVEL_TARGET'});continue
   memberships[key].append({'kind':'EXPLICIT_MAZE_BUFF_ID_LEVEL','sourceTable':name,'sourcePointer':f'/{i}','sourceSha256':MEMBERS[name],'value':{'MazeBuffID':key[0],'MazeBuffLevel':key[1]},'sourceRecord':public_value(row),'sourceProjectionSha256':digest(public_value(row)),'sourceRecordSha256':digest(row),'targetTable':'RogueMazeBuff','targetPointer':f'/{buff_index[key][0]}'})
 for key,relations in memberships.items():
  i,row=buff_index[key];title=field('RogueMazeBuff',i,row,'BuffName',False,'명칭');body=field('RogueMazeBuff',i,row,'BuffDesc',False,'설명')
  if not title or not body:continue
  ident='handbook-blessing-'+str(key[0])+'-'+str(key[1]);d=document(ident,title['text'],'축복·메아리 원문','blessings',title);d['recordLevel']=key[1]
  bodies=[body]+[field('RogueMazeBuff',i,row,k,False,label) for k,label in [('BuffSimpleDesc','짧은 설명'),('BuffDescBattle','전투 설명')]]
  section(ident,'레벨 '+str(key[1])+' 원문',bodies,proof('RogueMazeBuff',i,row,False),relations)
 empty=[ident for ident,d in documents.items() if not d['sections']]
 for ident in empty:del documents[ident]
 groups=defaultdict(list)
 for d in documents.values():groups[d['handbookGroup']].append(d['id'])
 for ident,sections in extensions.items():groups['books'].append(ident)
 same_titles=defaultdict(list)
 for d in documents.values():same_titles[(d['handbookGroup'],d['title'])].append(d['id'])
 title_groups=[]
 for (group,title),idents in same_titles.items():
  representative=idents[0]
  for ident in idents:documents[ident]['sameTitleDocumentIds']=idents;documents[ident]['sameTitleRepresentativeId']=representative
  title_groups.append({'group':group,'title':title,'documentIds':idents,'representativeId':representative})
 payload={'schemaVersion':'starrail-handbook-originals.v1','evidence':{'officialKorean':official,'nativePack':{'file':'1efaad7a4e7c92a8a12c66cffbe3b50a.bytes','sha256':EXPECTED_NATIVE['pack'],'tables':table_proofs,'readerSha256':EXPECTED_NATIVE['reader'],'schemasSha256':EXPECTED_NATIVE['schemas']},'metadata':{'commit':COMMIT,'archiveSha256':ARCHIVE_SHA,'files':{f'ExcelOutput/{k}.json':v for k,v in MEMBERS.items()},'observation':'PINNED_STRUCTURE_SEPARATE_FROM_KOREAN_VERSION'},'preservedCorpus':before,'preservedFiles':preserved_files,'currentInstalledRosterVerified':False},
 'documents':list(documents.values()),'extensions':dict(extensions),'groups':[{'id':ident,'title':label,'documentIds':groups[ident]} for ident,label in GROUPS if groups[ident]],'sameTitleGroups':title_groups,'unresolved':unresolved,'sourceOnlyRecords':suppressed,'nativeTableAudit':audit,
 'counts':{'newDocuments':len(documents),'extendedDocuments':len(extensions),'newRows':sum(d['count'] for d in documents.values())+sum(len(s['rows']) for ss in extensions.values() for s in ss),'categories':dict(Counter(d['category'] for d in documents.values())),'unresolved':len(unresolved)}}
 assert corpus_digest()==before and all(sha((SITE/n).read_bytes())==h for n,h in preserved_files.items())
 private={'suppressedRows':suppressed,'nativeTableAudit':audit,'counts':payload['counts'],'existingIDsUnmodified':True,'existingVersionTextChangesDeferred':True,'schemaScope':'All twenty known tables EOF; encyclopedia fields only. Mission/message/Talk ownership unchanged.'}
 return payload,private

def main():
 p=argparse.ArgumentParser();p.add_argument('--official-root',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--skill',type=Path,required=True);p.add_argument('--output',type=Path,default=SITE/'data/handbook-originals.json');p.add_argument('--report',type=Path);a=p.parse_args()
 result,report=build(a.official_root,a.archive,a.skill)
 body=json.dumps(result,ensure_ascii=False,separators=(',',':')).encode('utf8')
 for target in [a.output,SITE/'public/handbook-originals.json']:
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
 manifest={'schemaVersion':result['schemaVersion'],'path':'public/handbook-originals.json','target':'data/handbook-originals.json','size':len(body),'sha256':sha(body)}
 (SITE/'editorial/handbook-originals-manifest.json').write_text(json.dumps(manifest,separators=(',',':')),'utf8')
 if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
 print(json.dumps(result['counts'],ensure_ascii=False))
if __name__=='__main__':main()
