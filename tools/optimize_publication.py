"""Deduplicate generated UI only; retain each original passage as static HTML.

The audit permits exact expansion back to the pre-optimization HTML/CSS/JS.
No installation data, restoration bundles, or source artifacts are modified.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

LIMIT=1_000_000_000
REPORT=Path('.codex-work/publication-build-report.json')
RESTORATION_ONLY={
 'mission-dialogue-supplements.json','dialogue-contexts.json',
 'handbook-originals.json','official-talk-library.json','universe-catalog.json',
 'universe-source-records.json','official-universe-texts.json','catalog.json',
 'official-video-captions.json','official-mission-talks.json',
}
SCOPE=re.compile(r'\bastro-[a-z0-9]{8}\b')
TAG={k:re.compile(r'<'+k+r'\b([^>]*)>([\s\S]*?)</'+k+r'>') for k in ('style','script')}
FRAGMENTS=[
 re.compile(r'<template id="theme-icons">[\s\S]*?</template>'),
 re.compile(r'<header\b[\s\S]*?</header>'),
 re.compile(r'<nav class="sidebar\b[\s\S]*?</sl-sidebar-pane></nav>'),
 re.compile(r'<sl-sidebar-pane\b[\s\S]*?</sl-sidebar-pane>'),
 re.compile(r'<aside class="(?:right-sidebar-container|collection-panel)\b[\s\S]*?</aside>'),
 re.compile(r'<nav class="breadcrumbs"[\s\S]*?</nav>'),
 re.compile(r'<a class="catalog-return"[^>]*>[\s\S]*?</a>'),
 re.compile(r'<footer\b[\s\S]*?</footer>'),
 re.compile(r'<dialog class="context-dialog"[\s\S]*?</dialog>'),
]

def digest(body):return hashlib.sha256(body).hexdigest()
def require(condition,message):
 if not condition:raise ValueError(message)
def text_files(root):return sorted(p for p in root.rglob('*') if p.suffix in ('.html','.css','.js') and '_shared' not in p.parts and 'pagefind' not in p.parts)
def total(root):return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
def write_json(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),'utf8')

def optimize(root,base,report_path):
 require(not (root/'_shared').exists(),'Already optimized: rebuild HTML first')
 before=total(root);files=text_files(root);originals={};scopes=set();aliases=set();pools={k:Counter() for k in TAG};references={name:False for name in RESTORATION_ONLY}
 # Two bounded passes avoid retaining the complete 1.5 GB HTML in memory.
 for position,file in enumerate(files):
  raw=file.read_bytes();originals[file.relative_to(root).as_posix()]=digest(raw)
  s=raw.decode('utf8');scopes.update(SCOPE.findall(s));aliases.update(re.findall(r'\b_q[A-Za-z0-9]+\b',s))
  for name in references:
   if name in s:references[name]=True
  if file.suffix=='.html':
   for kind,pattern in TAG.items():
    for m in pattern.finditer(s):
     if kind=='script' and ('src=' in m[1] or 'application/' in m[1]):continue
     pools[kind][(m[1],m[2])]+=1
  if position%5000==0:print(f'Publication scan {position+1}/{len(files)}',flush=True)
 alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
 mapping={scope:'_q'+(alphabet[i] if i<len(alphabet) else str(i)) for i,scope in enumerate(sorted(scopes))}
 require(not(set(mapping.values())&aliases),'Generated scope alias collision')
 shared=root/'_shared';shared.mkdir();assets={};replacements={};counts=Counter()
 def asset(body,suffix,kind):
  raw=body.encode();key=digest(raw)[:20]+suffix;target=shared/key
  if key in assets:require(assets[key]['sha256']==digest(raw),'Asset hash collision')
  else:target.write_bytes(raw);assets[key]={'sha256':digest(raw),'kind':kind}
  return f'{base}/_shared/{key}'
 def remember(replacement,original):
  require(replacement not in replacements or replacements[replacement]==original,'Conflicting replacement')
  replacements[replacement]=original;return replacement
 fallback='<noscript><nav aria-label="자료집 탐색">'+''.join(f'<a href="{base}/{path}">{name}</a> ' for path,name in [('index.html','퀘스트'),('설정집.html','설정집'),('도감.html','도감'),('대사.html','대사'),('대화.html','사용 장면')])+'</nav></noscript>'
 footer_fallback=f'<noscript><footer data-pagefind-ignore><p>비공식 자료집 · 게임 콘텐츠 권리: HoYoverse 등 해당 권리자</p><a href="{base}/자료안내.html">자료 안내</a> · <a href="https://github.com/mizan0515/starrail-quests/tree/main/src/lib/reading-kit/cva">CVA 소스 · GPLv3</a></footer></noscript>'
 for position,file in enumerate(files):
  s=file.read_bytes().decode('utf8')
  if mapping:s=SCOPE.sub(lambda m:mapping[m[0]],s)
  if file.suffix=='.html':
   # Identical external modules execute once per URL. Keep any module that
   # originally has multiple occurrences on this page inline.
   module_counts=Counter((m[1],m[2]) for m in TAG['script'].finditer(s) if 'type="module"' in m[1])
   for kind,pattern in TAG.items():
    def extract(m):
     attrs,body=m[1],m[2]
     if kind=='script' and ('src=' in attrs or 'application/' in attrs or len(body)<128 or 'import.meta' in body):return m[0]
     original_body=body
     for old,new in mapping.items():original_body=re.sub(r'\b'+re.escape(new)+r'\b',old,original_body)
     if pools[kind][(attrs,original_body)]<2:return m[0]
     if kind=='script' and 'type="module"' in attrs:
      if module_counts[(attrs,body)]>1:return m[0]
      if re.search(r'(?:from\s*|import\s*\(?)[\'\"]\.',body):return m[0]
     url=asset(body,'.css' if kind=='style' else '.js',kind)
     if kind=='style':replacement=f'<link rel="stylesheet" href="{url}" data-ps{attrs}>'
     else:replacement=f'<script{attrs} src="{url}" data-pj></script>'
     counts[kind]+=1;return remember(replacement,m[0])
    s=pattern.sub(extract,s)
   for pattern in FRAGMENTS:
    def extract_fragment(m):
     fragment=m[0]
     # A classic, parser-blocking script inserts the exact original subtree
     # in its original parser position. Its existing scripts retain order.
     url=asset('document.write('+json.dumps(fragment,ensure_ascii=False)+');\n','.js','fragment')
     replacement=f'<script src="{url}" data-pf></script>'
     if fragment.startswith('<header'):replacement+=fallback
     if fragment.startswith('<footer'):replacement+=footer_fallback
     counts['fragment']+=1;return remember(replacement,fragment)
    s=pattern.sub(extract_fragment,s)
  file.write_text(s,'utf8',newline='')
  if position%5000==0:print(f'Publication shared UI {position+1}/{len(files)}',flush=True)
 # Only known build-time mirrors can be omitted. Runtime JSON, linked raw
 # dialogue JSON, and every reading-data shard stay available.
 removed={}
 for name,used in references.items():
  file=root/name
  if not used and file.exists():
   removed[name]={'bytes':file.stat().st_size,'sha256':digest(file.read_bytes())};file.unlink()
 after=total(root)
 report={'schema':'starrail-publication-dedup.v1','base':base,'beforeBytes':before,'afterBytes':after,'limitBytes':LIMIT,'scopes':mapping,'originalFiles':originals,'assets':assets,'replacements':replacements,'removedBuildMirrors':removed,'counts':dict(counts)}
 write_json(report_path,report)
 print(json.dumps({'status':'PASS' if after<=LIMIT else 'OVER_LIMIT','beforeBytes':before,'afterBytes':after,'savedBytes':before-after,'removedMirrors':list(removed),'sharedAssets':len(assets),'counts':dict(counts)},ensure_ascii=False),flush=True)
 require(after<=LIMIT,'Published site exceeds 1 GB')

def verify(root,report_path):
 report=json.loads(report_path.read_text('utf8'));replacements=report['replacements']
 # Longest match first: fragment expansion reveals external style/script
 # tags, which are then expanded in a second pass.
 fragments={r:o for r,o in replacements.items() if re.search(r'\bdata-(?:pf|publication-fragment)\b',r)}
 inline={r:o for r,o in replacements.items() if r not in fragments}
 # Match the small generated tag grammar, then require an exact dictionary
 # key. This avoids thousands of near-identical URL regex alternatives.
 # The only optional suffixes are the exact injected no-JS fallbacks.
 suffixes={r.partition('</script>')[2] for r in fragments if r.partition('</script>')[2]}
 suffix='(?:'+'|'.join(map(re.escape,sorted(suffixes,key=len,reverse=True)))+')?' if suffixes else ''
 fragment_pattern=re.compile(r'<script\b[^>]*\bdata-(?:pf|publication-fragment)\b[^>]*></script>'+suffix)
 inline_pattern=re.compile(r'<script\b[^>]*\bdata-(?:pj|publication-script)\b[^>]*></script>|<link\b[^>]*\bdata-(?:ps|publication-style)\b[^>]*>')
 expand_fragment=lambda s:fragment_pattern.sub(lambda m:fragments.get(m[0],m[0]),s)
 expand_inline=lambda s:inline_pattern.sub(lambda m:inline.get(m[0],m[0]),s)
 reverse={v:k for k,v in report['scopes'].items()};scope=re.compile(r'\b(?:'+'|'.join(map(re.escape,reverse))+r')\b')
 for name,record in report['assets'].items():
  file=root/'_shared'/name;require(file.is_file() and digest(file.read_bytes())==record['sha256'],'Shared asset differs '+name)
 for name,expected in report['originalFiles'].items():
  file=root/name;require(file.is_file(),'Generated file missing '+name)
  s=file.read_bytes().decode('utf8')
  if file.suffix=='.html':s=expand_inline(expand_fragment(s))
  if reverse:s=scope.sub(lambda m:reverse[m[0]],s)
  require(digest(s.encode())==expected,'Generated UI/HTML does not expand exactly '+name)
 for name in report['removedBuildMirrors']:require(name in RESTORATION_ONLY and not(root/name).exists(),'Unexpected removed asset')
 size=total(root);require(size==report['afterBytes'] and size<=LIMIT,'Publication size changed or exceeds 1 GB')
 print(json.dumps({'status':'PASS','exactExpandedFiles':len(report['originalFiles']),'sharedAssets':len(report['assets']),'staticOriginalHtml':True,'afterBytes':size,'limitBytes':LIMIT},ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('dist'));p.add_argument('--base',default='/starrail-quests');p.add_argument('--report',type=Path,default=REPORT);p.add_argument('--verify',action='store_true');a=p.parse_args()
 if a.verify:verify(a.root,a.report)
 else:optimize(a.root,a.base.rstrip('/'),a.report);verify(a.root,a.report)
