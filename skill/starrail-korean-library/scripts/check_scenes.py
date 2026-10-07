"""Check auxiliary scene ID references against local bytes; not a control-flow decoder."""
import argparse, hashlib, json, re
from collections import defaultdict
from pathlib import Path
from binary import LocalData, decode_table, varint
from export_library import SKILL, scenes_from_object, sha, dump

ID_PATTERN=re.compile(rb'[\x80-\xff]{3,4}[\x00-\x7f]')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--game-data',type=Path,required=True);ap.add_argument('--structure',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.output.exists():raise SystemExit('Evidence output already exists')
    data=LocalData(args.game_data);schema=json.loads((SKILL/'assets/schemas-v4.json').read_text(encoding='utf8'))['TalkSentenceConfig']
    raw,_=data.entry(schema['entry_hash']);talks={r.get('TalkSentenceID',0) for r in decode_table(raw,schema['schema'])}
    pack=max((f for f in data.catalog if not f['language']),key=lambda f:len(f['entries']))
    blob=data.read(data.file_path(pack));sequences={};inverted=defaultdict(set);entry_meta={}
    for key,length,offset in pack['entries']:
        seq=[]
        for m in ID_PATTERN.finditer(blob[offset:offset+length]):
            value,_=varint(m.group(),0)
            if value in talks:seq.append(value)
        if seq:
            sequences[key]=seq;entry_meta[key]=[str(key),length,offset]
            for tid in set(seq):inverted[tid].add(key)
    checks={};matched=0
    for base in ('Story','Config/Level/Mission'):
        for p in sorted((args.structure/base).rglob('*.json')):
            refs=scenes_from_object(json.loads(p.read_text(encoding='utf8')))
            if not refs:continue
            known=list(dict.fromkeys(x['id'] for x in refs if x['id'] in talks))
            candidates=None
            for tid in known:
                candidates=inverted[tid].copy() if candidates is None else candidates&inverted[tid]
                if not candidates:break
            candidates=candidates or set();status='UNVERIFIED_SCENE_MAPPING';local=None
            if len(known)>=2 and len(candidates)==1:
                key=next(iter(candidates));iterator=iter(sequences[key])
                if all(any(v==tid for v in iterator) for tid in known):
                    status='LOCAL_ID_ORDER_MATCH';local=entry_meta[key];matched+=1
            checks[p.relative_to(args.structure).as_posix()]={'status':status,'references':len(refs),'missing_talks':sum(x['id'] not in talks for x in refs),'candidates':len(candidates),'local_entry':local,'structure_sha256':sha(p)}
    data.verify_unchanged()
    dump(args.output,{'method':'Distinct known IDs in JSON traversal order must be an ordered subsequence in one unique local catalog entry. Byte occurrence only; execution order/conditions are unverified.','local_pack':str(data.file_path(pack)),'source_files':data.evidence,'checks':checks})
    print(json.dumps({'scenes':len(checks),'local_id_order_matches':matched},indent=2),flush=True)

if __name__=='__main__':main()
