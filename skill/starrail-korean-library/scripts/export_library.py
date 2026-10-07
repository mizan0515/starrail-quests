"""Extract local Korean HSR text, then build an offline reading library."""
import argparse, csv, hashlib, html, json, re, shutil, subprocess, sys, time
from pathlib import Path
from collections import Counter, defaultdict
from binary import LocalData, decode_table, decode_textmap, varint

SKILL=Path(__file__).resolve().parents[1]
TYPE_NAMES={1:'개척 임무',2:'모험 임무',3:'일일 임무',4:'시뮬레이션 우주',5:'도전 임무',6:'동행 임무',7:'개척 후문'}
CATEGORIES=['퀘스트','서적·문서','캐릭터 이야기','에이언즈·운명의 길','세계관·용어','광추 이야기','유물 이야기','아이템 설정','시뮬레이션 우주 설정','메시지','기타 장면','미귀속 대사']
TABLE_LORE=[('ItemConfigEquipment','광추 이야기'),('ItemConfigRelic','유물 이야기'),('ItemConfig','아이템 설정'),('ItemConfigBook','아이템 설정')]

def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf8')
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def readable(raw):
    text=raw.replace('\\n','\n').replace('\u00a0',' ')
    text=re.sub(r'\{RUBY_B#[^}]*\}|\{RUBY_E#[^}]*\}', '',text)
    text=re.sub(r'</?(?:color|size|b|i|u|align|voffset|indent|line-height|unbreak)(?:=[^>]*)?>','',text,flags=re.I)
    text=re.sub(r'<br\s*/?>','\n',text,flags=re.I)
    return text
def hash_of(value):return value.get('Hash',0) if isinstance(value,dict) else 0
def csv_write(path,fields,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def scenes_from_object(obj):
    """Keep source traversal order and branch destinations; do not linearize a playthrough."""
    result=[]
    def walk(x,pointer='',context='',option=False):
        if isinstance(x,dict):
            context=x.get('$type',context)
            option=option or 'OptionTalk' in context or 'Option' in pointer
            if isinstance(x.get('TalkSentenceID'),int):
                dest={k:v for k,v in x.items() if any(t in k.lower() for t in ('next','jump','target','optionid','trigger','finishkey','sequence','branch','condition','success','fail'))}
                result.append({'id':x['TalkSentenceID'],'kind':'선택지' if option else '대사','pointer':pointer,'task':context,'destinations':dest})
            for k,v in x.items():
                if k=='TalkSentenceIDList' and isinstance(v,list):
                    for i,talk in enumerate(v):
                        if isinstance(talk,int):result.append({'id':talk,'kind':'대사 참조','pointer':pointer+'/'+k+'/'+str(i),'task':context,'destinations':{}})
                elif isinstance(v,(dict,list)):walk(v,pointer+'/'+k,context,option)
        elif isinstance(x,list):
            for i,v in enumerate(x):walk(v,pointer+'/'+str(i),context,option)
    walk(obj)
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--game-data',required=True,type=Path);ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--structure',required=True,type=Path,help='Public or supplied JSON structure snapshot; no text-map fallback')
    ap.add_argument('--scene-checks',type=Path);ap.add_argument('--zip',type=Path)
    args=ap.parse_args(); out=args.output.resolve(); structure=args.structure.resolve()
    if out.exists() and any(p.is_file() for p in out.rglob('*')):raise SystemExit('Output must contain no files; existing results will not be replaced')
    if args.zip and args.zip.exists():raise SystemExit('ZIP already exists')
    if args.zip and args.zip.suffix.lower()!='.zip':raise SystemExit('ZIP path must end with .zip')
    if out==args.game_data.resolve() or args.game_data.resolve() in out.parents:raise SystemExit('Output must be outside game data')
    out.mkdir(parents=True,exist_ok=True)
    for sub in ('문서','TXT','JSON','원문','검증'): (out/sub).mkdir(exist_ok=True)
    data=LocalData(args.game_data);schemas=json.loads((SKILL/'assets/schemas-v4.json').read_text(encoding='utf8'))
    kr=[f for f in data.catalog if f['language']=='kr']
    if len(kr)!=1:raise ValueError('Expected exactly one full Korean DesignV pack')
    text_bytes,text_source=data.entry(kr[0]['entries'][0][0]);text_rows=decode_textmap(text_bytes)
    textmap={r['hash']:r for r in text_rows};tables={};table_sources={}
    for name,info in schemas.items():
        raw,source=data.entry(info['entry_hash']);tables[name]=decode_table(raw,info['schema']);table_sources[name]=source
    talks={r.get('TalkSentenceID',0):r for r in tables['TalkSentenceConfig']}
    if len(talks)!=len(tables['TalkSentenceConfig']):raise ValueError('Duplicate local dialogue IDs')
    dump(out/'원문/로컬표.json',{'tables':tables,'sources':table_sources})
    csv_write(out/'원문/전체한국어.csv',['hash','legacy','raw','has_params','offset','end'],text_rows)
    raw_talks=[]
    for r in talks.values():
        raw_talks.append({'id':r.get('TalkSentenceID',0),'voice':r.get('VoiceID',0),'speaker_hash':hash_of(r.get('TextmapTalkSentenceName')),'text_hash':hash_of(r.get('TalkSentenceText')),'speaker_raw':textmap.get(hash_of(r.get('TextmapTalkSentenceName')),{}).get('raw',''),'raw':textmap.get(hash_of(r.get('TalkSentenceText')),{}).get('raw',''),'offset':r['_offset'],'end':r['_end']})
    csv_write(out/'원문/전체대사.csv',['id','voice','speaker_hash','text_hash','speaker_raw','raw','offset','end'],raw_talks)
    missing=[];used_hashes=set();docs={};used_talks=set();source_manifest={}
    def textref(value,where):
        key=hash_of(value)
        if key==0:return '',None
        used_hashes.add(key)
        if key not in textmap:missing.append({'kind':'MISSING_TEXT_HASH','hash':str(key),'location':where});return f'[한국어 본문 누락: {key}]',None
        return readable(textmap[key]['raw']),key
    def line(value,label,where):
        text,key=textref(value,where)
        return {'label':label,'text':text,'hash':str(key) if key else '', 'source':where}
    def newdoc(key,title,category,world='',kind='',source=''):
        doc={'id':key,'title':title,'category':category,'world':world or '분류 미확인','kind':kind,'source':source,'sections':[],'notes':[]}
        docs[key]=doc;return doc
    def add_section(doc,title,rows,source='',mapping='LOCAL_TABLE',local_entry=None):
        if rows:doc['sections'].append({'title':title,'rows':rows,'source':source,'mapping':mapping,'local_entry':local_entry})
    worlds={r['ID']:textref(r.get('WorldName'),f'WorldDataConfig:{r["ID"]}')[0] for r in tables['WorldDataConfig']}
    missions={r['MainMissionID']:r for r in tables['MainMission']}
    for mid,r in missions.items():
        title,key=textref(r.get('Name'),f'MainMission:{mid}.Name')
        doc=newdoc('quest-'+str(mid),title or f'제목 미확인 임무 {mid}','퀘스트',worlds.get(r.get('WorldID',0),''),TYPE_NAMES.get(r.get('Type',0),'기타 임무'),'MainMission:'+str(mid))
        doc['title_hash']=str(key) if key else ''
        doc['notes'].append('장면은 정적 목록입니다. 장면 내부의 선택지·대사 참조를 보존하며, 모든 분기를 한 번에 플레이하는 순서로 해석하지 않습니다.')

    checks=json.loads(args.scene_checks.read_text()) if args.scene_checks else {}
    if checks:
        if 'checks' not in checks:raise ValueError('Use check_scenes.py evidence with source bindings')
        for path,evidence in checks['source_files'].items():
            path=Path(path).resolve()
            if not path.is_relative_to(data.root) or hashlib.sha256(data.read(path)).hexdigest()!=evidence['sha256']:raise ValueError('Scene evidence belongs to a different local source')
        checks=checks['checks']
    # Scene structure is auxiliary metadata. Every displayed dialogue and speaker comes from local tables.
    scene_count=0;verified_count=0;seen={};scene_diagnostics=[]
    for base in ('Story','Config/Level/Mission'):
        for p in sorted((structure/base).rglob('*.json')):
            rel=p.relative_to(structure).as_posix();obj=json.loads(p.read_text(encoding='utf8'));refs=scenes_from_object(obj)
            if not refs:continue
            source_manifest[rel]=sha(p)
            check=checks.get(rel,{})
            valid=[x for x in refs if x['id'] in talks];signature=tuple((x['id'],x['kind'],json.dumps(x['destinations'],sort_keys=True)) for x in refs)
            match=re.search(r'(?:Story/(?:Discussion/)?Mission|Config/Level/Mission)/(\d+)(?:/|\.)',rel)
            mid=int(match.group(1)) if match else 0
            if mid in missions:doc=docs['quest-'+str(mid)]
            else:
                parts=rel.split('/');group='/'.join(parts[:3]) if base=='Story' else '/'.join(parts[:4])
                key='scene-'+hashlib.sha1(group.encode()).hexdigest()[:12]
                doc=docs.get(key) or newdoc(key,'장면 모음 · '+group,'기타 장면',kind='임무 연결 미확인',source=group)
            dedup=(doc['id'],signature)
            if dedup in seen:
                seen[dedup].setdefault('aliases',[]).append(rel);continue
            rows=[]
            for ref in refs:
                tid=ref['id'];r=talks.get(tid)
                if r is None:
                    missing.append({'kind':'MISSING_LOCAL_TALK','id':tid,'location':rel+ref['pointer']})
                    rows.append({'label':'대사 누락','text':f'[로컬 대사 ID 없음: {tid}]','talk_id':tid,'pointer':ref['pointer'],'hash':'','destinations':ref['destinations']});continue
                text,key=textref(r.get('TalkSentenceText'),f'TalkSentenceConfig:{tid}.TalkSentenceText')
                speaker,sk=textref(r.get('TextmapTalkSentenceName'),f'TalkSentenceConfig:{tid}.TextmapTalkSentenceName')
                rows.append({'label':ref['kind'],'speaker':speaker or '화자 미지정','text':text,'talk_id':tid,'hash':str(key) if key else '', 'speaker_hash':str(sk) if sk else '', 'pointer':ref['pointer'],'destinations':ref['destinations']})
                used_talks.add(tid)
            if not valid:scene_diagnostics.append({'scene':rel,'status':'NO_LOCAL_DIALOGUE','references':len(refs)});continue
            mapping=check.get('status','UNVERIFIED_SCENE_MAPPING')
            if check.get('references')!=len(refs) or check.get('structure_sha256')!=source_manifest[rel]:mapping='UNVERIFIED_SCENE_MAPPING'
            if mapping=='LOCAL_ID_ORDER_MATCH':verified_count+=1
            scene_count+=1
            add_section(doc,p.stem,rows,rel,mapping,check.get('local_entry'));seen[dedup]=doc['sections'][-1]
            scene_diagnostics.append({'scene':rel,'status':mapping,'references':len(refs),'local_talks':len(valid),'local_entry':check.get('local_entry')})
    print('Scene structure linked',scene_count,'local ID order matched',verified_count,flush=True)

    book_world={r['BookSeriesWorld']:textref(r.get('BookSeriesWorldTextmapID'),f'BookSeriesWorld:{r["BookSeriesWorld"]}')[0] for r in tables['BookSeriesWorld']}
    series={r['BookSeriesID']:r for r in tables['BookSeriesConfig']}
    for bid,r in series.items():
        title,key=textref(r.get('BookSeries'),f'BookSeriesConfig:{bid}.BookSeries');desc,dh=textref(r.get('BookSeriesComments'),f'BookSeriesConfig:{bid}.BookSeriesComments')
        doc=newdoc('book-'+str(bid),title or f'서적 모음 {bid}','서적·문서',book_world.get(r.get('BookSeriesWorld',0),''),source='BookSeriesConfig:'+str(bid));doc['title_hash']=str(key) if key else ''
        if desc:add_section(doc,'자료 설명',[{'label':'설명','text':desc,'hash':str(dh) if dh else '', 'source':f'BookSeriesConfig:{bid}.BookSeriesComments'}])
    for r in sorted(tables['LocalbookConfig'],key=lambda x:(x.get('BookSeriesID',0),x.get('BookSeriesInsideID',0),x['BookID'])):
        sid=r.get('BookSeriesID',0);bid=r['BookID'];doc=docs.get('book-'+str(sid))
        if doc is None:doc=newdoc('book-'+str(sid),f'서적 모음 {sid}','서적·문서')
        title,th=textref(r.get('BookInsideName'),f'LocalbookConfig:{bid}.BookInsideName');body=line(r.get('BookContent'),'본문',f'LocalbookConfig:{bid}.BookContent');body['book_id']=bid;body['title_hash']=str(th) if th else ''
        add_section(doc,title or f'문서 {bid}',[body],f'LocalbookConfig:{bid}')
    # Avatar names are a supplemental ID -> local name-hash mapping; stories themselves are local StoryAtlas rows.
    avatar_names={}
    avatar_path=structure/'ExcelOutput/AvatarConfig.json'
    if avatar_path.exists():
        source_manifest['ExcelOutput/AvatarConfig.json']=sha(avatar_path)
        for r in json.loads(avatar_path.read_text(encoding='utf8')):avatar_names[r['AvatarID']]=textref(r.get('AvatarName'),f'AvatarConfig:{r["AvatarID"]}.AvatarName')[0]
    for r in tables['StoryAtlas']:
        aid=r['AvatarID'];sid=r['StoryID'];key='avatar-'+str(aid)
        doc=docs.get(key) or newdoc(key,avatar_names.get(aid) or f'캐릭터 {aid}','캐릭터 이야기',source='StoryAtlas:'+str(aid))
        row=line(r.get('Story'),'본문',f'StoryAtlas:{aid}:{sid}.Story');row['avatar_id']=aid;row['story_id']=sid
        add_section(doc,f'이야기 {sid}',[row],f'StoryAtlas:{aid}:{sid}')
    aeons={r['DisplayID']:r for r in tables['RogueAeonDisplay']}
    for r in tables['RogueAeonStoryConfig']:
        aid=r['RogueAeonID'];sid=r['AeonStoryID'];ar=aeons.get(aid,{})
        name,nh=textref(ar.get('RogueAeonName'),f'RogueAeonDisplay:{aid}.RogueAeonName')
        doc=docs.get('aeon-'+str(aid)) or newdoc('aeon-'+str(aid),name or f'에이언즈 {aid}','에이언즈·운명의 길',source='RogueAeonStoryConfig:'+str(aid))
        title,th=textref(r.get('AeonStory_Name'),f'RogueAeonStoryConfig:{aid}:{sid}.AeonStory_Name');row=line(r.get('AeonStory'),'본문',f'RogueAeonStoryConfig:{aid}:{sid}.AeonStory')
        add_section(doc,title or f'기록 {sid}',[row],f'RogueAeonStoryConfig:{aid}:{sid}')
    for r in tables['WorldDataConfig']:
        wid=r['ID'];title,key=textref(r.get('WorldName'),f'WorldDataConfig:{wid}.WorldName');doc=newdoc('world-'+str(wid),title or f'세계 {wid}','세계관·용어',title,source='WorldDataConfig:'+str(wid))
        add_section(doc,'세계 설명',[line(r.get('WorldDesc'),'설명',f'WorldDataConfig:{wid}.WorldDesc'),line(r.get('SimpleWorldDesc'),'짧은 설명',f'WorldDataConfig:{wid}.SimpleWorldDesc')])
    for r in tables['LoadingDesc']:
        rid=r['ID'];title,key=textref(r.get('TitleTextmapID'),f'LoadingDesc:{rid}.TitleTextmapID');doc=newdoc('lore-'+str(rid),title or f'세계관 기록 {rid}','세계관·용어',source='LoadingDesc:'+str(rid))
        add_section(doc,'기록',[line(r.get('DescTextmapID'),'본문',f'LoadingDesc:{rid}.DescTextmapID')])
    for table,cat in TABLE_LORE:
        for r in tables[table]:
            rid=r['ID'];title,th=textref(r.get('ItemName'),f'{table}:{rid}.ItemName');rows=[]
            for field,label in [('ItemDesc','설명'),('ItemBGDesc','배경 이야기')]:
                if r.get(field):rows.append(line(r[field],label,f'{table}:{rid}.{field}'))
            if not rows:continue
            doc=newdoc('item-'+table+'-'+str(rid),title or f'항목 {rid}',cat,source=table+':'+str(rid));add_section(doc,'설정 기록',rows)
    for r in tables['RogueMiracleDisplay']:
        rid=r['MiracleDisplayID'];title,th=textref(r.get('MiracleName'),f'RogueMiracleDisplay:{rid}.MiracleName');doc=newdoc('miracle-'+str(rid),title or f'기물 {rid}','시뮬레이션 우주 설정',source='RogueMiracleDisplay:'+str(rid));add_section(doc,'기물 배경',[line(r.get('MiracleBGDesc'),'본문',f'RogueMiracleDisplay:{rid}.MiracleBGDesc')])

    contacts={r['ID']:r for r in tables['MessageContactsConfig']};sections={r['ID']:r for r in tables['MessageSectionConfig']};items={r['ID']:r for r in tables['MessageItemConfig']};section_contacts={}
    for r in tables['MessageGroupConfig']:
        for section in r.get('MessageSectionIDList',[]):section_contacts[section]=r.get('MessageContactsID',0)
    message_groups=defaultdict(list)
    for r in items.values():message_groups[r.get('SectionID',0)].append(r)
    for sid,group in message_groups.items():
        cid=section_contacts.get(sid,0);name,nh=textref(contacts.get(cid,{}).get('Name'),f'MessageContactsConfig:{cid}.Name')
        doc=newdoc('message-'+str(sid),(name or '연락처 미확인')+f' · 메시지 {sid}','메시지',source='MessageSectionConfig:'+str(sid));doc['notes'].append('다음 메시지 ID와 선택지를 보존했습니다. 분기가 있는 메시지는 하나의 선형 대화가 아닙니다.')
        section=sections.get(sid,{});queue=list(section.get('StartMessageItemIDList',[]));visited=set();ordered=[]
        while queue:
            iid=queue.pop(0)
            if iid in visited or iid not in items or items[iid].get('SectionID',0)!=sid:continue
            visited.add(iid);r=items[iid];ordered.append(r);queue.extend(r.get('NextItemIDList',[]))
        ordered.extend(sorted((r for r in group if r['ID'] not in visited),key=lambda r:r['ID']));rows=[]
        for r in ordered:
            iid=r['ID'];actual_cid=r.get('ContactsID',cid) or cid
            speaker,sk=textref(contacts.get(actual_cid,{}).get('Name'),f'MessageContactsConfig:{actual_cid}.Name')
            speaker=speaker or f'연락처 {actual_cid}'
            if r.get('Sender') in (2,3):speaker='{NICKNAME}';sk=None
            elif r.get('Sender')==4:speaker='시스템';sk=None
            for field,label in [('MainText','메시지'),('OptionText','선택지')]:
                if not r.get(field):continue
                row=line(r[field],label,f'MessageItemConfig:{iid}.{field}');row.update(speaker=speaker,speaker_hash=str(sk) if sk else '',sender=r.get('Sender',0),message_id=iid,destinations={'NextItemIDList':r.get('NextItemIDList',[])})
                rows.append(row)
        add_section(doc,'대화',rows)

    remaining=sorted(set(talks)-used_talks)
    for chunk in range(0,len(remaining),500):
        part=remaining[chunk:chunk+500];doc=newdoc(f'unassigned-{chunk//500+1}',f'미귀속 대사 {part[0]}–{part[-1]}','미귀속 대사',source='TalkSentenceConfig')
        doc['notes'].append('임무·장면 연결을 확인하지 못한 원문입니다. 대사 ID순이며 이야기 진행 순서를 뜻하지 않습니다.')
        rows=[]
        for tid in part:
            r=talks[tid];body,h=textref(r.get('TalkSentenceText'),f'TalkSentenceConfig:{tid}.TalkSentenceText');name,nh=textref(r.get('TextmapTalkSentenceName'),f'TalkSentenceConfig:{tid}.TextmapTalkSentenceName')
            rows.append({'label':'대사','speaker':name or '화자 미지정','talk_id':tid,'text':body,'hash':str(h) if h else '', 'speaker_hash':str(nh) if nh else ''})
        add_section(doc,'원문 대사',rows)
    # Drop settings shells with no text, but retain every local mission in the catalog.
    docs={k:d for k,d in docs.items() if d['category']=='퀘스트' or any(r.get('text') or 'talk_id' in r for s in d['sections'] for r in s['rows'])}
    shutil.copyfile(SKILL/'assets/library.css',out/'library.css');shutil.copyfile(SKILL/'assets/library.js',out/'library.js');shutil.copyfile(SKILL/'assets/index.html',out/'시작.html')
    catalog=[];body_index=[];flat_rows=[]
    for doc in docs.values():
        key=doc['id'];all_rows=[r for s in doc['sections'] for r in s['rows']];count=len(all_rows);doc['count']=count
        doc['url']='문서/'+key+'.html';doc['txt']='TXT/'+key+'.txt';doc['json']='JSON/'+key+'.json'
        dump(out/doc['json'],doc);(out/doc['txt']).write_text(render_txt(doc),encoding='utf8');(out/doc['url']).write_text(render_html(doc),encoding='utf8')
        catalog.append({k:doc[k] for k in ('id','title','category','world','kind','count','url','txt','json')})
        body_index.append([key,'\n'.join([doc['title']]+[r.get('speaker','')+' '+r.get('text','') for r in all_rows])])
        for s in doc['sections']:
            for r in s['rows']:flat_rows.append({'doc_id':key,'category':doc['category'],'title':doc['title'],'section':s['title'],**r,'destinations':json.dumps(r.get('destinations',{}),ensure_ascii=False),'mapping':s['mapping']})
    catalog.sort(key=lambda x:(CATEGORIES.index(x['category']),x['world']=='분류 미확인',x['world'],x['title'].startswith(('제목 미확인','[한국어 본문 누락:')),x['kind'],x['id']))
    csv_write(out/'정리본문.csv',['doc_id','category','title','section','label','speaker','text','talk_id','hash','speaker_hash','source','pointer','destinations','mapping'],flat_rows)
    counts=Counter(d['category'] for d in docs.values());missions_with_body=sum(bool(d['count']) for d in docs.values() if d['category']=='퀘스트')
    stats={'korean_texts':len(text_rows),'local_dialogues':len(talks),'dialogues_with_korean':sum(bool(r['raw']) for r in raw_talks),'local_missions':len(missions),'missions_with_linked_body':missions_with_body,'local_books':len(tables['LocalbookConfig']),'local_character_story_records':len(tables['StoryAtlas']),'scene_sections':scene_count,'local_scene_id_order_matches':verified_count,'unassigned_dialogues':len(remaining),'documents':len(docs),'categories':dict(counts),'missing_text_refs':len(missing)}
    dump(out/'목록.json',{'stats':stats,'documents':catalog})
    (out/'목록.js').write_text('window.LIBRARY='+json.dumps({'stats':stats,'documents':catalog},ensure_ascii=False,separators=(',',':'))+';',encoding='utf8')
    (out/'본문검색.js').write_text('window.BODY_INDEX='+json.dumps(body_index,ensure_ascii=False,separators=(',',':'))+';',encoding='utf8')
    (out/'전체문자열검색.js').write_text('window.RAW_INDEX='+json.dumps([[str(r['hash']),readable(r['raw'])] for r in text_rows],ensure_ascii=False,separators=(',',':'))+';',encoding='utf8')
    csv_write(out/'검증/누락.csv',['kind','id','hash','location'],missing);dump(out/'검증/장면연결.json',scene_diagnostics)
    ref_commit='UNVERIFIED'
    if (structure/'.git').exists():
        try:ref_commit=subprocess.check_output(['git','-C',str(structure),'rev-parse','HEAD'],text=True).strip()
        except (OSError,subprocess.CalledProcessError):pass
    report={'status':'EXTRACTED_STATIC_LIBRARY','stats':stats,'source_root':str(data.root),'local_design_version':data.version,'source_files':data.evidence,'text_source':text_source,'table_sources':table_sources,'schemas_sha256':sha(SKILL/'assets/schemas-v4.json'),'schema_version':'observed-4.5-v4','structure_root':str(structure),'structure_commit':ref_commit,'structure_file_sha256':source_manifest,'structure_provenance':'Public scene/branch structure supplements local tables. No public text map is used. ID-order matches are checks of references, not decoded local control flow.','limitations':['공개 구조 보조에 따른 장면 연결과 실제 플레이 조건·실행 순서는 별도 검증되지 않았습니다.','임무 제목이 없는 설정·내부 자료·미번역 항목이 포함될 수 있습니다.','연결하지 못한 모든 대사와 전체 한국어 문자열은 원문 파일에 보존했습니다.','컷신 영상 안의 별도 자막·음성은 이 추출 범위에서 복원하지 않았습니다.'],'design_guide_status':'UNVERIFIED_DESIGN_GUIDE_MISSING'}
    data.verify_unchanged();report['source_unchanged']=True;dump(out/'검증/추출보고서.json',report)
    (out/'자료안내.html').write_text(render_about(report),encoding='utf8')
    # Raw hashes remain strings in browser data to avoid IEEE-754 integer truncation.
    print(json.dumps(stats,ensure_ascii=False,indent=2),flush=True)
    if args.zip:
        archive=shutil.make_archive(str(args.zip.with_suffix('')),'zip',root_dir=out)
        if Path(archive).resolve()!=args.zip.resolve():raise ValueError('ZIP path must end with .zip')
        print('ZIP',archive,flush=True)

def render_txt(doc):
    parts=[doc['title'],f'분류: {doc["category"]} / {doc["world"]}',f'자료 ID: {doc["id"]}',*doc['notes'],'']
    for s in doc['sections']:
        parts+=['## '+s['title'],'연결: '+s['mapping'],'출처: '+s['source'],'']
        for r in s['rows']:
            speaker=r.get('speaker','');parts.append(f'[{r["label"]}]'+(' '+speaker if speaker else '')+(f' · ID {r["talk_id"]}' if 'talk_id' in r else ''))
            parts.append(r.get('text',''))
            if r.get('destinations'):parts.append('이동/분기: '+json.dumps(r['destinations'],ensure_ascii=False))
            parts.append('')
    return '\n'.join(parts)

def render_html(doc):
    esc=html.escape;parts=[]
    for i,s in enumerate(doc['sections']):
        parts.append(f'<section id="s{i}"><h2>{esc(s["title"])}</h2>')
        for ri,r in enumerate(s['rows']):
            css='option' if r['label']=='선택지' else 'line'
            anchor='talk-'+str(r.get('talk_id',r.get('message_id',i)))+'-'+str(i)+'-'+str(ri)
            speaker=r.get('speaker') or r['label']
            if r['label']=='선택지':speaker='선택지 · '+speaker
            parts.append(f'<article class="{css}" id="{anchor}"><div class="speaker">{esc(speaker)}</div><p>{esc(r.get("text",""))}</p>')
            if r.get('destinations'):parts.append('<details><summary>선택지 연결 보기</summary><pre>'+esc(json.dumps(r['destinations'],ensure_ascii=False,indent=2))+'</pre></details>')
            parts.append('<details class="evidence"><summary>원문 근거</summary><p>텍스트 해시: '+esc(r.get('hash',''))+'</p><p>대사 ID: '+str(r.get('talk_id',''))+'</p><p>'+esc(r.get('source','') or s['source'])+esc(r.get('pointer',''))+'</p></details></article>')
        parts.append('<details class="evidence"><summary>장면 출처·연결 검증</summary><p>'+esc(s['source'])+'</p><p>'+esc(s['mapping'])+'</p><p>'+esc(', '.join(s.get('aliases',[])))+'</p></details></section>')
    toc=''.join(f'<a href="#s{i}">{esc(s["title"])}</a>' for i,s in enumerate(doc['sections']))
    if not parts:parts=['<div class="notice">이 임무의 제목·설정은 확인했지만 대사 장면은 연결하지 못했습니다. 전체 원문 검색에서도 찾아볼 수 있습니다.</div>']
    return f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(doc['title'])} | 스타레일 자료집</title><link rel="stylesheet" href="../library.css"><body><a class="skip" href="#content">본문으로 이동</a><header><a href="../시작.html">✦ 스타레일 한국어 자료집</a><a href="../자료안내.html">자료 안내</a><button id="theme" type="button">테마 전환</button></header><div class="reader-layout"><aside><a href="../시작.html">← 목록으로</a><p>{esc(doc['category'])}</p><nav aria-label="문서 목차">{toc}</nav></aside><main id="content"><div class="eyebrow">HONKAI: STAR RAIL / 한국어 원문</div><h1>{esc(doc['title'])}</h1><div class="meta">{esc(doc['world'])} · {esc(doc['kind'])} · {doc['count']:,}개 본문 항목</div><div class="downloads"><a href="../{doc['txt']}" download>TXT 저장</a><a href="../{doc['json']}" download>JSON 저장</a></div>{''.join('<p class="notice">'+esc(n)+'</p>' for n in doc['notes'])}{''.join(parts)}<footer>비공식 로컬 자료집 · 게임 콘텐츠의 권리는 해당 권리자에게 있습니다.</footer></main></div><script>document.getElementById('theme').onclick=()=>{{document.documentElement.classList.toggle('light');localStorage.setItem('hsr-theme',document.documentElement.className)}};document.documentElement.className=localStorage.getItem('hsr-theme')||'';</script></body></html>'''

def render_about(report):
    stats=report['stats'];e=html.escape
    content='<h1>자료 안내</h1><p>지정된 로컬 클라이언트에서 한국어 원문과 관계 표를 읽어 만든 정적 자료집입니다. AI가 본문을 번역하거나 요약하지 않았습니다.</p>'
    content+='<h2>수록 범위</h2><ul>'+''.join('<li>'+e(k)+': '+str(v)+'</li>' for k,v in stats.items() if isinstance(v,int))+'</ul>'
    content+='<h2>출처와 연결 방법</h2><p>대사·화자·임무 제목·서적·설정 본문은 로컬 DesignData에서 추출했습니다. 공개 <a href="https://github.com/DimbreathBot/TurnBasedGameData">TurnBasedGameData (Dimbreath)</a>의 필드 정의와 장면·분기 구조는 보조 자료입니다. 공개 한국어 TextMap은 사용하지 않았습니다.</p><p>보조 구조 커밋: '+e(report['structure_commit'])+'</p><p>장면의 LOCAL_ID_ORDER_MATCH 표시는 로컬 바이너리에 대사 ID가 같은 상대 순서로 나타난다는 뜻입니다. 로컬 실행 조건이나 전체 제어 흐름의 복호화 성공을 뜻하지 않습니다. 나머지 장면 연결은 UNVERIFIED로 보존했습니다.</p>'
    content+='<h2>한계와 누락</h2><ul>'+''.join('<li>'+e(x)+'</li>' for x in report['limitations'])+'</ul><p>미귀속 대사를 임의의 임무에 붙이지 않았습니다. 원문 CSV에는 게임의 태그·공백·변수가 그대로 남습니다. 읽기 화면에서는 줄바꿈·비분리 공백·일부 서식 태그만 정리합니다.</p><p><a href="검증/추출보고서.json">추출·원본 해시 보고서</a> · <a href="검증/누락.csv">누락 참조</a> · <a href="검증/장면연결.json">장면 연결 근거</a> · <a href="원문/전체한국어.csv">전체 한국어 원문</a> · <a href="원문/전체대사.csv">전체 대사 원문</a> · <a href="정리본문.csv">정리 본문 CSV</a></p><p>사용자 참고 사이트: <a href="https://mizan0515.github.io/wuwa-quests/index.html">명조 퀘스트 자료집</a>. 제목·유형 목록에서 장면을 읽는 흐름을 참고했으며 사이트 코드는 복사하지 않았습니다.</p>'
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>자료 안내 | 스타레일 자료집</title><link rel="stylesheet" href="library.css"><body><header><a href="시작.html">✦ 스타레일 한국어 자료집</a></header><main class="about">'+content+'</main></body></html>'

if __name__=='__main__':main()

