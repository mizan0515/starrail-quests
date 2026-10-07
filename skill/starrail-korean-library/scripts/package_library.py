"""Package only a verified artifact folder; compare every archived file afterward."""
import argparse,json,zipfile
from pathlib import Path
from verify_library import require,verify_zip
from export_library import dump

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path);ap.add_argument('--zip',required=True,type=Path);args=ap.parse_args();root=args.output.resolve();archive=args.zip.resolve()
    require(archive.suffix.lower()=='.zip' and not archive.exists(),'ZIP must be new and end with .zip')
    require(not archive.is_relative_to(root),'Keep archive outside its input folder')
    result=json.loads((root/'검증/검증결과.json').read_text(encoding='utf8'));require(result['status']=='PASS_WITH_LIMITATIONS','Run source/content verification first')
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(root).as_posix())
    evidence={'status':'PASS','archive':verify_zip(archive,root)};dump(archive.with_suffix('.verification.json'),evidence);print(json.dumps(evidence,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
