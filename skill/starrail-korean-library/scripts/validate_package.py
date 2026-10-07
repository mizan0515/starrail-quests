"""Validate this deliberately simple skill package without third-party YAML libraries."""
import ast,argparse,json,re,subprocess
from pathlib import Path
from export_library import SKILL,dump

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--node',required=True,type=Path);ap.add_argument('--report',type=Path);args=ap.parse_args()
    text=(SKILL/'SKILL.md').read_text(encoding='utf8');m=re.match(r'^---\n(.*?)\n---',text,re.S)
    if not m:raise ValueError('Missing YAML frontmatter')
    meta={}
    for line in m.group(1).splitlines():
        k,v=line.split(':',1);v=v.strip()
        if not re.fullmatch('[a-z-]+',k) or not v or ': ' in v or v[0] in '[{>&*!|':raise ValueError('Frontmatter requires a YAML parser beyond this simple schema')
        meta[k]=json.loads(v) if v.startswith('"') else v
    if set(meta)!={'name','description'}:raise ValueError('Unexpected frontmatter fields')
    name=meta['name'];desc=meta['description']
    if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',name) or len(name)>64 or name!=SKILL.name:raise ValueError('Invalid skill name')
    if len(desc)>1024 or '<' in desc or '>' in desc or '[TODO:' in text:raise ValueError('Invalid description or unfinished scaffold')
    interface=(SKILL/'agents/openai.yaml').read_text(encoding='utf8').splitlines();fields={}
    if interface[0]!='interface:':raise ValueError('Missing interface')
    for line in interface[1:]:
        key,value=line.strip().split(':',1);fields[key]=json.loads(value.strip())
    if not 25<=len(fields['short_description'])<=64:raise ValueError('Interface short description length')
    if '$'+name not in fields['default_prompt']:raise ValueError('Prompt must reference skill')
    scripts=list((SKILL/'scripts').glob('*.py'))
    for p in scripts:ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    subprocess.run([str(args.node),'--check',str(SKILL/'assets/library.js')],check=True)
    for rel in ('references/format-and-evidence.md','assets/schemas-v4.json','assets/index.html','assets/library.css'):assert (SKILL/rel).is_file()
    json.loads((SKILL/'assets/schemas-v4.json').read_text(encoding='utf8'))
    result={'status':'PASS','skill':name,'python_scripts_checked':len(scripts),'frontend_syntax_checked':True,'frontmatter_and_interface_checked':True,'validator':'Stdlib checks for this flat YAML schema; official quick_validate.py was unavailable because bundled Python has no PyYAML.'}
    if args.report:dump(args.report,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
