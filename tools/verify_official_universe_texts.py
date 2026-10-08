"""Check additions independently; optional inputs reread original official bytes."""
import argparse,hashlib,json,re,sys,tarfile
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
ROLES={'FormulaStory':'story','MiracleName':'name','MiracleBGDesc':'story','CollectionName':'name','CollectionDesc':'description','CollectionEffectDesc':'effect','RankName':'name','SubStoryName':'name','MainStoryName':'name','BonusToast':'description','TriggerCondition':'condition','StoryName':'name','ScepterName':'name','ScepterBGDesc':'story','ScepterTriggerDesc':'effect'}
CONTRACTS={
 'RogueTournFormulaDisplay':('divergent-universe','FormulaDisplayID','formula','방정식','formula','방정식 이야기'),
 'RogueTournMiracleDisplay':('divergent-universe','MiracleDisplayID','curio','기물','curio','기물'),
 'RogueTournCollection':('divergent-universe','CollectionID','collection','수집품','collection','수집품'),
 'RogueDLCSubStory':('swarm-disaster','RogueDLCSubStoryID','record','기록','swarm-record','곤충 떼 재난 기록'),
 'RogueDLCMainStory':('swarm-disaster','MainStoryID','record','기록','swarm-main','곤충 떼 재난 중심 기록'),
 'RogueNousSubStory':('gold-and-gears','StoryID','record','기록','gold-record','황금과 기계 기록'),
 'RogueNousMainStory':('gold-and-gears','StoryID','record','기록','gold-main','황금과 기계 중심 기록'),
 'RogueNousStoryDisplay':('gold-and-gears','DisplayID','record','기록','gold-condition','황금과 기계 조건'),
 'RogueMagicStory':('unknowable-domain','StoryID','record','기록','unknowable-record','인지 불가 영역 기록'),
 'RogueMagicScepterDisplay':('unknowable-domain','ScepterID','scepter','셉터','scepter','셉터')}
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text('utf8'))
def at(obj,pointer):
 for key in pointer.split('/')[1:]:obj=obj[int(key)] if isinstance(obj,list) else obj[key]
 return obj
def readable(raw):
 s=raw.replace('\\n','\n').replace('\u00a0',' ')
 s=re.sub(r'\{RUBY_B#[^}]*\}|\{RUBY_E#[^}]*\}','',s)
 s=re.sub(r'</?(?:color|size|b|i|u|align|voffset|indent|line-height|unbreak)(?:=[^>]*)?>','',s,flags=re.I)
 return re.sub(r'<br\s*/?>','\n',s,flags=re.I)
def corpus():
 h=hashlib.sha256();n=0
 for folder in ('documents','dialogues'):
  for p in sorted((SITE/'data'/folder).glob('*.json')):
   h.update((p.relative_to(SITE).as_posix()+'\0'+sha(p.read_bytes())+'\n').encode());n+=1
 return {'files':n,'sha256':h.hexdigest()}
def safe(obj):
 if isinstance(obj,dict):
  for k,v in obj.items():assert 'dispatch_seed' not in k.lower();safe(v)
 elif isinstance(obj,list):
  for v in obj:safe(v)
 elif isinstance(obj,str):assert not re.search(r'(?:^[A-Za-z]:[\\/]|^\\\\|dispatch_seed|\.codex-work)',obj)
def field_check(f,e):
 assert f['role']==ROLES[f['fieldKey']]
 assert f['text']==readable(f['raw'])
 assert re.fullmatch(r'[1-9][0-9]*',f['textmapHash'])
 assert 0<=f['offset']<f['end']<=e['entry']['length']
 assert f['sourcePointer'].endswith('/'+f['fieldKey'])
def name_binding(n,r,e):
 assert r['sourceTable']=='ExcelOutput/RogueTournFormulaDisplay.json'
 assert n['sourceTable']=='ExcelOutput/RogueMazeBuff.json' and n['fieldKey']=='BuffName'
 assert n['sourceSha256']==e['metadataFiles'][n['sourceTable']]
 assert len(n['proof'])==3
 display,buff_ref,buff_row=n['proof']
 assert display['sourceTable']==buff_ref['sourceTable']=='ExcelOutput/RogueTournFormula.json'
 assert buff_row['sourceTable']==n['sourceTable']
 assert display['pointer'].endswith('/FormulaDisplayID') and buff_ref['pointer'].endswith('/MazeBuffID')
 assert buff_row['pointer'].endswith('/ID') and n['sourcePointer'].endswith('/BuffName')
 assert display['pointer'].rsplit('/',1)[0]==buff_ref['pointer'].rsplit('/',1)[0]
 assert buff_row['pointer'].rsplit('/',1)[0]==n['sourcePointer'].rsplit('/',1)[0]
 assert type(display['value']) is int and display['value']==r['sourceRecordId']
 assert type(buff_ref['value']) is int and type(buff_row['value']) is int and buff_ref['value']==buff_row['value']
 for proof in n['proof']:assert proof['sourceSha256']==e['metadataFiles'][proof['sourceTable']]
def main(a):
 path=SITE/'data/official-universe-texts.json';b=path.read_bytes();assert b==(SITE/'public/official-universe-texts.json').read_bytes();d=json.loads(b);safe(d)
 assert d['schemaVersion']=='starrail-official-universe-texts.v1'
 e=d['evidence'];assert e['clientVersion']=='OSPRODWin4.6.0' and e['officialHost']=='autopatchos.starrails.com'
 assert e['koreanPack']['sha256']=='99dadf3786823c934ff12e970df594a77d413f8b090d2645f58cc8ad903fda20'
 assert e['catalogSha256']=='ae92b3dd2417efbb9cd08e463891051ed515df2f97d40137223cec394a7e6132'
 assert e['entry']['key']=='15229857389724683600' and e['entry']['rows']==474191 and e['entry']['fullEofVerified'] is True
 assert corpus()==e['preservedCorpus']
 basepath=SITE/'data/universe-source-records.json';assert sha(basepath.read_bytes())==e['preservedUniverseSourceRecordsSha256'];base=read(basepath)
 bases={r['id']:r for m in base['modes'] for r in m['records']};ids=set();fields=0;names=0;linked=set();coordinates=set()
 for r in d['records']:
  mode,idfield,kind,label,slug,fallback=CONTRACTS[Path(r['sourceTable']).stem]
  assert (r['modeId'],r['idField'],r['kind'],r['kindLabel'])==(mode,idfield,kind,label)
  assert r['id']==f'official46-{slug}-{r["sourceRecordId"]}'
  assert re.fullmatch(r'official46-[a-z0-9-]+',r['id']) and r['id'] not in ids;ids.add(r['id'])
  assert r['sourceSha256']==e['metadataFiles'][r['sourceTable']]
  assert r['metadataReference']['pointer']=='/'+str(r['sourceRow'])
  assert r['kindLabel'] and r['fields'] and r['title']
  assert r['linkedSourceRecordIds']==list(dict.fromkeys(x['targetSourceRecordId'] for x in r['references']))
  for f in r['fields']:
   field_check(f,e);fields+=1;names+=f['role']=='name'
   assert f['sourcePointer']==f'/{r["sourceRow"]}/{f["fieldKey"]}'
   c=(r['sourceTable'],f['sourcePointer']);assert c not in coordinates;coordinates.add(c)
  named=next((f['text'] for f in r['fields'] if f['role']=='name'),None)
  unique_names={n['textmapHash']:n for n in r['names']}
  if named is not None:assert r['title']==named
  elif len(unique_names)==1:assert r['title']==next(iter(unique_names.values()))['text']
  else:assert r['title']==f'{fallback} {r["sourceRecordId"]}'
  assert r['titleStatus']==('EXACT_NAME_HASH' if named is not None or len(unique_names)==1 else 'NAME_UNVERIFIED')
  for n in r['names']:
   name_binding(n,r,e)
   assert n['text']==readable(n['raw']) and n['sourceTable']=='ExcelOutput/RogueMazeBuff.json' and n['fieldKey']=='BuffName'
   assert n['sourceSha256']==e['metadataFiles'][n['sourceTable']]
   assert n['proof'][0]['value']==r['sourceRecordId'] and n['proof'][1]['value']==n['proof'][2]['value']
  for ref in r['references']:
   target=bases[ref['targetSourceRecordId']];linked.add(target['id'])
   assert ref['sourceSha256']==e['metadataFiles'][ref['sourceTable']]
   if ref['kind']=='EXACT_SAME_METADATA_RECORD':assert target['sourceTable']==r['sourceTable'] and target['sourceRow']==r['sourceRow'] and ref['value']==r['sourceRecordId']
   else:assert ref['kind']=='EXPLICIT_FORMULA_DISPLAY_ID' and ref['sourceTable']=='ExcelOutput/RogueTournFormula.json' and ref['sourcePointer']==f'/{target["sourceRow"]}/FormulaDisplayID' and ref['value']==r['sourceRecordId'] and ref['targetPointer']==f'/{r["sourceRow"]}/FormulaDisplayID'
 assert d['counts']=={'records':len(ids),'fields':fields,'nameFields':names,'linkedSourceRecords':len(linked),'unresolvedFields':len(d['unresolved'])}
 assert fields==916 and len(d['unresolved'])==13
 # Deliberate mutations must fail independently of stored counters.
 sample=d['records'][0]['fields'][0]
 for key,value in [('raw',sample['raw']+'x'),('role','wrong'),('end',e['entry']['length']+1)]:
  try:field_check({**sample,key:value},e)
  except AssertionError:pass
  else:raise AssertionError('Accepted mutation: '+key)
 # Each foreign record's name/proofs is individually valid; attaching it to
 # another display, or splicing its buff endpoint, must still be rejected.
 named_records=[r for r in d['records'] if r['names']]
 first=named_records[0];other=next(r for r in named_records if r['sourceRecordId']!=first['sourceRecordId'] and r['names'][0]['proof'][2]['value']!=first['names'][0]['proof'][2]['value'])
 mismatched_buff={**other['names'][0],'proof':[first['names'][0]['proof'][0],first['names'][0]['proof'][1],other['names'][0]['proof'][2]]}
 for label,name in [('wrongFormulaDisplay',other['names'][0]),('incorrectMazeBuffFK',mismatched_buff)]:
  try:name_binding(name,first,e)
  except AssertionError:pass
  else:raise AssertionError('Accepted name-chain mutation: '+label)
 deep=bool(a.archive or a.official_root or a.skill)
 if deep:
  assert a.archive and a.official_root and a.skill,'Provide --archive, --official-root and --skill together'
  assert sha(a.archive.read_bytes())==e['archiveSha256'];metadata={}
  with tarfile.open(a.archive,'r:gz') as t:
   for member in t:
    name=member.name.split('/',1)[-1]
    if name in e['metadataFiles']:
     raw=t.extractfile(member).read();assert sha(raw)==e['metadataFiles'][name];metadata[name]=json.loads(raw)
  assert set(metadata)==set(e['metadataFiles'])
  sys.path.insert(0,str(a.skill/'scripts'));from binary import read_catalog,decode_textmap
  root=a.official_root;manifest=(root/'M_DesignV.bytes').read_bytes();assert sha(manifest)==e['manifestSha256'] and len(manifest)==66
  catalogbytes=(root/e['catalogFile']).read_bytes();assert sha(catalogbytes)==e['catalogSha256']
  catalog=read_catalog(catalogbytes);kr=next(x for x in catalog if x['language']=='kr')
  assert kr['file']==e['koreanPack']['file'] and kr['size']==e['koreanPack']['size']
  pack=(root/'kr'/kr['file']).read_bytes();assert sha(pack)==e['koreanPack']['sha256'] and hashlib.md5(pack).hexdigest()==e['koreanPack']['md5']
  key,length,offset=next(x for x in kr['entries'] if str(x[0])==e['entry']['key']);assert (length,offset)==(e['entry']['length'],e['entry']['offset'])
  entry=pack[offset:offset+length];assert sha(entry)==e['entry']['sha256'];rows=decode_textmap(entry);assert len(rows)==e['entry']['rows'];texts={str(x['hash']):x for x in rows};assert len(texts)==len(rows)
  expected=set();missing=set()
  for table,table_rows in metadata.items():
   if table in ('ExcelOutput/RogueTournFormula.json','ExcelOutput/RogueMazeBuff.json'):continue
   for i,row in enumerate(table_rows):
    for key,v in row.items():
     if isinstance(v,dict) and type(v.get('Hash')) is int and v['Hash']:
      c=(table,f'/{i}/{key}');assert key in ROLES
      (expected if str(v['Hash']) in texts else missing).add(c)
  assert expected==coordinates and missing=={(x['sourceTable'],x['pointer']) for x in d['unresolved']}
  for r in d['records']:
   original=metadata[r['sourceTable']][r['sourceRow']];assert original[r['idField']]==r['sourceRecordId']
   for f in r['fields']:
    assert str(at(metadata[r['sourceTable']],f['sourcePointer'])['Hash'])==f['textmapHash'];raw=texts[f['textmapHash']]
    for public,source in [('raw','raw'),('offset','offset'),('end','end'),('hasParams','has_params')]:assert f[public]==raw[source]
    assert f['legacy']==str(raw['legacy'])
   for ref in r['references']:
    assert at(metadata[ref['sourceTable']],ref['sourcePointer'])==ref['value']
    assert at(metadata[ref['targetTable']],ref['targetPointer'])==ref['value']
   for n in r['names']:
    name_binding(n,r,e)
    assert str(at(metadata[n['sourceTable']],n['sourcePointer'])['Hash'])==n['textmapHash'];raw=texts[n['textmapHash']]
    for public,source in [('raw','raw'),('offset','offset'),('end','end'),('hasParams','has_params')]:assert n[public]==raw[source]
    assert n['legacy']==str(raw['legacy'])
    for proof in n['proof']:assert e['metadataFiles'][proof['sourceTable']]==proof['sourceSha256'] and at(metadata[proof['sourceTable']],proof['pointer'])==proof['value']
    assert n['proof'][0]['sourceTable']==n['proof'][1]['sourceTable']=='ExcelOutput/RogueTournFormula.json'
    assert n['proof'][0]['pointer'].endswith('/FormulaDisplayID') and n['proof'][1]['pointer'].endswith('/MazeBuffID') and n['proof'][2]['pointer'].endswith('/ID')
    assert n['proof'][0]['pointer'].rsplit('/',1)[0]==n['proof'][1]['pointer'].rsplit('/',1)[0]
    assert n['proof'][2]['pointer'].rsplit('/',1)[0]==n['sourcePointer'].rsplit('/',1)[0]
   if r['sourceTable']=='ExcelOutput/RogueTournFormulaDisplay.json':
    expected_names=[]
    for fi,formula in enumerate(metadata['ExcelOutput/RogueTournFormula.json']):
     if formula['FormulaDisplayID']!=r['sourceRecordId']:continue
     for bi,buff in enumerate(metadata['ExcelOutput/RogueMazeBuff.json']):
      nh=str(buff.get('BuffName',{}).get('Hash',0))
      if buff['ID']==formula['MazeBuffID'] and nh in texts:expected_names.append((f'/{fi}/FormulaDisplayID',f'/{bi}/BuffName',nh))
    assert expected_names==[(n['proof'][0]['pointer'],n['sourcePointer'],n['textmapHash'])for n in r['names']]
  for u in d['unresolved']:assert str(at(metadata[u['sourceTable']],u['pointer'])['Hash'])==u['textmapHash'] and u['textmapHash'] not in texts
 print(json.dumps({'status':'PASS','scope':'official pack full EOF, pinned metadata and preserved corpus' if deep else 'repository dataset, bound evidence, preserved corpus; original pack not reread','sha256':sha(b),'counts':d['counts'],'mutationRejections':5,'nameChainMutationsRejected':['wrongFormulaDisplay','incorrectMazeBuffFK']},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--official-root',type=Path);p.add_argument('--archive',type=Path);p.add_argument('--skill',type=Path);main(p.parse_args())
