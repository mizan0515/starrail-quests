"""Restore only manifest-listed curated files after checking every archive hash."""
import argparse,hashlib,io,json,zipfile
from pathlib import Path

def digest(x):return hashlib.sha256(x).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=Path('dataset'));p.add_argument('--target',type=Path,default=Path('.'));a=p.parse_args();m=json.loads((a.bundle/'manifest.json').read_text('utf8'));parts=[]
    for part in m['parts']:
        name=part['path']
        if Path(name).name!=name:raise ValueError('Invalid part name')
        raw=(a.bundle/name).read_bytes()
        if len(raw)!=part['size'] or digest(raw)!=part['sha256']:raise ValueError('Part hash mismatch')
        parts.append(raw)
    raw=b''.join(parts)
    if len(raw)!=m['zip_size'] or digest(raw)!=m['zip_sha256']:raise ValueError('Archive hash mismatch')
    allowed={x['path']:x for x in m['files']};root=a.target.resolve();pending=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if set(z.namelist())!=set(allowed) or len(z.namelist())!=len(allowed):raise ValueError('Archive member mismatch')
        for name in z.namelist():
            target=(root/name).resolve()
            if not target.is_relative_to(root) or not name.startswith('data/'):raise ValueError('Unsafe archive path')
            body=z.read(name);entry=allowed[name]
            if len(body)!=entry['size'] or digest(body)!=entry['sha256']:raise ValueError('File hash mismatch')
            if target.exists() and target.read_bytes()!=body:raise ValueError('Refusing to overwrite changed data')
            pending.append((target,body))
    for target,body in pending:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
    catalog=root/'data/catalog.json';(root/'public').mkdir(exist_ok=True);(root/'public/catalog.json').write_bytes(catalog.read_bytes())
    print(f'Restored {len(pending)} verified curated files')
if __name__=='__main__':main()
