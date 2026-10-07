"""Check complete dialogue coverage independently against local CSV and ID snapshots."""
import argparse,csv,json
from pathlib import Path
from export_dialogue_browser import clean
def main():
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,default=Path('.'));p.add_argument('--local-csv',type=Path);p.add_argument('--snapshot-cache',type=Path);a=p.parse_args();data=a.site/'data';idx=json.loads((data/'dialogue-index.json').read_text('utf8'));ex=json.loads((data/'explorer.json').read_text('utf8'));seen={};counts={}
    for page in idx['pages']:
        d=json.loads((data/'dialogues'/(page['id']+'.json')).read_text('utf8'));rows=d['section']['rows'];assert len(rows)==page['count'];assert page['version']==d['version']
        for row in rows:
            tid=row['talk_id'];assert tid not in seen and row['text'];assert isinstance(row['hash'],str);seen[tid]=(page['version'],row);counts[page['version']]=counts.get(page['version'],0)+1
    assert len(seen)==idx['evidence']['displayed']==idx['evidence']['totalLocal']-idx['evidence']['missingKorean']
    assert counts=={v['version']:v['count'] for v in idx['versions']}
    if a.local_csv:
        original={int(r['id']):r for r in csv.DictReader(a.local_csv.open(encoding='utf-8-sig'))};valid={tid for tid,r in original.items() if clean(r['raw'])};assert set(seen)==valid
        for tid,(_,row) in seen.items():
            r=original[tid];assert row['text']==clean(r['raw']);assert row['speaker']==(clean(r['speaker_raw']) or '화자 미지정');assert row['hash']==r['text_hash'];assert row['speaker_hash']==r['speaker_hash'];assert row['offset']==int(r['offset']) and row['end']==int(r['end'])
    if a.snapshot_cache:
        first={}
        for s in idx['evidence']['snapshots']:
            d=json.loads((a.snapshot_cache/(s['version']+'-talk-ids.json')).read_text('utf8'));assert d['sha256']==s['sha256'] and d['commit']==s['commit']
            for tid in d['ids']:first.setdefault(tid,'early' if s['version']==idx['evidence']['firstSnapshotBaseline'] else s['version'])
        for tid,(version,_) in seen.items():assert version==first.get(tid,'unknown')
    assert ex['counts']=={axis:sum(e['axis']==axis for e in ex['entries']) for axis in ex['counts']};characters=[e for e in ex['entries'] if e['axis']=='person'];assert len({e['id'] for e in characters})==len(characters)
    report={'status':'PASS','dialogues':len(seen),'pages':len(idx['pages']),'counts':ex['counts'],'characterStoryRows':sum(len(e['stories']) for e in characters),'localCsvCompared':bool(a.local_csv),'snapshotsCompared':bool(a.snapshot_cache)}
    (a.site/'verification').mkdir(exist_ok=True);(a.site/'verification/complete-data.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
