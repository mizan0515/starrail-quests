"""Package verified supplemental exploration and complete local dialogue data."""
import argparse,hashlib,io,json,zipfile
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,default=Path('.'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('Choose an empty bundle directory')
    a.output.mkdir(parents=True,exist_ok=True);files=[Path('data/explorer.json'),Path('data/dialogue-index.json')]+sorted(Path('data/dialogues')/p.name for p in (a.site/'data/dialogues').glob('*.json'));buf=io.BytesIO();manifest=[]
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for rel in files:
            raw=(a.site/rel).read_bytes();s=raw.decode('utf8')
            if 'C:\\Users\\' in s or 'D:\\game\\' in s:raise ValueError('Personal path in data')
            info=zipfile.ZipInfo(rel.as_posix(),(2026,10,7,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,raw);manifest.append({'path':rel.as_posix(),'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    raw=buf.getvalue();parts=[]
    for i,start in enumerate(range(0,len(raw),256*1024)):
        name=f'extra-{i:03d}.part';body=raw[start:start+256*1024];(a.output/name).write_bytes(body);parts.append({'path':name,'size':len(body),'sha256':hashlib.sha256(body).hexdigest()})
    (a.output/'manifest.json').write_text(json.dumps({'format':'starrail-dataset.v1','zip_size':len(raw),'zip_sha256':hashlib.sha256(raw).hexdigest(),'parts':parts,'files':manifest},separators=(',',':')),encoding='utf8');print(json.dumps({'bytes':len(raw),'parts':len(parts),'files':len(files)}))
if __name__=='__main__':main()
