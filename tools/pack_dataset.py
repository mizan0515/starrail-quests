"""Create small, verified Git blobs from the curated reading dataset."""
import argparse,hashlib,io,json,zipfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('Choose an empty bundle directory')
    a.output.mkdir(parents=True,exist_ok=True);catalog=json.loads((a.site/'data/catalog.json').read_text('utf8'))
    files=[Path('data')/x for x in ['catalog.json','aliases.json','topics.json','stats.json']]+[Path('data/documents')/(d['id']+'.json') for d in catalog]
    buf=io.BytesIO();manifest=[]
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for relative in sorted(files):
            raw=(a.site/relative).read_bytes();s=raw.decode('utf8')
            if 'C:\\Users\\' in s or 'D:\\game\\' in s:raise ValueError('Absolute personal path in public dataset')
            info=zipfile.ZipInfo(relative.as_posix(),(2026,10,7,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,raw)
            manifest.append({'path':relative.as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)})
    raw=buf.getvalue();parts=[]
    for i,start in enumerate(range(0,len(raw),256*1024)):
        name=f'dataset-{i:03d}.part';part=raw[start:start+256*1024];(a.output/name).write_bytes(part);parts.append({'path':name,'size':len(part),'sha256':hashlib.sha256(part).hexdigest()})
    result={'format':'starrail-dataset.v1','zip_sha256':hashlib.sha256(raw).hexdigest(),'zip_size':len(raw),'parts':parts,'files':manifest}
    (a.output/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf8');print(json.dumps({'bytes':len(raw),'parts':len(parts),'files':len(files)}))
if __name__=='__main__':main()
