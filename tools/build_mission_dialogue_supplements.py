"""Join exact public Story references with preserved local Korean dialogue.

Never uses a numeric prefix/range to assign a dialogue to a mission. Public
metadata provides IDs and pointers; all text and speaker fields come from the
preserved local extraction. Structure traversal order is not execution order.
"""
import argparse, hashlib, json, re, tarfile
from collections import defaultdict
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
COMMIT = '8b178dd48698e5e7b12f0cc319ddab149f2ffc5c'
REPO = 'DimbreathBot/TurnBasedGameData'
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p): return json.loads(p.read_text('utf8'))
def refs(obj, pointer=''):
    if isinstance(obj, dict):
        for key, value in obj.items():
            p=pointer+'/'+key
            if key=='TalkSentenceID' and isinstance(value,int):
                yield value,p,'TalkSentenceID'
            elif key=='TalkSentenceIDList' and isinstance(value,list):
                for i,v in enumerate(value):
                    if isinstance(v,int): yield v,p+'/'+str(i),'TalkSentenceIDList'
            elif isinstance(value,str) and re.fullmatch(r'TalkSentence_\d+',value):
                yield int(value.split('_')[1]),p,'TalkSentence event reference'
            yield from refs(value,p)
    elif isinstance(obj,list):
        for i,v in enumerate(obj): yield from refs(v,pointer+'/'+str(i))

def build(archive):
    quests={d['id']:d for p in (SITE/'data/documents').glob('quest-*.json') if (d:=read(p))}
    local={}
    for p in (SITE/'data/dialogues').glob('*.json'):
        for row in read(p)['section']['rows']:
            local[row['talk_id']]={**row,'pageId':p.stem,'url':'대사/'+p.stem+'.html#talk-'+str(row['talk_id'])}
    expected={s['source'] for q in quests.values() for s in q['sections'] if s.get('source')}
    missions=defaultdict(list); files={}; missing=[]; unresolved=[]
    with tarfile.open(archive,'r:gz') as tf:
        for member in tf:
            path=member.name.split('/',1)[-1]
            # Only structure JSON is opened. Public TextMap is never read.
            match=re.match(r'(?:Story/(?:Discussion/)?Mission|Config/Level/Mission)/(\d+)(?:/|\.)',path)
            if not match or not path.endswith('.json'): continue
            mid='quest-'+match[1]
            if mid not in quests: continue
            raw=tf.extractfile(member).read(); obj=json.loads(raw)
            found=list(refs(obj)); files[path]=sha(raw)
            existing={r.get('talk_id') for s in quests[mid]['sections'] if s.get('source')==path for r in s['rows']}
            grouped=defaultdict(list)
            for tid,ptr,kind in found: grouped[tid].append({'pointer':ptr,'kind':kind})
            rows=[]
            for tid,pointers in grouped.items():
                if tid in existing: continue
                if tid not in local:
                    unresolved.append({'missionId':mid,'source':path,'talkId':tid,'references':pointers}); continue
                row=local[tid]
                rows.append({**row,'references':pointers,'anchor':'talk-'+str(tid)})
            if rows:
                missions[mid].append({'anchor':'supplement-'+sha(path.encode())[:12], 'title':'추가 대사 원문', 'source':path,'sourceSha256':sha(raw),'sourceUrl':f'https://github.com/{REPO}/blob/{COMMIT}/{path}', 'mapping':'EXACT_PUBLIC_STRUCTURE_REFERENCE_TO_PRESERVED_LOCAL_TALK', 'order':'구조 파일의 참조 순서', 'rows':rows})
    missing=sorted(expected-set(files))
    out={'schema':'starrail-mission-dialogue-supplements.v1','evidence':{'repository':REPO,'commit':COMMIT,'archiveSha256':sha(archive.read_bytes()),'dialogueIndexSha256':sha((SITE/'data/dialogue-index.json').read_bytes()),'preservedLocalSources':read(SITE/'data/dialogue-index.json')['evidence']['sources'],'currentInstallationReparse':'UNVERIFIED_FULL_KOREAN_PACK_UNAVAILABLE','structureFiles':files,'method':'Exact integer TalkSentenceID, ID-list or TalkSentence_N event references in a mission-owned structure path; local Korean text unchanged.'},'missions':dict(missions),'unresolvedReferences':unresolved,'missingExistingStructurePaths':missing,'counts':{'localKoreanRows':len(local),'missions':len(missions),'scenes':sum(map(len,missions.values())),'rows':sum(len(s['rows']) for scenes in missions.values() for s in scenes),'structureFiles':len(files),'missingStructurePaths':len(missing),'unresolvedReferences':len(unresolved)},'limitations':['공개 구조의 참조는 해당 장면에서 사용하는 식별자를 보여준다. 실제 실행 조건과 재생 순서는 별도 자료가 필요하다.','타임라인 내부 자막 중 구조 JSON에 식별자가 없는 대사는 이 연결 범위에 포함되지 않는다.']}
    for p in [SITE/'data/mission-dialogue-supplements.json',SITE/'public/mission-dialogue-supplements.json']:
        p.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),'utf8')
    print(json.dumps(out['counts']))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);a=p.parse_args();build(a.archive)
