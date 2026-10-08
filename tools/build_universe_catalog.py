"""Project reviewed universe records into a source-preserving discovery catalogue.

The reviewed dialogue intervals select source-table rows, not gameplay order.
Keyword occurrences are kept in relatedRecords and never become relationship edges.
"""
import argparse, hashlib, json, sys
from pathlib import Path
from export_dialogue_browser import clean

SITE = Path(__file__).resolve().parents[1]
MODES = [
    ('simulation', '시뮬레이션 우주', '에이언즈를 연구하는 사고 실험과 개발자들의 설명을 읽는다.', ['quest-4030001','quest-4030002','quest-4030003','quest-4030004','quest-4030007','avatar-1303'], [], ['시뮬레이션 우주']),
    ('swarm-disaster', '곤충 떼 재난', '헤르타는 타이츠론스가 몰락하기 전 시대에 시간을 고정해 에이언즈를 연구한다고 설명한다.', ['quest-8013104','quest-8013101','quest-8013102','quest-8013105','quest-8013106','quest-8013107','quest-8013110','lore-10144','miracle-183'], [], ['곤충 떼','타이츠론스']),
    ('gold-and-gears', '황금과 기계', '루버트의 사망 전 시기를 연산하는 연구와 컴퍼니의 방문을 함께 읽는다.', ['quest-8016101','quest-8016102','quest-8016103','quest-8016104','quest-8016105','quest-8016106','miracle-64','miracle-123','miracle-52'], [], ['루버트','제왕 전쟁']),
    ('unknowable-domain', '인지 불가 영역', '학파 전쟁, 셉터의 계산력 분배, 파티비아의 난제와 헤르타의 관측을 함께 읽는다.', ['quest-8026401','miracle-64','miracle-108','miracle-109','miracle-123','book-57'], [
        ('knowledge-circle','헤르타가 설명하는 파티비아와 지식의 원',403058381,403058413),
        ('scepter-allocation','미래학 총회와 셉터의 분배',403058441,403058573),
        ('school-war','학파의 실험과 전쟁',403058591,403058918),
        ('partavia','셉터의 코어와 파티비아의 난제',403058941,403059128),
        ('observation','헤르타의 관측과 폴카의 개입',403059151,403059462)
    ], ['인지 불가 영역','셉터','파티비아']),
    ('divergent-universe', '차분화 우주', '스크루룸은 시뮬레이션 우주의 기본 논리와 스크루별의 기술로 만든 독립 연구라고 설명한다.', ['quest-8023401'], [], ['차분화 우주']),
    ('virtue', '덕성의 찬가', '칼리도르토스가 설명하는 나무 정원의 지식과 기억 속 사고 실험을 읽는다.', ['quest-8031301','quest-8031302'], [('garden','나무 정원의 지식과 덕성',803130051,803130162)], ['덕성의 찬가']),
    ('ahas-game', '아하의 게임', '펄의 개인 협력과 원력·환락을 변수로 삼은 신규 과제를 스크루룸의 설명으로 읽는다.', ['quest-8041500'], [('pearl','펄의 협력과 신규 과제',845000101,845000211)], ['아하의 게임'])
]

def read(p): return json.loads(p.read_text(encoding='utf8'))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':')),encoding='utf8',newline='\n')

def build(verify_game=None, skill=None):
    catalogue=read(SITE/'data/catalog.json')
    documents={d['id']:read(SITE/'data/documents'/(d['id']+'.json')) for d in catalogue}
    dialogue={}
    for p in (SITE/'data/dialogues').glob('*.json'):
        for row in read(p)['section']['rows']:
            assert row['talk_id'] not in dialogue
            dialogue[row['talk_id']]={**row,'pageId':p.stem,'anchor':'talk-'+str(row['talk_id']), 'url':'대사/'+p.stem+'.html#talk-'+str(row['talk_id'])}
    preserved=read(SITE/'data/dialogue-index.json')['evidence']
    evidence={'method':'reviewed-document-ids-and-dialogue-rows.v1','catalogueSha256':digest(SITE/'data/catalog.json'), 'dialogueIndexSha256':digest(SITE/'data/dialogue-index.json'), 'preservedSnapshot':{'dialogueTable':preserved['dialogueTable'],'textMap':preserved['textMap'],'sources':preserved['sources']},'localVerification':None}
    intro_talks={'simulation':403010206,'swarm-disaster':403055011,'gold-and-gears':403060005,'unknowable-domain':826410111,'divergent-universe':802341007,'virtue':803130107,'ahas-game':845000107}
    def proof(tid):
        for d in documents.values():
            for sec in d['sections']:
                for row in sec['rows']:
                    if row.get('talk_id')==tid:
                        return {'id':d['id'],'title':d['title'],'anchor':sec['anchor'],'quote':row['text'],'hash':row['hash'],'speaker':row.get('speaker',''),'status':row.get('speaker','')+'의 설명','url':d['url']+'#'+sec['anchor']}
        row=dialogue[tid]
        return {'id':'dialogue-'+row['pageId'],'title':'한국어 대사 원문','anchor':row['anchor'],'quote':row['text'],'hash':row['hash'],'speaker':row['speaker'],'status':row['speaker']+'의 설명','url':row['url']}
    def record(d, role='원문'):
        source=next(((s,r) for s in d['sections'] for r in s['rows'] if r.get('text')),None)
        sec,row=source if source else ({'anchor':''},{'text':''})
        return {'id':d['id'],'title':d['title'],'category':d['category'],'url':d['url'], 'anchor':sec['anchor'],'role':role,'excerpt':row['text'][:250], 'count':d['count'],'sha256':digest(SITE/'data/documents'/(d['id']+'.json'))}
    modes=[]
    for mid,name,intro,ids,groups,terms in MODES:
        refs=[record(documents[id],'검토한 핵심 원문') for id in ids if id in documents and documents[id]['sections']]
        missing=[id for id in ids if id not in documents]
        if missing: raise ValueError('Reviewed document missing: '+str(missing))
        output_groups=[]
        for gid,title,lo,hi in groups:
            rows=[r for tid,r in dialogue.items() if lo<=tid<=hi]
            # Source order is preserved, including mutually exclusive responses.
            rows.sort(key=lambda r:r['offset'])
            if not rows: raise ValueError('Empty reviewed dialogue group: '+gid)
            output_groups.append({'id':gid,'title':title,'role':'검토한 대사 원문','status':'편집 독서 묶음 · 대사 표 행 순서','url':rows[0]['url'],'rows':rows,'count':len(rows),'chronology':'선택지와 응답을 함께 보존한 대사 표의 행 순서'})
        related=[]
        for d in documents.values():
            if d['id'] in ids: continue
            hits=[]
            for s in d['sections']:
                for r in s['rows']:
                    if any(t in r['text'] or t in d['title'] for t in terms):
                        hits.append({'anchor':s['anchor'],'hash':r.get('hash',''),'quote':r['text'][:350]})
            if hits: related.append({**record(d,'용어가 등장하는 원문'),'matches':hits[:3],'status':'원문 검색 결과'})
        modes.append({'id':mid,'name':name,'intro':intro,'introEvidence':proof(intro_talks[mid]),'documents':refs,'dialogueGroups':output_groups,'relatedRecords':related,'terms':terms})
    collections=[]
    for cid,name,category,intro in [
        ('curios','기물의 배경 이야기','시뮬레이션 우주 설정','기물의 이름과 배경에 남은 사건·인물·문명의 기록을 읽는다.'),
        ('items','아이템 설명','아이템 설정','용도 설명과 배경 기록, 아이템에 인용된 발언을 함께 읽는다.'),
        ('relics','유물 이야기','유물 이야기','세트와 개별 유물에 기록된 인물·문명의 이야기를 읽는다.'),
        ('light-cones','광추 이야기','광추 이야기','광추에 담긴 장면과 대화를 읽는다.')]:
        refs=[{**record(d),'searchText':'\n'.join([d['title']]+[r['text'] for s in d['sections'] for r in s['rows']])} for d in documents.values() if d['category']==category]
        collections.append({'id':cid,'name':name,'intro':intro,'documents':refs,'count':len(refs)})
    if verify_game:
        sys.path.insert(0,str(skill/'scripts'))
        from binary import LocalData,decode_table,decode_textmap
        local=LocalData(verify_game);spec=read(skill/'assets/schemas-v4.json')
        table,ts=local.entry(spec['TalkSentenceConfig']['entry_hash'])
        talks={r['TalkSentenceID']:r for r in decode_table(table,spec['TalkSentenceConfig']['schema'])}
        kr=next(f for f in local.catalog if f['language']=='kr');raw,ks=local.entry(kr['entries'][0][0])
        texts={str(r['hash']):clean(r['raw']) for r in decode_textmap(raw)}
        selected={r['talk_id']:r for m in modes for g in m['dialogueGroups'] for r in g['rows']}
        for tid,r in selected.items():
            original=talks[tid]
            assert str(original['TalkSentenceText']['Hash'])==r['hash'] and texts[r['hash']]==r['text'],tid
            assert r['speaker']==(texts.get(r['speaker_hash'],'') or '화자 미지정'),tid
            assert original['_offset']==r['offset'] and original['_end']==r['end'],tid
        # Curio and item references are also compared to current local Korean rows.
        for collection in collections:
            for ref in collection['documents']:
                for sec in documents[ref['id']]['sections']:
                    for r in sec['rows']:
                        if r.get('hash') and r['hash'] in texts:
                            assert texts[r['hash']]==r['text'],(ref['id'],r['hash'])
        local.verify_unchanged()
        evidence['localVerification']={'method':'current-local-TalkSentenceConfig-and-Korean-TextMap','verifiedDialogueRows':len(selected),'table':{**ts,'file':Path(ts['file']).name},'textMap':{**ks,'file':Path(ks['file']).name},'files':[{**e,'file':Path(p).name} for p,e in local.evidence.items()]}
    result={'schema':'starrail-universe-catalog.v1','modes':modes,'itemCollections':collections,'counts':{'modes':len(modes),'coreDocuments':len({d['id'] for m in modes for d in m['documents']}),'reviewedDialogueRows':len({r['talk_id'] for m in modes for g in m['dialogueGroups'] for r in g['rows']}),'itemRecords':sum(c['count'] for c in collections)},'evidence':evidence}
    source_records_path=SITE/'data/universe-source-records.json'
    if source_records_path.exists():
        source_records=read(source_records_path)
        assert source_records['schemaVersion']=='starrail-universe-source-records.v1'
        by_mode={m['id']:m['records'] for m in source_records['modes']}
        for mode in modes:mode['sourceRecordIds']=[r['id'] for r in by_mode.get(mode['id'],[])]
        result['sourceRecords']={'url':'universe-source-records.json','sha256':digest(source_records_path),'counts':source_records['counts']}
    write(SITE/'data/universe-catalog.json',result);write(SITE/'public/universe-catalog.json',result)
    print(json.dumps(result['counts'],ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--game-data',type=Path);p.add_argument('--skill',type=Path);a=p.parse_args()
    if bool(a.game_data)!=bool(a.skill):p.error('--game-data and --skill must be provided together')
    build(a.game_data,a.skill)
