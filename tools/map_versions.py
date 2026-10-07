"""Reproduce the public version classification from recorded snapshot commits.

Read metadata only. Never fetch public dialogue or infer version from an ID.
"""
import argparse,concurrent.futures,hashlib,json,urllib.request
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--metadata',type=Path,default=Path('editorial/mission-versions.json'));p.add_argument('--cache',type=Path,required=True);a=p.parse_args()
    meta=json.loads(a.metadata.read_text('utf8'));a.cache.mkdir(parents=True,exist_ok=True)
    def read_snapshot(s):
        path=a.cache/(s['version']+'.json')
        if not path.exists():
            url=f"https://raw.githubusercontent.com/{s.get('repository',meta['repository'])}/{s['commit']}/ExcelOutput/MainMission.json"
            req=urllib.request.Request(url,headers={'User-Agent':'StarRail-Korean-Library'})
            path.write_bytes(urllib.request.urlopen(req,timeout=40).read())
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=s['sha256']:raise ValueError('Snapshot hash mismatch')
        rows=json.loads(raw)
        rows=list(rows.values()) if isinstance(rows,dict) else rows
        if len(rows)!=s['missions']:raise ValueError('Snapshot row count mismatch')
        return s['version'],[str(r['MainMissionID']) for r in rows]
    ordered=sorted(meta['snapshots'],key=lambda s:tuple(map(int,s['version'].split('.'))))
    first={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for version,ids in pool.map(read_snapshot,ordered):
            for mid in ids:first.setdefault('quest-'+mid,version)
    if first!=meta.get('firstObservedVersions',meta['missions']):raise ValueError('Version projection differs from recorded metadata')
    for mid,e in meta.get('releaseEvidence',{}).items():
        if meta['missions'].get(mid)!=e['version']:raise ValueError('Release evidence projection mismatch')
    print(f"PASS: {len(ordered)} hashed snapshots, {len(first)} mission IDs. Earliest snapshot is a baseline, not a release assertion.")

if __name__=='__main__':main()
