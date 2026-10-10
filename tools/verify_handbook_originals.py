"""Verify the additive originals against exact cached source bytes, never rewrite them."""
import argparse
import copy
import json
from pathlib import Path
import re
import sys
from build_handbook_originals import build, read, sha, digest, SITE, project_strikes
from build_official_universe_texts import corpus_digest
from verify_official_universe_texts import readable

def safe(value):
 if isinstance(value,dict):
  for k,v in value.items():
   assert not re.search(r'rawhex|dispatch.seed|password|token|localpath',k,re.I),k
   safe(v)
 elif isinstance(value,list):
  for v in value:safe(v)
 elif isinstance(value,str):
  assert not re.search(r'(?:^[A-Za-z]:[\\/]|^\\\\|\.codex-work|\.bin(?:$|[\\/]))',value),value[:100]
 elif type(value) is int:assert abs(value)<=9007199254740991,'Unsafe JSON integer'

def artifact_check(payload):
 assert payload['schemaVersion']=='starrail-handbook-originals.v1'
 e=payload['evidence'];assert e['officialKorean']['clientVersion']=='OSPRODWin4.6.0'
 assert e['metadata']['observation']=='PINNED_STRUCTURE_SEPARATE_FROM_KOREAN_VERSION'
 assert e['officialKorean']['entry']['fullEofVerified'] is True and e['officialKorean']['entry']['rows']==474191
 assert e['currentInstalledRosterVerified'] is False
 assert e['preservedCorpus']==corpus_digest()
 for name,value in e['preservedFiles'].items():assert sha((SITE/name).read_bytes())==value
 original=read(SITE/'data/catalog.json');old_ids={d['id'] for d in original}
 ids=[d['id'] for d in payload['documents']];assert len(ids)==len(set(ids)) and not set(ids)&old_ids
 docs={d['id']:d for d in payload['documents']}
 all_sections=[(d,s) for d in payload['documents'] for s in d['sections']]
 for ident,sections in payload['extensions'].items():
  assert ident in old_ids;old=read(SITE/'data/documents'/(ident+'.json'));oldanchors={s['anchor'] for s in old['sections']}
  assert not oldanchors&{s['anchor'] for s in sections}
  all_sections.extend(({'id':ident},s) for s in sections)
 def field(r,p=None):
  s=r['handbookSource'];assert re.fullmatch(r'[1-9][0-9]*',r['hash'])
  text,strikes=project_strikes(r['raw'],readable);assert r['text']==text and r['strikeRanges']==strikes
  assert 0<=s['koreanOffset']<s['koreanEnd']<=e['officialKorean']['entry']['length']
  assert type(s['hasParams']) is int and s['hasParams']>=0
  assert s['pointer']==f'/{s["row"]}/{s["field"]}'
  if s['kind']=='OBSERVED_NATIVE_TABLE':
   t=e['nativePack']['tables'][s['table']];assert t['fullEofVerified'] is True and 0<=s['row']<t['rows']
   assert 0<=s['tableStart']<s['tableEnd']<=t['length']
  else:assert s['kind']=='PINNED_METADATA_HASH_REFERENCE' and 'ExcelOutput/'+s['table']+'.json' in e['metadata']['files']
  if p:
   assert s['table']==p['table'] and s['row']==p['row'] and s['kind']==p['kind']
   assert str(p['record'][s['field']]['Hash'])==r['hash']
   if s['kind']=='OBSERVED_NATIVE_TABLE':assert (s['tableStart'],s['tableEnd'])==(p['tableStart'],p['tableEnd'])
 for d in payload['documents']:
  assert d['count']==sum(len(s['rows']) for s in d['sections'])
  assert len({s['anchor'] for s in d['sections']})==len(d['sections'])
  field(d['titleProof']);assert d['title']==d['titleProof']['text']
 for d,s in all_sections:
  p=s['handbookProof'];r=p['record'];assert p['pointer']=='/'+str(p['row']) and digest(r)==p['recordProjectionSha256']
  assert re.fullmatch(r'[a-f0-9]{64}',p['sourceRecordSha256'])
  assert s['mapping']=='EXACT_HANDBOOK_HASH_REFERENCE'
  if p['kind']=='PINNED_METADATA_HASH_REFERENCE':assert p['sourceSha256']==e['metadata']['files']['ExcelOutput/'+p['table']+'.json']
  for f in s['rows']:field(f,p)
  if p['table']=='LocalbookConfig':
   assert d['id']=='book-'+str(r['BookSeriesID']) and s['anchor']=='official46-book-'+str(r['BookID'])
   assert s['rows'][0]['book_id']==r['BookID']
  elif p['table']=='StoryAtlas':
   assert d['id']=='avatar-'+str(r['AvatarID']) and s['anchor']=='official46-story-'+str(r['StoryID'])
   assert s['rows'][0]['avatar_id']==r['AvatarID'] and s['rows'][0]['story_id']==r['StoryID']
  elif p['table']=='BookSeriesConfig':assert d['id']=='book-'+str(r['BookSeriesID'])
  elif p['table']=='LoadingDesc':assert d['id']=='lore-'+str(r['ID'])
  elif p['table'].startswith('ItemConfig'):assert d['id']=='item-'+p['table']+'-'+str(r['ID'])
  elif p['table']=='AchievementData':assert d['id']=='handbook-achievement-'+str(r['AchievementID'])
  elif p['table']=='MonsterConfig':assert d['id']=='handbook-monster-'+str(r['MonsterID'])
  elif p['table']=='RogueMazeBuff':assert 'Lv' in r and d['id']==f'handbook-blessing-{r["ID"]}-{r["Lv"]}' and d['recordLevel']==r['Lv']
  else:raise AssertionError('Unknown handbook source table')
  for rel in s['handbookRelations']:
   assert rel['targetTable'] in ('BookSeriesConfig','AvatarConfig','AchievementSeries','MonsterTemplateConfig','RogueMazeBuff')
   if rel['kind']=='EXPLICIT_MAZE_BUFF_ID_LEVEL':
    assert rel['sourceTable'] in ('RogueBuff','RogueTournBuff') and rel['targetTable']=='RogueMazeBuff'
    assert rel['sourceSha256']==e['metadata']['files']['ExcelOutput/'+rel['sourceTable']+'.json']
    assert digest(rel['sourceRecord'])==rel['sourceProjectionSha256']
    assert rel['sourceRecord']['MazeBuffID']==rel['value']['MazeBuffID']==r['ID'] and rel['sourceRecord']['MazeBuffLevel']==rel['value']['MazeBuffLevel']==r['Lv']
    assert rel['targetPointer']==p['pointer']
   else:
    key={'EXPLICIT_BOOK_SERIES_ID':'BookSeriesID','EXPLICIT_AVATAR_ID_NAME_ANNOTATION':'AvatarID','EXPLICIT_ACHIEVEMENT_SERIES_ID':'SeriesID','EXPLICIT_MONSTER_TEMPLATE_ID':'MonsterTemplateID'}[rel['kind']]
    assert rel['sourceTable']==p['table'] and rel['sourcePointer']==p['pointer']+'/'+key and r[key]==rel['value']
 groups={g['id']:g for g in payload['groups']};assigned=[id for g in groups.values() for id in g['documentIds']]
 assert len(assigned)==len(set(assigned)) and set(assigned)==set(ids)|set(payload['extensions'])
 assert groups['blessings']['title']=='축복·메아리 원문'
 for d in payload['documents']:assert d['id'] in groups[d['handbookGroup']]['documentIds']
 variantids=[]
 for g in payload['sameTitleGroups']:
  assert g['representativeId']==g['documentIds'][0]
  for id in g['documentIds']:
   d=docs[id];assert d['title']==g['title'] and d['handbookGroup']==g['group'] and d['sameTitleDocumentIds']==g['documentIds'] and d['sameTitleRepresentativeId']==g['representativeId']
  variantids.extend(g['documentIds'])
 assert len(variantids)==len(set(variantids)) and set(variantids)==set(ids)
 assert set(payload['extensions'])=={'book-647'} and len(payload['extensions']['book-647'])==1 and payload['extensions']['book-647'][0]['rows'][0]['book_id']==192195
 pearl=docs['avatar-1503'];assert len(pearl['sections'])==5 and pearl['title']=='펄' and pearl['titleProof']['handbookSource']['table']=='AvatarConfig'
 assert any(x.get('row')==1469 and x.get('id')==617000 and x['status']=='LEVEL_NOT_EXPLICIT_NO_DEFAULT_INFERRED' for x in payload['unresolved'])
 assert payload['counts']['newDocuments']==len(ids) and payload['counts']['extendedDocuments']==len(payload['extensions'])
 assert payload['counts']['newRows']==sum(len(s['rows']) for _,s in all_sections) and payload['counts']['unresolved']==len(payload['unresolved'])

def check(payload,expected=None):
 safe(payload)
 if expected is not None:assert payload==expected,'Handbook payload differs from the exact source reconstruction'
 artifact_check(payload)
 assert payload['evidence']['currentInstalledRosterVerified'] is False
 assert payload['evidence']['preservedCorpus']==corpus_digest()
 for name,value in payload['evidence']['preservedFiles'].items():assert sha((SITE/name).read_bytes())==value
 for d in payload['documents']:
  assert d['count']==sum(len(s['rows']) for s in d['sections'])
  for s in d['sections']:
   p=s['handbookProof'];assert digest(p['record'])==p['recordProjectionSha256']
   for r in s['rows']:
    source=r['handbookSource'];h=p['record'][source['field']]['Hash'];assert str(h)==r['hash']
    assert source['pointer']==f'/{p["row"]}/{source["field"]}'
   for relation in s['handbookRelations']:
    if 'sourceRecord' in relation:assert digest(relation['sourceRecord'])==relation['sourceProjectionSha256']
 assert len({d['id'] for d in payload['documents']})==len(payload['documents'])
 return payload['counts']

def varint(number):
 out=bytearray()
 while number>127:out.append((number&127)|128);number>>=7
 out.append(number);return bytes(out)

def source_canaries(payload,root,skill):
 sys.path.insert(0,str(skill/'scripts'));from binary import decode_table
 schemas=read(skill/'assets/schemas-v4.json');name='BookSeriesWorld';p=payload['evidence']['nativePack']['tables'][name]
 pack=(root/p['file']).read_bytes();raw=pack[p['offset']:p['offset']+p['length']];rows=decode_table(raw,schemas[name]['schema']);assert len(rows)==6
 cases=[raw[:cut] for cut in range(len(raw))]+[raw+b'\x00']
 start=rows[0]['_offset'];from binary import varint as parse
 flags,end=parse(raw,start);cases.append(raw[:start]+varint(flags|(1<<len(schemas[name]['schema'])))+raw[end:])
 for malformed in cases:
  try:decode_table(malformed,schemas[name]['schema'])
  except (ValueError,IndexError,UnicodeDecodeError):pass
  else:raise AssertionError('Accepted malformed source EOF or unknown slot')
 return len(cases)

def mutations(payload,expected):
 cases=[]
 def add(label,modify):
  mutant=copy.deepcopy(payload);modify(mutant)
  try:check(mutant,expected)
  except AssertionError:cases.append(label)
  else:raise AssertionError('Accepted mutation '+label)
 add('raw Korean',lambda x:x['documents'][0]['sections'][0]['rows'][0].__setitem__('raw','변조'))
 add('Korean hash',lambda x:x['documents'][0]['sections'][0]['rows'][0].__setitem__('hash','1'))
 add('Korean byte end',lambda x:x['documents'][0]['sections'][0]['rows'][0]['handbookSource'].__setitem__('koreanEnd',0))
 add('source pointer',lambda x:x['documents'][0]['sections'][0]['rows'][0]['handbookSource'].__setitem__('pointer','/0/other'))
 add('source row identity',lambda x:x['documents'][0]['sections'][0]['handbookProof']['record'].__setitem__('BookID',1))
 add('native span',lambda x:x['documents'][0]['sections'][0]['handbookProof'].__setitem__('tableEnd',0))
 add('native entry hash',lambda x:x['evidence']['nativePack']['tables']['LocalbookConfig'].__setitem__('sha256','0'*64))
 add('pinned source hash',lambda x:x['evidence']['metadata']['files'].__setitem__('ExcelOutput/MonsterConfig.json','0'*64))
 add('membership target',lambda x:next(d for d in x['documents'] if d['handbookGroup']=='blessings')['sections'][0]['handbookRelations'][0].__setitem__('targetPointer','/1469'))
 add('missing Lv default',lambda x:x['unresolved'].remove(next(r for r in x['unresolved'] if r['status']=='LEVEL_NOT_EXPLICIT_NO_DEFAULT_INFERRED')))
 add('variant omission',lambda x:next(g for g in x['sameTitleGroups'] if len(g['documentIds'])>1)['documentIds'].pop())
 add('original extension omission',lambda x:x['extensions'].pop('book-647'))
 add('current codex overclaim',lambda x:x['evidence'].__setitem__('currentInstalledRosterVerified',True))
 add('core digest bypass',lambda x:x['evidence']['preservedCorpus'].__setitem__('sha256','0'*64))
 add('unsafe number',lambda x:x['documents'][0]['sections'][0]['rows'][0].__setitem__('hash',2**63))
 add('source strike range omitted',lambda x:next(r for d in x['documents'] for s in d['sections'] for r in s['rows'] if r['strikeRanges']).__setitem__('strikeRanges',[]))
 return len(cases)

def main():
 p=argparse.ArgumentParser();p.add_argument('--official-root',type=Path);p.add_argument('--archive',type=Path);p.add_argument('--skill',type=Path);p.add_argument('--input',type=Path,default=SITE/'data/handbook-originals.json');p.add_argument('--self-test',action='store_true');p.add_argument('--verify-only',action='store_true');p.add_argument('--artifact-only',action='store_true');a=p.parse_args()
 body=a.input.read_bytes();payload=json.loads(body);assert body==(SITE/'public/handbook-originals.json').read_bytes(),'Public mirror differs'
 manifest=read(SITE/'editorial/handbook-originals-manifest.json');assert manifest['size']==len(body) and manifest['sha256']==sha(body) and manifest['schemaVersion']==payload['schemaVersion']
 expected=None
 if not a.artifact_only:
  assert a.official_root and a.archive and a.skill,'Exact source replay requires official root, archive and skill'
  expected,_=build(a.official_root,a.archive,a.skill)
 counts=check(payload,expected)
 # Artifact mutations also preserve the reviewed manifest-bound public receipt.
 # Raw replay instead uses a fresh source reconstruction as its immutable oracle.
 rejected=mutations(payload,expected if expected is not None else payload) if a.self_test else 0;malformed=source_canaries(payload,a.official_root,a.skill) if a.self_test and not a.artifact_only else 0
 print(json.dumps({'status':'PASS','counts':counts,'payloadMutationRejects':rejected,'nativeMalformedRejects':malformed,'preservedFilesVerified':True,'sourceReconstruction':'PUBLIC_ARTIFACT_CONTRACT' if a.artifact_only else 'ALL20_NATIVE_EOF_AND8_PINNED_MEMBERS_OFFICIAL_KOREAN','sha256':sha(body)},ensure_ascii=False))
if __name__=='__main__':main()
