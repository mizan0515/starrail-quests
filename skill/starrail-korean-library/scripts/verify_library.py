"""Verify source preservation, coverage, attribution, rendered exports and optional ZIP."""
import argparse,csv,hashlib,json,re,zipfile,time
from pathlib import Path
from collections import Counter
from binary import LocalData,decode_table,decode_textmap,varint
from export_library import SKILL,hash_of,readable,sha,dump,render_txt,render_html,scenes_from_object

def require(ok,message):
    if not ok:raise ValueError(message)
def verify_zip(path,root):
    files={p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file()}
    with zipfile.ZipFile(path) as z:
        names=[i.filename for i in z.infolist() if not i.is_dir()]
        require(len(names)==len(set(names)) and set(names)==set(files),'ZIP member set differs from library')
        for name,p in files.items():
            require(z.getinfo(name).file_size==p.stat().st_size,'ZIP size mismatch: '+name)
            h=hashlib.sha256()
            with z.open(name) as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            require(h.hexdigest()==sha(p),'ZIP content mismatch: '+name)
    return {'files':len(files),'size':path.stat().st_size,'sha256':sha(path)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--zip',type=Path);ap.add_argument('--zip-only',action='store_true');args=ap.parse_args();out=args.output.resolve()
    if args.zip_only:
        require(args.zip is not None,'ZIP required');result=verify_zip(args.zip,out);dump(args.zip.with_suffix('.verification.json'),{'status':'PASS','archive':result});print(json.dumps(result,indent=2));return
    started=time.time();report=json.loads((out/'검증/추출보고서.json').read_text(encoding='utf8'));catalog=json.loads((out/'목록.json').read_text(encoding='utf8'));data=LocalData(report['source_root'])
    for path,e in report['source_files'].items():
        require(Path(path).resolve().is_relative_to(data.root),'Source outside requested game folder')
        require(sha(path)==e['sha256'],'Original game source changed: '+path)
    schemas=json.loads((SKILL/'assets/schemas-v4.json').read_text(encoding='utf8'));require(sha(SKILL/'assets/schemas-v4.json')==report['schemas_sha256'],'Schema digest changed')
    pack=[f for f in data.catalog if f['language']=='kr'];require(len(pack)==1,'Korean pack ambiguous');raw,_=data.entry(pack[0]['entries'][0][0]);texts=decode_textmap(raw);textmap={r['hash']:r['raw'] for r in texts}
    with (out/'원문/전체한국어.csv').open(encoding='utf-8-sig',newline='') as f:
        count=0
        for actual,expected in zip(csv.DictReader(f),texts,strict=True):
            require(actual=={k:str(v) for k,v in expected.items()},'Raw Korean CSV differs at row '+str(count));count+=1
    tables={};local=json.loads((out/'원문/로컬표.json').read_text(encoding='utf8'))
    for name,info in schemas.items():
        raw,source=data.entry(info['entry_hash']);rows=decode_table(raw,info['schema']);tables[name]=rows
        require(local['tables'][name]==rows and local['sources'][name]==source,'Decoded local table/source mismatch: '+name)
    talks={r.get('TalkSentenceID',0):r for r in tables['TalkSentenceConfig']}
    with (out/'원문/전체대사.csv').open(encoding='utf-8-sig',newline='') as f:
        for actual,r in zip(csv.DictReader(f),talks.values(),strict=True):
            expected={'id':r.get('TalkSentenceID',0),'voice':r.get('VoiceID',0),'speaker_hash':hash_of(r.get('TextmapTalkSentenceName')),'text_hash':hash_of(r.get('TalkSentenceText')),'speaker_raw':textmap.get(hash_of(r.get('TextmapTalkSentenceName')),''),'raw':textmap.get(hash_of(r.get('TalkSentenceText')),''),'offset':r['_offset'],'end':r['_end']}
            require(actual=={k:str(v) for k,v in expected.items()},'Raw dialogue CSV mismatch: '+actual['id'])
    structure=Path(report['structure_root']);structure_files=report['structure_file_sha256']
    for rel,digest in structure_files.items():require(sha(structure/rel)==digest,'Auxiliary structure changed: '+rel)
    contacts={r['ID']:r for r in tables['MessageContactsConfig']};messages={r['ID']:r for r in tables['MessageItemConfig']};scids={}
    source_rows={}
    special_ids={'MainMission':['MainMissionID'],'BookSeriesConfig':['BookSeriesID'],'LocalbookConfig':['BookID'],'StoryAtlas':['AvatarID','StoryID'],'RogueAeonStoryConfig':['RogueAeonID','AeonStoryID'],'RogueAeonDisplay':['DisplayID'],'RogueMiracleDisplay':['MiracleDisplayID']}
    for name,records in tables.items():
        for record in records:
            ids=special_ids.get(name,['ID'])
            if all(k in record for k in ids):source_rows[name+':'+':'.join(str(record[k]) for k in ids)]=record
    for r in tables['MessageGroupConfig']:
        for sid in r.get('MessageSectionIDList',[]):scids[sid]=r.get('MessageContactsID',0)
    all_talks=set();books=set();stories=set();doc_ids=set();row_count=0;matched=0;missing_refs=0;categories=Counter();body_index={}
    common_cache={};flat=(out/'정리본문.csv').open(encoding='utf-8-sig',newline='');flat_reader=csv.DictReader(flat)
    # Published catalog order and CSV order intentionally agree after finalization;
    # future exports may use insertion order, so match rows as a multiset by document.
    csv_docs={}
    for r in flat_reader:csv_docs.setdefault(r['doc_id'],[]).append(r)
    flat.close()
    for entry in catalog['documents']:
        doc=json.loads((out/entry['json']).read_text(encoding='utf8'));require(doc['id'] not in doc_ids,'Duplicate document');doc_ids.add(doc['id']);categories[doc['category']]+=1
        for k in entry:require(entry[k]==doc[k],'Catalog/document mismatch '+doc['id']+':'+k)
        require((out/doc['txt']).read_text(encoding='utf8')==render_txt(doc),'TXT differs from document: '+doc['id'])
        require((out/doc['url']).read_text(encoding='utf8')==render_html(doc),'HTML differs from document: '+doc['id'])
        rows=[r for s in doc['sections'] for r in s['rows']];require(doc['count']==len(rows),'Document count mismatch');row_count+=len(rows)
        body_index[doc['id']]='\n'.join([doc['title']]+[r.get('speaker','')+' '+r.get('text','') for r in rows])
        expected_flat=[]
        for s in doc['sections']:
            if s['source'] in structure_files:
                rel=s['source'];refs=scenes_from_object(json.loads((structure/rel).read_text(encoding='utf8')))
                require([x['id'] for x in refs]==[r['talk_id'] for r in s['rows']],'Scene reference order changed: '+rel)
                require([x['destinations'] for x in refs]==[r.get('destinations',{}) for r in s['rows']],'Scene option/trigger metadata lost: '+rel)
            if s['mapping']=='LOCAL_ID_ORDER_MATCH':
                matched+=1;rel=s['source'];require(rel in structure_files,'Unattributed scene structure')
                known=list(dict.fromkeys(x['id'] for x in refs if x['id'] in talks));require(len(known)>=2,'Insufficient matching IDs')
                key,length,offset=s['local_entry'];raw,source=data.entry(key);require(source['size']==length and source['offset']==offset,'Local scene evidence offsets differ')
                sequence=[]
                for m in re.finditer(rb'[\x80-\xff]{3,4}[\x00-\x7f]',raw):
                    value,_=varint(m.group(),0)
                    if value in talks:sequence.append(value)
                iterator=iter(sequence);require(all(any(v==tid for v in iterator) for tid in known),'Local ID order evidence failed: '+rel)
            for row in s['rows']:
                key=int(row.get('hash') or 0);sk=int(row.get('speaker_hash') or 0)
                if key:require(key in textmap and row['text']==readable(textmap[key]),'Body differs from local Korean hash: '+doc['id'])
                else:require(not row.get('text') or row['text'].startswith(('[한국어 본문 누락:','[로컬 대사 ID 없음:')),'Unattributed nonempty body: '+doc['id'])
                if sk:require(row.get('speaker')==readable(textmap[sk]),'Speaker differs from local Korean hash')
                if row.get('source') and '.' in row['source']:
                    src,field=row['source'].rsplit('.',1)
                    if src in source_rows:
                        expected=hash_of(source_rows[src].get(field));require(key==expected or expected not in textmap,'Body linked to incorrect local table field: '+row['source'])
                if 'talk_id' in row:
                    tid=row['talk_id']
                    if tid in talks:
                        all_talks.add(tid);r=talks[tid];expected=hash_of(r.get('TalkSentenceText'))
                        require(key==expected or expected not in textmap,'Dialogue attributed to wrong text hash')
                        expected_speaker=readable(textmap.get(hash_of(r.get('TextmapTalkSentenceName')),'')) or '화자 미지정'
                        require(row.get('speaker')==expected_speaker,'Dialogue speaker attribution differs')
                    else:missing_refs+=1;require(row['label']=='대사 누락','Missing local dialogue unmarked')
                if 'message_id' in row:
                    r=messages[row['message_id']];cid=r.get('ContactsID',scids.get(r.get('SectionID',0),0)) or scids.get(r.get('SectionID',0),0);sender=r.get('Sender',0)
                    expected_speaker=readable(textmap.get(hash_of(contacts.get(cid,{}).get('Name')),'')) or f'연락처 {cid}'
                    if sender in (2,3):expected_speaker='{NICKNAME}'
                    elif sender==4:expected_speaker='시스템'
                    require(row['speaker']==expected_speaker,'Message sender attribution differs')
                    require(row['destinations']['NextItemIDList']==r.get('NextItemIDList',[]),'Message branch lost')
                    field=row['source'].split('.')[-1];expected=hash_of(r.get(field));require(key==expected or expected not in textmap,'Message hash differs')
                if 'book_id' in row:books.add(row['book_id'])
                if 'story_id' in row:stories.add((row['avatar_id'],row['story_id']))
                expected_flat.append({k:str(v) for k,v in {'doc_id':doc['id'],'category':doc['category'],'title':doc['title'],'section':s['title'],**row,'destinations':json.dumps(row.get('destinations',{}),ensure_ascii=False),'mapping':s['mapping']}.items() if k in next(iter(csv_docs[doc['id']]),{})})
        actual_flat=csv_docs.get(doc['id'],[])
        require(len(actual_flat)==len(expected_flat),'CSV row count differs')
        for a,b in zip(actual_flat,expected_flat):require(all(a.get(k,'')==b.get(k,'') for k in a),'CSV body/metadata differs: '+doc['id'])
    require(all_talks==set(talks),'Local dialogues omitted from organized/raw fallback pages')
    require(books=={r['BookID'] for r in tables['LocalbookConfig']},'Local books omitted')
    require(stories=={(r['AvatarID'],r['StoryID']) for r in tables['StoryAtlas']},'Character stories omitted')
    require(dict(categories)==catalog['stats']['categories'],'Category counts differ')
    require(matched==catalog['stats']['local_scene_id_order_matches'],'Scene evidence count differs')
    for filename,prefix,expected in [('목록.js','window.LIBRARY=',catalog),('본문검색.js','window.BODY_INDEX=',body_index)]:
        source=(out/filename).read_text(encoding='utf8');require(source.startswith(prefix) and source.endswith(';'),'Invalid search bundle');actual=json.loads(source[len(prefix):-1])
        if filename=='본문검색.js':actual=dict(actual)
        require(actual==expected,'Search index differs: '+filename)
    source=(out/'전체문자열검색.js').read_text(encoding='utf8');raw_index=json.loads(source[len('window.RAW_INDEX='):-1]);require(raw_index==[[str(r['hash']),readable(r['raw'])] for r in texts],'Raw search index differs or hash precision lost')
    data.verify_unchanged()
    result={'status':'PASS_WITH_LIMITATIONS','korean_texts':len(texts),'dialogues_preserved':len(all_talks),'book_chapters_preserved':len(books),'character_story_records_preserved':len(stories),'documents':len(doc_ids),'organized_rows':row_count,'local_scene_id_order_matches':matched,'auxiliary_structure_files_checked':len(structure_files),'original_game_files_unchanged':True,'raw_csv_exact':True,'all_local_dialogue_ids_represented':True,'rendered_exports_and_search_indexes_consistent':True,'limitations':report['limitations'],'elapsed_seconds':round(time.time()-started,2)}
    if args.zip:result['archive']=verify_zip(args.zip,out)
    dump(out/'검증/검증결과.json',result);print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
