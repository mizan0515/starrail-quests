"""Read local dialogue/TextMap tables; classify IDs by hashed version snapshots.

Public snapshots supply IDs only. Text and speakers always come from local files.
"""
import argparse, concurrent.futures, hashlib, json, re, sys, urllib.request
from collections import defaultdict
from pathlib import Path

def clean(s):
    s=s.replace('\\n','\n').replace('\u00a0',' ')
    s=re.sub(r'\{RUBY_[BE]#[^}]*\}','',s)
    return re.sub(r'</?(?:color|size|b|i|u|s|align|voffset|indent|line-height|unbreak)(?:=[^>]*)?>','',s,flags=re.I)
def dump(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf8')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--game-data',type=Path,required=True);ap.add_argument('--skill',type=Path,required=True);ap.add_argument('--site',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);a=ap.parse_args()
    sys.path.insert(0,str(a.skill/'scripts'));from binary import LocalData,decode_table,decode_textmap
    data=LocalData(a.game_data);schemas=json.loads((a.skill/'assets/schemas-v4.json').read_text('utf8'));spec=schemas['TalkSentenceConfig']
    raw,source=data.entry(spec['entry_hash']);talks=decode_table(raw,spec['schema'])
    kr=[f for f in data.catalog if f['language']=='kr'];assert len(kr)==1
    traw,tsource=data.entry(kr[0]['entries'][0][0]);texts={r['hash']:r['raw'] for r in decode_textmap(traw)}
    print('LOCAL',len(talks),'dialogues',len(texts),'Korean strings',flush=True)
    meta=json.loads((a.site/'editorial/mission-versions.json').read_text('utf8'));a.cache.mkdir(parents=True,exist_ok=True)
    def snapshot(s):
        p=a.cache/(s['version']+'-talk-ids.json')
        url=f"https://raw.githubusercontent.com/{meta['repository']}/{s['commit']}/ExcelOutput/TalkSentenceConfig.json"
        if p.exists():
            saved=json.loads(p.read_text('utf8'))
            if saved['commit']!=s['commit']:raise ValueError('Cached snapshot commit mismatch')
        else:
            b=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'StarRail-Korean-Library'}),timeout=90).read()
            rows=json.loads(b);ids=[r.get('TalkSentenceID',0) for r in rows];assert len(ids)==len(set(ids))
            saved={'version':s['version'],'commit':s['commit'],'source':url,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'ids':ids}
            dump(p,saved)
        print('SNAPSHOT',s['version'],len(saved['ids']),flush=True);return saved
    ordered=sorted(meta['snapshots'],key=lambda s:tuple(map(int,s['version'].split('.'))))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: snapshots=list(pool.map(snapshot,ordered))
    first={}
    for s in snapshots:
        for tid in s['ids']:first.setdefault(tid,'early' if s['version']==ordered[0]['version'] else s['version'])
    catalog=json.loads((a.site/'data/catalog.json').read_text('utf8'));missions=defaultdict(set)
    for d in catalog:
        if d['category']!='퀘스트':continue
        doc=json.loads((a.site/'data/documents'/(d['id']+'.json')).read_text('utf8'))
        for sec in doc['sections']:
            for row in sec['rows']:
                if row.get('talk_id'):missions[row['talk_id']].add(d['id'])
    buckets=defaultdict(list)
    for row in talks:
        h=row.get('TalkSentenceText',{}).get('Hash',0);sh=row.get('TextmapTalkSentenceName',{}).get('Hash',0)
        tid=row.get('TalkSentenceID',0)
        buckets[first.get(tid,'unknown')].append({'talk_id':tid,'label':'대사','speaker':clean(texts.get(sh,'')) or '화자 미지정','text':clean(texts.get(h,'')),'hash':str(h),'speaker_hash':str(sh),'voice':row.get('VoiceID',0),'offset':row['_offset'],'end':row['_end'],'missions':sorted(missions[tid])})
    pages=[];versions=[]
    for version,rows in buckets.items():
        valid=[r for r in rows if r['text']];empty=[r for r in rows if not r['text']]
        # Preserve local table row order. This is not a scene execution order.
        for start in range(0,len(valid),400):
            part=valid[start:start+400];key=f'{version}-{start//400+1:03d}';speakers=list(dict.fromkeys(r['speaker'] for r in part));mids=sorted({m for r in part for m in r['missions']})
            dump(a.site/'data/dialogues'/(key+'.json'),{'id':key,'version':version,'section':{'anchor':'dialogue','title':'한국어 대사 원문','mapping':'LOCAL_TABLE','source':'TalkSentenceConfig','rows':part}})
            pages.append({'id':key,'version':version,'part':start//400+1,'count':len(part),'speakers':speakers,'missions':mids,'preview':part[0]['text'][:95],'linked':sum(bool(r['missions']) for r in part)})
        versions.append({'version':version,'count':len(valid),'missingKorean':len(empty),'linked':sum(bool(r['missions']) for r in valid),'unlinked':sum(not r['missions'] for r in valid)})
    def portable(s):return {**s,'file':Path(s['file']).name}
    evidence={'method':'LOCAL_TALK_TABLE_AND_KOREAN_TEXTMAP_WITH_VERSION_ID_FIRST_APPEARANCE','dialogueTable':portable(source),'textMap':portable(tsource),'sources':[{**v,'file':Path(k).name} for k,v in data.evidence.items()],'snapshots':[{k:v for k,v in s.items() if k!='ids'} for s in snapshots],'totalLocal':len(talks),'displayed':sum(v['count'] for v in versions),'missingKorean':sum(v['missingKorean'] for v in versions),'firstSnapshotBaseline':ordered[0]['version'],'chronology':'Local table row order; never claimed as story execution order'}
    dump(a.site/'data/dialogue-index.json',{'versions':versions,'pages':pages,'evidence':evidence});data.verify_unchanged()
    print(json.dumps({'pages':len(pages),'versions':versions},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
