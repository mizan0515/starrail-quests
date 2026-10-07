"""Project a preserved local extraction into a contextual, portable reading site."""
import argparse,csv,json,re,hashlib
from pathlib import Path
from collections import defaultdict

def read(p):return json.loads(p.read_text('utf8'))
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,separators=(',',':')),encoding='utf8')
def clean(s):
    s=s.replace('\u00a0',' ').replace('\\n','\n');s=re.sub(r'</?(?:color|size|b|i|u|s|align|voffset|indent|line-height|unbreak)(?:=[^>]*)?>','',s,flags=re.I)
    s=re.sub(r'\{RUBY_[BE]#[^}]*\}','',s)
    return s
def visible(s):
    s=clean(s)
    return re.sub(r'\[한국어 본문 누락: [^]]+\]','한국어 본문 미수록',s)
def topological(ids,edges,rank):
    ids=set(ids);out=[];indeg={i:0 for i in ids};adj=defaultdict(set)
    for a,b in edges:
        if a in ids and b in ids and a!=b and b not in adj[a]:adj[a].add(b);indeg[b]+=1
    ready=sorted((i for i in ids if not indeg[i]),key=lambda i:rank[i])
    while ready:
        a=ready.pop(0);out.append(a)
        for b in adj[a]:
            indeg[b]-=1
            if not indeg[b]:ready.append(b)
        ready.sort(key=lambda i:rank[i])
    return out+sorted(ids-set(out),key=lambda i:rank[i]),len(out)==len(ids)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',required=True,type=Path);ap.add_argument('--structure',required=True,type=Path);ap.add_argument('--extended',required=True,type=Path);args=ap.parse_args();site=Path(__file__).resolve().parents[1]
    old=read(args.library/'목록.json');tables=read(args.library/'원문/로컬표.json')['tables'];ext=read(args.extended)['tables']
    textmap={r['hash']:clean(r['raw']) for r in csv.DictReader((args.library/'원문/전체한국어.csv').open(encoding='utf-8-sig'))}
    def text(v):return textmap.get(str(v.get('Hash',0)),'') if isinstance(v,dict) else ''
    chapters={};public_chapters={r['ID']:r for r in read(args.structure/'ExcelOutput/MissionChapterConfig.json')}
    for r in ext['MissionChapterConfig']['rows']:
        ref=public_chapters.get(r['ID'],{});c={}
        for k in ['ChapterName','StageName','ChapterDesc']:
            raw=r.get(k,'')
            if raw and raw!=f'MissionChapterConfig_{k}_{r["ID"]}':raise ValueError('Unknown local chapter localization key')
            c[k]=text(ref.get(k)) if raw else ''
        c['priority']=r.get('ChapterDisplayPriority',999999);chapters[r['ID']]=c
    subs={r['SubMissionID']:r for r in ext['SubMission']['rows']};missions={r['MainMissionID']:r for r in tables['MainMission']}
    sequence,acyclic=topological(missions,[(i,r.get('NextTrackMainMission',0)) for i,r in missions.items()]+[(i,j) for i,r in missions.items() for j in r.get('NextMainMissionList',[])],{i:(chapters.get(r.get('ChapterID'),{}).get('priority',999999),r.get('DisplayPriority',i),i) for i,r in missions.items()});mission_rank={i:n for n,i in enumerate(sequence)}
    relics={r['ID']:r for r in ext['RelicConfig']['rows']};relic_sets={r['SetID']:r for r in read(args.structure/'ExcelOutput/RelicSetConfig.json')}
    docs=[];all_docs={};aliases={};dupes={};missing_rows=0
    for entry in old['documents']:
        d=read(args.library/'JSON'/(entry['id']+'.json'));d['title']=visible(d['title']);d['sections']=[{**s,'rows':[{**r,'text':visible(r.get('text','')),'speaker':visible(r.get('speaker',''))} for r in s['rows']]} for s in d['sections']]
        for s in d['sections']:
            for r in s['rows']:
                if '한국어 본문 미수록' in r['text']:missing_rows+=1
        if d['category']=='미귀속 대사':continue
        if re.match(r'^(?:제목 미확인 임무|캐릭터 \d+|\[한국어 본문 누락)',d['title']):continue
        if not d['sections'] and d['category']!='퀘스트':continue
        d['count']=sum(len(s['rows']) for s in d['sections']);d['topics']=[];d['stages']=[];d['aliases']=[]
        if d['category']=='퀘스트':
            mid=int(d['id'].split('-')[-1]);m=missions[mid];ch=chapters.get(m.get('ChapterID'),{})
            d['chapter']=ch.get('ChapterName') or ch.get('StageName') or '챕터 미지정';d['chapterDescription']=ch.get('ChapterDesc','');d['chapterRank']=ch.get('priority',999999);d['rank']=mission_rank[mid];d['next']=m.get('NextTrackMainMission',0)
            p=args.structure/'Config/Level/Mission'/str(mid)/f'MissionInfo_{mid}.partial.json'
            stages=read(p).get('SubMissionList',[]) if p.exists() else [];lookup={r['ID']:r for r in stages};edges=[]
            for r in stages:
                if r.get('TakeType') in ('Sequence','AnySequence','MultiSequence'):
                    edges.extend((i,r['ID']) for i in r.get('TakeParamIntList',[]) if i in lookup)
            order,ok=topological(lookup,edges,{r['ID']:(int('(선택)' in text(subs.get(r['ID'],{}).get('TargetText'))),n) for n,r in enumerate(stages)})
            for sid in order:
                sub=subs.get(sid,{});title=text(sub.get('TargetText'));description=text(sub.get('DescrptionText'))
                if not title:continue
                d['stages'].append({'id':sid,'title':title,'description':description,'optional':'(선택)' in title,'predecessors':[a for a,b in edges if b==sid],'hash':str(sub.get('TargetText',{}).get('Hash','')),'description_hash':str(sub.get('DescrptionText',{}).get('Hash','')),'key':lookup[sid].get('ParamStr1','')})
            d['stageGraphAcyclic']=ok;positions={sid:i for i,sid in enumerate(order)}
            for n,s in enumerate(d['sections']):
                s['sourceTitle']=s['title'];s['anchor']='scene-'+str(n+1);s['stage']=None
                keys=[s['title']]+s.get('aliases',[])
                keys+= [r.get('destinations',{}).get('FinishKey','') for r in s['rows']]
                candidates=[sid for sid,r in lookup.items() if r.get('ParamStr1') and r['ParamStr1'] in keys]
                if len(candidates)==1:s['stage']=candidates[0]
                primary=next((r for r in s['rows'] if r['text'] and '미수록' not in r['text']),None)
                if primary:
                    fragment=re.sub(r'\s+',' ',primary['text']).strip();fragment=fragment[:37]+('…' if len(fragment)>37 else '')
                    speaker=primary.get('speaker','')
                    s['title']=('선택 · ' if primary.get('label')=='선택지' else (speaker+' · ' if speaker and speaker!='화자 미지정' else '대화 · '))+fragment
                else:s['title']='한국어 본문이 연결되지 않은 장면'
            d['sections'].sort(key=lambda s:(positions.get(s['stage'],len(order)),int(s['anchor'].split('-')[-1])))
            # Deliberate editorial arrangement for the reviewed canary; stage associations are labelled interpretation.
            if mid==2022303:
                editorial={'DS202230304':(202230304,'운기군에게 배치와 보리인 식별법 묻기'),'DS202230302':(202230308,'Mar. 7th에게 도움을 약속하기'),'Story202230305':(202230305,'엔진실에서 다시 만난 상대에게 질문하기'),'Story202230312':(202230312,'습격 대응 중 자신의 정체를 확인하는 선택')}
                for s in d['sections']:
                    if s['sourceTitle'] in editorial:s['stage'],s['title']=editorial[s['sourceTitle']];s['editorialPlacement']=True
                d['sections'].sort(key=lambda s:(positions.get(s['stage'],len(order)),int(s['anchor'].split('-')[-1])))
        else:
            d['rank']=0;d['chapter']=''
            for n,s in enumerate(d['sections']):s['anchor']='section-'+str(n+1)
            if d['category']=='기타 장면':
                names=list(dict.fromkeys(r.get('speaker','') for s in d['sections'] for r in s['rows'] if r.get('speaker') and r.get('speaker')!='화자 미지정'))
                d['title']=('임무 외 대화 · '+', '.join(names[:3])) if names else '임무 외 대화 기록'
                for n,s in enumerate(d['sections']):
                    s['sourceTitle']=s['title'];first=next((r['text'] for r in s['rows'] if r['text'] and '미수록' not in r['text']),'대화 기록');s['title']=re.sub(r'\s+',' ',first)[:45]
        if d['category']=='유물 이야기':
            rid=int(d['id'].split('-')[-1]);r=relics.get(rid,{});sid=r.get('SetID');ref=relic_sets.get(sid,{})
            d['collection']=text(ref.get('SetName')) or ('유물 세트 '+str(sid) if sid else '기타 유물');d['collection_id']=sid
        if d['category'] in ['유물 이야기','아이템 설정']:
            signature=(d['category'],d['title'],tuple(r['text'] for s in d['sections'] for r in s['rows']))
            if signature in dupes:aliases[d['id']]=dupes[signature];all_docs[dupes[signature]]['aliases'].append(d['id']);continue
            dupes[signature]=d['id']
        docs.append(d);all_docs[d['id']]=d
    # Match titles/kinds/worlds/chapters only inside a locally observed mission pack.
    # The pack array gives the part order; no title-only merge of unrelated quests.
    merged_parts=0
    for pack in ext['MainMissionPack']['rows']:
        compatible=defaultdict(list)
        for mid in pack['MainMissionIdList']:
            d=all_docs.get('quest-'+str(mid))
            if d:compatible[(d['title'],d.get('kind'),d.get('world'),d.get('chapter'))].append(d)
        for parts in compatible.values():
            if len(parts)<2:continue
            primary=parts[0];primary['missionParts']=[p['id'] for p in parts]
            primary['sections']=[{**s,'anchor':p['id']+'-'+s['anchor']} for p in parts for s in p['sections']]
            primary['stages']=[s for p in parts for s in p['stages']]
            primary['count']=sum(p['count'] for p in parts);primary['next']=parts[-1].get('next',0)
            for p in parts[1:]:
                aliases[p['id']]=primary['id'];primary['aliases'].append(p['id']);all_docs.pop(p['id']);docs.remove(p);merged_parts+=1
    for d in docs:
        if d['category']=='퀘스트' and d.get('next'):
            resolved=aliases.get('quest-'+str(d['next']),'quest-'+str(d['next']))
            d['next']=int(resolved.split('-')[-1]) if resolved!=d['id'] else 0
    # Keep progression references within the same chapter; cross-chapter tracking
    # suggestions must not interleave worlds or split a chapter's reading group.
    groups=defaultdict(list)
    for d in docs:
        if d['category']=='퀘스트':groups[(d['kind'],d['world'],d['chapter'])].append(d)
    world_priority={}
    for d in docs:
        if d['category']=='퀘스트' and d['kind']=='개척 임무':world_priority[d['world']]=min(world_priority.get(d['world'],999999),d['chapterRank'])
    for group in groups.values():
        byid={int(d['id'][6:]):d for d in group}
        edges=[(mid,d['next']) for mid,d in byid.items() if d.get('next')]
        local_order,_=topological(byid,edges,{mid:(missions[mid].get('DisplayPriority',mid),mid) for mid in byid})
        for rank,mid in enumerate(local_order):byid[mid]['rank']=rank;byid[mid]['worldRank']=world_priority.get(byid[mid]['world'],999999)
    topics=read(site/'editorial/topics.json');fail=[]
    for topic in topics:
        explicit=set()
        for s in topic['sections']:
            for ev in s['evidence']:
                if ev['id'] not in all_docs:fail.append((topic['id'],ev,'document missing'));continue
                d=all_docs[ev['id']];found=[(sec,row) for sec in d['sections'] for row in sec['rows'] if ev['needle'] in row['text']]
                if not found:fail.append((topic['id'],ev,'quotation not found'));continue
                sec,row=found[0];ev['anchor']=sec['anchor'];ev['title']=d['title'];ev['hash']=row.get('hash','');pos=row['text'].find(ev['needle']);ev['quote']=row['text'][max(0,pos-35):min(len(row['text']),pos+len(ev['needle'])+85)].strip();explicit.add(d['id'])
        for r in topic['reading']:
            if r['id'] in all_docs:r['title']=all_docs[r['id']]['title'];explicit.add(r['id'])
            else:fail.append((topic['id'],r,'reading document missing'))
        topic['sources']=sorted(explicit)
        for d in docs:
            if d['id'] in explicit:d['topics'].append({'id':topic['id'],'title':topic['title'],'reason':'해설의 근거 원문'})
            elif d['category'] not in ('퀘스트','기타 장면','메시지'):
                content='\n'.join([d['title']]+[r['text'] for s in d['sections'] for r in s['rows']]);hits=[term for term in topic['terms'] if term in content]
                if len(hits)>=2:d['topics'].append({'id':topic['id'],'title':topic['title'],'reason':'본문의 관련 용어: '+', '.join(hits[:4])})
    if fail:write(site/'verification/editorial-errors.json',fail);raise ValueError(str(fail))
    catalog=[]
    for d in docs:
        # Public provenance contains relative source paths only. Full local raw files remain in the preserved extraction.
        d['source']=re.sub(r'[A-Za-z]:[/\\][^\n]*','로컬 추출 원문',d.get('source',''));d.pop('notes',None)
        for s in d['sections']:
            s.pop('local_entry',None)
            if s.get('source','').startswith(('D:','C:')):s['source']='로컬 표'
        write(site/'data/documents'/(d['id']+'.json'),d)
        catalog.append({k:d.get(k,'') for k in ['id','title','category','world','kind','count','chapter','rank','chapterRank','worldRank','collection','topics']})
    # Alias pages resolve to their preserved representative, without duplicating search results.
    write(site/'data/aliases.json',aliases);write(site/'data/catalog.json',catalog);write(site/'data/topics.json',topics)
    stats={'documents':len(docs),'aliases':len(aliases),'questTypes':sorted({d['kind'] for d in docs if d['category']=='퀘스트'}),'original':old['stats'],'chapters':len(chapters),'localSubMissions':len(subs),'missionOrderAcyclic':acyclic,'editorialEssays':len(topics),'verifiedEvidenceLinks':sum(len(s['evidence']) for t in topics for s in t['sections']),'missingTextRows':missing_rows,'limits':['컷신 .playable의 대사 순서는 복원하지 못한 부분이 있습니다.','진행 관계는 임무 설정의 선행 조건 기준이며 모든 분기를 한 회차 순서로 합치지 않습니다.','일부 임무 목표와 컷신이 연결되지 않아 추가 대화로 표시합니다.','챕터 문자열 키와 공개 메타데이터의 Hash를 대응시켜 로컬 한국어 제목을 읽었습니다.']}
    write(site/'data/stats.json',stats);write(site/'verification/preparation.json',stats)
    print(json.dumps({k:v for k,v in stats.items() if k!='original'},ensure_ascii=False))
if __name__=='__main__':main()
