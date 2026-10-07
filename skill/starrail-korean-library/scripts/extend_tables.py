"""Discover additional observed tables; require unique match, reference rows and EOF."""
import argparse, json, heapq
from pathlib import Path
from binary import LocalData, varint, signed, decode_table

def order(rows):
    rank={};edges={};degree={}
    for r in rows:
        for k in r:rank.setdefault(k,len(rank));edges.setdefault(k,set());degree.setdefault(k,0)
        for a,b in zip(r,list(r)[1:]):
            if b not in edges[a]:edges[a].add(b);degree[b]+=1
    ready=[(rank[k],k) for k in rank if degree[k]==0];heapq.heapify(ready);result=[]
    while ready:
        _,k=heapq.heappop(ready);result.append(k)
        for b in edges[k]:
            degree[b]-=1
            if not degree[b]:heapq.heappush(ready,(rank[b],b))
    if len(result)!=len(rank):raise ValueError('Conflicting field order')
    return result

def infer(rows):
    types={}
    for k in order(rows):
        samples=[r[k] for r in rows if k in r];v=next((x for x in samples if x),samples[0])
        if isinstance(v,dict):t='hash' if 'Hash' in v else infer(samples)
        elif isinstance(v,list):
            values=[x for s in samples for x in s]
            t=[infer(values)] if values and isinstance(values[0],dict) else ['enum' if values and isinstance(values[0],str) else 'int']
        elif isinstance(v,str):t='str' if k.endswith('Path') or k.endswith('Name') and '/' in v else 'enum'
        elif isinstance(v,float):t='float'
        else:t='int'
        types[k]=t
    return types

def eq(a,b):
    if isinstance(b,dict):return isinstance(a,dict) and all(eq(a.get(k),v) for k,v in b.items())
    if isinstance(b,list):return isinstance(a,list) and len(a)==len(b) and all(eq(x,y) for x,y in zip(a,b))
    return True if isinstance(b,str) else a==b

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--game-data',type=Path,required=True);ap.add_argument('--structure',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--tables',nargs='+',required=True);args=ap.parse_args()
    local=LocalData(args.game_data);pieces=[]
    for f in local.catalog:
        if f['language'] or len(f['entries'])>10000:continue
        raw=local.read(local.file_path(f))
        for h,n,o in f['entries']:
            try:
                p=o+int(raw[o]==0);count,p=varint(raw,p);flags,p=varint(raw,p);first,p=varint(raw,p)
                pieces.append((h,signed(count),flags,first))
            except ValueError:pass
    result={}
    for name in args.tables:
        ref=json.loads((args.structure/'ExcelOutput'/(name+'.json')).read_text('utf8'));ref=list(ref.values()) if isinstance(ref,dict) else ref
        types=infer(ref)
        if name=='MissionChapterConfig':
            for k in ('ChapterName','StageName','ChapterDesc'):types[k]='str'
        fields=list(types);first=ref[0][fields[0]];matches=[]
        for h,n,flags,v in pieces:
            if v!=first or not .8*len(ref)<=n<=1.1*len(ref) or flags.bit_length()>len(fields)+8:continue
            schema=list(types.items());bits=[i for i in range(flags.bit_length()) if flags&(1<<i)]
            if len(bits)==len(ref[0]):
                slots=dict(zip(ref[0],bits));occupied=set(bits)
                try:
                    for index,k in enumerate(fields):
                        if k in slots:continue
                        lo=max((slots[x]+1 for x in fields[:index] if x in slots),default=0);hi=min((slots[x] for x in fields[index+1:] if x in slots),default=lo+len(fields)+5)
                        slots[k]=next(i for i in range(lo,hi) if i not in occupied);occupied.add(slots[k])
                    schema=[('_reserved'+str(i),'int') for i in range(max(slots.values())+1)]
                    for k,i in slots.items():schema[i]=(k,types[k])
                except StopIteration:continue
            try:
                raw,source=local.entry(h);rows=decode_table(raw,schema)
                if not all(all(eq(a.get(k),v) for k,v in b.items()) for a,b in zip(rows[:3],ref[:3])):continue
                matches.append({'schema':schema,'source':source,'rows':rows})
            except (ValueError,UnicodeDecodeError,IndexError):continue
        if len(matches)!=1:raise ValueError((name,'unique table match required',len(matches)))
        result[name]=matches[0];print(name,len(matches[0]['rows']),matches[0]['source']['entry_hash'])
    local.verify_unchanged();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps({'tables':result,'sources':local.evidence},ensure_ascii=False),encoding='utf8')
if __name__=='__main__':main()
