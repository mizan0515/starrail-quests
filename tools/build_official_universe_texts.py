"""Selective official Korean additions; preserved site documents stay immutable."""
import argparse,hashlib,json,sys,tarfile
from pathlib import Path
from urllib.parse import urlparse

SITE=Path(__file__).resolve().parents[1]
COMMIT='8b178dd48698e5e7b12f0cc319ddab149f2ffc5c'
TABLES={
 'RogueTournFormulaDisplay':('divergent-universe','FormulaDisplayID','formula','방정식','방정식 이야기'),
 'RogueTournMiracleDisplay':('divergent-universe','MiracleDisplayID','curio','기물','기물'),
 'RogueTournCollection':('divergent-universe','CollectionID','collection','수집품','수집품'),
 'RogueTournRecordShowcase':('divergent-universe','AreaID','rank','등차','등차'),
 'RogueDLCSubStory':('swarm-disaster','RogueDLCSubStoryID','record','기록','곤충 떼 재난 기록'),
 'RogueDLCMainStory':('swarm-disaster','MainStoryID','record','기록','곤충 떼 재난 중심 기록'),
 'RogueNousSubStory':('gold-and-gears','StoryID','record','기록','황금과 기계 기록'),
 'RogueNousMainStory':('gold-and-gears','StoryID','record','기록','황금과 기계 중심 기록'),
 'RogueNousStoryDisplay':('gold-and-gears','DisplayID','record','기록','황금과 기계 조건'),
 'RogueMagicStory':('unknowable-domain','StoryID','record','기록','인지 불가 영역 기록'),
 'RogueMagicScepterDisplay':('unknowable-domain','ScepterID','scepter','셉터','셉터')}
FIELDS={'FormulaStory':('이야기','story'),'MiracleName':('명칭','name'),'MiracleBGDesc':('배경 이야기','story'),'CollectionName':('명칭','name'),'CollectionDesc':('설명','description'),'CollectionEffectDesc':('게임 효과','effect'),'RankName':('등차 명칭','name'),'SubStoryName':('기록 명칭','name'),'MainStoryName':('중심 기록 명칭','name'),'BonusToast':('보상 알림','description'),'TriggerCondition':('조건','condition'),'StoryName':('기록 명칭','name'),'ScepterName':('명칭','name'),'ScepterBGDesc':('배경 이야기','story'),'ScepterTriggerDesc':('발동 효과','effect')}
SLUGS={'RogueTournFormulaDisplay':'formula','RogueTournMiracleDisplay':'curio','RogueTournCollection':'collection','RogueTournRecordShowcase':'rank','RogueDLCSubStory':'swarm-record','RogueDLCMainStory':'swarm-main','RogueNousSubStory':'gold-record','RogueNousMainStory':'gold-main','RogueNousStoryDisplay':'gold-condition','RogueMagicStory':'unknowable-record','RogueMagicScepterDisplay':'scepter'}
def read(p):return json.loads(p.read_text('utf8'))
def sha(b):return hashlib.sha256(b).hexdigest()
def corpus_digest():
 h=hashlib.sha256();count=0
 for folder in ('documents','dialogues'):
  for p in sorted((SITE/'data'/folder).glob('*.json')):
   h.update((p.relative_to(SITE).as_posix()+'\0'+sha(p.read_bytes())+'\n').encode());count+=1
 return {'files':count,'sha256':h.hexdigest()}

def official_input(root,skill):
 sys.path.insert(0,str(skill/'scripts'))
 from binary import read_catalog,decode_textmap
 from export_library import readable
 manifest=(root/'M_DesignV.bytes').read_bytes();assert len(manifest)==66 and manifest.startswith(b'SRMI')
 md5=b''.join(manifest[i:i+4][::-1] for i in range(28,44,4)).hex();size=int.from_bytes(manifest[44:52],'little')
 catalog_bytes=(root/('DesignV_'+md5+'.bytes')).read_bytes();assert len(catalog_bytes)==size and hashlib.md5(catalog_bytes).hexdigest()==md5
 catalog=read_catalog(catalog_bytes);reports=read(root/'catalog.json');assert reports['version']=='OSPRODWin4.6.0' and reports['catalog']==json.loads(json.dumps(catalog))
 host=urlparse(reports['baseUrl']).hostname;assert host and host.endswith('.starrails.com')
 kr=[f for f in catalog if f['language']=='kr'];assert len(kr)==1;info=kr[0]
 pack=(root/'kr'/info['file']).read_bytes();assert len(pack)==info['size'] and hashlib.md5(pack).hexdigest()==Path(info['file']).stem
 report=read(root/'korean-pack-provenance.json');assert report['verified'] and report['sha256']==sha(pack) and report['version']==reports['version']
 key,length,offset=next(e for e in info['entries'] if e[0]==15229857389724683600)
 entry=pack[offset:offset+length];rows=decode_textmap(entry);assert len({r['hash'] for r in rows})==len(rows)
 evidence={'kind':'OFFICIAL_GAME_KOREAN_TEXTMAP','clientVersion':reports['version'],'officialHost':host,'manifestSha256':sha(manifest),'catalogSha256':sha(catalog_bytes),'catalogFile':'DesignV_'+md5+'.bytes','koreanPack':{'file':info['file'],'sha256':sha(pack),'md5':Path(info['file']).stem,'size':len(pack)},'entry':{'key':str(key),'offset':offset,'length':length,'sha256':sha(entry),'rows':len(rows),'fullEofVerified':True},'projection':'export_library.readable: only whitespace, markup and ruby display normalization; raw retained'}
 return {str(r['hash']):r for r in rows},evidence,readable

def build(root,archive,skill):
 before=corpus_digest();base=SITE/'data/universe-source-records.json';base_bytes=base.read_bytes();base_sources=read(base)
 texts,evidence,projection=official_input(root,skill);metadata={};hashes={}
 wanted={f'ExcelOutput/{n}.json' for n in TABLES}|{'ExcelOutput/RogueTournFormula.json','ExcelOutput/RogueMazeBuff.json'}
 with tarfile.open(archive,'r:gz') as t:
  for item in t:
   name=item.name.split('/',1)[-1]
   if name in wanted:
    raw=t.extractfile(item).read();metadata[name]=json.loads(raw);hashes[name]=sha(raw)
 assert set(metadata)==wanted and sha(archive.read_bytes())==base_sources['evidence']['archiveSha256']
 for name in wanted & set(base_sources['evidence']['structureFiles']):assert hashes[name]==base_sources['evidence']['structureFiles'][name]
 records=[];unresolved=[];field_count=0;name_count=0
 base_records=[r for m in base_sources['modes'] for r in m['records']]
 for table,(mode,idfield,kind,kindlabel,fallback) in TABLES.items():
  path='ExcelOutput/'+table+'.json';seen=set()
  for i,row in enumerate(metadata[path]):
   rid=row[idfield];fields=[]
   for key,value in row.items():
    if not isinstance(value,dict) or type(value.get('Hash')) is not int or not value['Hash']:continue
    assert key in FIELDS,(table,key);text_hash=str(value['Hash']);pointer=f'/{i}/{key}'
    if text_hash not in texts:
     unresolved.append({'modeId':mode,'sourceTable':path,'sourceRow':i,'recordId':rid,'fieldKey':key,'pointer':pointer,'textmapHash':text_hash,'sourceSha256':hashes[path],'status':'NO_OFFICIAL_4_6_KOREAN_HASH_JOIN'});continue
    source=texts[text_hash];label,role=FIELDS[key];field_count+=1;name_count+=role=='name'
    fields.append({'label':label,'fieldKey':key,'role':role,'raw':source['raw'],'text':projection(source['raw']),'textmapHash':text_hash,'offset':source['offset'],'end':source['end'],'legacy':str(source['legacy']),'hasParams':source['has_params'],'sourcePointer':pointer})
   if not fields:continue
   assert rid not in seen,(table,rid);seen.add(rid)
   links=[];linked=[]
   for r in base_records:
    if r['sourceTable']==path and r['sourceRow']==i:
     linked.append(r['id']);links.append({'kind':'EXACT_SAME_METADATA_RECORD','sourceTable':path,'sourcePointer':f'/{i}/{idfield}','sourceSha256':hashes[path],'value':rid,'targetSourceRecordId':r['id'],'targetTable':r['sourceTable'],'targetPointer':f'/{r["sourceRow"]}/{idfield}'})
   if table=='RogueTournFormulaDisplay':
    formula_path='ExcelOutput/RogueTournFormula.json'
    for r in base_records:
     if r['sourceTable']!=formula_path:continue
     formula=metadata[formula_path][r['sourceRow']]
     if formula.get('FormulaDisplayID')==rid:
      linked.append(r['id']);links.append({'kind':'EXPLICIT_FORMULA_DISPLAY_ID','sourceTable':formula_path,'sourcePointer':f'/{r["sourceRow"]}/FormulaDisplayID','sourceSha256':hashes[formula_path],'value':rid,'targetTable':path,'targetPointer':f'/{i}/{idfield}','targetSourceRecordId':r['id']})
   names=[]
   if table=='RogueTournFormulaDisplay':
    formula_path='ExcelOutput/RogueTournFormula.json';buff_path='ExcelOutput/RogueMazeBuff.json'
    for fi,formula in enumerate(metadata[formula_path]):
     if formula.get('FormulaDisplayID')!=rid:continue
     for bi,buff in enumerate(metadata[buff_path]):
      if buff.get('ID')!=formula.get('MazeBuffID'):continue
      nh=str(buff.get('BuffName',{}).get('Hash',0))
      if nh not in texts:continue
      source=texts[nh]
      names.append({'raw':source['raw'],'text':projection(source['raw']),'textmapHash':nh,'offset':source['offset'],'end':source['end'],'legacy':str(source['legacy']),'hasParams':source['has_params'],'fieldKey':'BuffName','sourceTable':buff_path,'sourceSha256':hashes[buff_path],'sourcePointer':f'/{bi}/BuffName','proof':[{'sourceTable':formula_path,'sourceSha256':hashes[formula_path],'pointer':f'/{fi}/FormulaDisplayID','value':rid},{'sourceTable':formula_path,'sourceSha256':hashes[formula_path],'pointer':f'/{fi}/MazeBuffID','value':formula['MazeBuffID']},{'sourceTable':buff_path,'sourceSha256':hashes[buff_path],'pointer':f'/{bi}/ID','value':buff['ID']}]})
   direct_title=next((f['text'] for f in fields if f['role']=='name'),None)
   unique_names={n['textmapHash']:n for n in names}
   title=direct_title or (next(iter(unique_names.values()))['text'] if len(unique_names)==1 else f'{fallback} {rid}')
   records.append({'id':'official46-'+SLUGS[table]+'-'+str(rid),'modeId':mode,'title':title,'titleStatus':'EXACT_NAME_HASH' if direct_title or len(unique_names)==1 else 'NAME_UNVERIFIED','names':names,'kind':kind,'kindLabel':kindlabel,'sourceTable':path,'sourceRow':i,'sourceRecordId':rid,'idField':idfield,'sourceSha256':hashes[path],'fields':fields,'linkedSourceRecordIds':list(dict.fromkeys(linked)),'references':links,'metadataReference':{'sourceTable':path,'sourceSha256':hashes[path],'pointer':f'/{i}','url':f'https://github.com/DimbreathBot/TurnBasedGameData/blob/{COMMIT}/{path}'}})
 result={'schemaVersion':'starrail-official-universe-texts.v1','evidence':{**evidence,'metadataCommit':COMMIT,'archiveSha256':sha(archive.read_bytes()),'metadataFiles':hashes,'preservedCorpus':before,'preservedUniverseSourceRecordsSha256':sha(base_bytes)},'records':records,'unresolved':unresolved,'counts':{'records':len(records),'fields':field_count,'nameFields':name_count,'linkedSourceRecords':len({x for r in records for x in r['linkedSourceRecordIds']}),'unresolvedFields':len(unresolved)}}
 assert corpus_digest()==before and base.read_bytes()==base_bytes
 for path in (SITE/'data/official-universe-texts.json',SITE/'public/official-universe-texts.json'):path.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),'utf8')
 print(json.dumps(result['counts']))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--official-root',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--skill',type=Path,required=True);a=p.parse_args();build(a.official_root,a.archive,a.skill)
