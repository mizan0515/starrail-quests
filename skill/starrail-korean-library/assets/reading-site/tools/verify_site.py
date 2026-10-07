"""Verify generated document links, anchors, hidden technical labels and evidence."""
import argparse,json,re
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote

class Page(HTMLParser):
    def __init__(self):super().__init__();self.ids=set();self.links=[];self.labels=[];self.capture=False;self.duplicates=[];self.original={};self.original_id=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get('id'):
            if a['id'] in self.ids:self.duplicates.append(a['id'])
            self.ids.add(a['id'])
        if tag=='a' and a.get('href'):self.links.append(a['href'])
        if tag in ('script','link','img'):
            src=a.get('src') or a.get('href')
            if src:self.links.append(src)
        if tag in ('h1','h2','h3','h4'):self.capture=True
        if tag=='p' and 'original-body' in a.get('class','').split():self.original_id=a.get('id');self.original[self.original_id]=''
    def handle_endtag(self,tag):
        if tag in ('h1','h2','h3','h4'):self.capture=False
        if tag=='p':self.original_id=None
    def handle_data(self,data):
        if self.capture:self.labels.append(data)
        if self.original_id is not None:self.original[self.original_id]+=data

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--base',default='/starrail-quests');p.add_argument('--report',type=Path);a=p.parse_args();root=a.root.resolve();pages={};errors=[];links=0
    for file in root.rglob('*.html'):
        page=Page();page.feed(file.read_text('utf8'));pages[file.resolve()]=page
        if page.duplicates:errors.append((file.relative_to(root).as_posix(),'duplicate anchors',page.duplicates))
        if any(re.search(r'\b(?:DS|Story)\d{6,}',x) for x in page.labels):errors.append((str(file),'technical scene heading'))
        if any('정리본문.csv' in x or '정리%EB%B3%B8' in x for x in page.links):errors.append((str(file),'work CSV link'))
    for file,page in pages.items():
        for link in page.links:
            u=urlsplit(link)
            if u.scheme or u.netloc:continue
            path=unquote(u.path)
            if path.startswith('/'):
                if a.base and path.startswith(a.base):path=path[len(a.base):]
                target=(root/path.lstrip('/')).resolve()
            else:target=(file.parent/path).resolve() if path else file
            if target.is_dir():target/= 'index.html'
            if not target.exists() and not target.suffix and target.with_suffix('.html').exists():target=target.with_suffix('.html')
            if not target.is_relative_to(root) or not target.exists():errors.append((str(file.relative_to(root)),link,'missing target'));continue
            if u.fragment and target in pages and unquote(u.fragment) not in pages[target].ids:errors.append((str(file.relative_to(root)),link,'missing anchor'))
            links+=1
    data=root.parent/'data';catalog=json.loads((data/'catalog.json').read_text('utf8'));topics=json.loads((data/'topics.json').read_text('utf8'));evidence=0
    for t in topics:
        for section in t['sections']:
            for e in section['evidence']:
                d=json.loads((data/'documents'/(e['id']+'.json')).read_text('utf8'));matched=[s for s in d['sections'] if s['anchor']==e['anchor'] and any(e['needle'] in row['text'] for row in s['rows'])]
                if not matched:errors.append((t['id'],e['id'],'evidence mismatch'))
                evidence+=1
    if not (root/'pagefind/pagefind.js').exists():errors.append(('pagefind','missing index'))
    version_file=root/'versions-data.json'
    if not version_file.exists():errors.append(('versions','missing metadata'))
    else:
        version_data=json.loads(version_file.read_text('utf8'))
        if set(version_data)!={d['id'] for d in catalog if d['category']=='퀘스트'}:errors.append(('versions','catalog mismatch'))
        for version in {v for values in version_data.values() for v in values}:
            if not (root/'versions'/(version+'.html')).exists():errors.append(('versions',version,'missing page'))
    original_rows=0
    for d in catalog:
        if (root/'문서'/(d['id']+'.html')).resolve() not in pages:errors.append((d['id'],'missing document'))
        else:
            document=json.loads((data/'documents'/(d['id']+'.json')).read_text('utf8'));rendered=pages[(root/'문서'/(d['id']+'.html')).resolve()].original
            for section in document['sections']:
                for i,row in enumerate(section['rows'],1):
                    anchor=f"{section['anchor']}-row-{i}"
                    if rendered.get(anchor)!=row['text']:errors.append((d['id'],anchor,'rendered original text differs'))
                    original_rows+=1
    atlas=json.loads((root.parent/'editorial/context-atlas.json').read_text('utf8'));atlas_evidence={};node_ids={n['id'] for n in atlas['nodes']}
    for node in atlas['nodes']:
        target=root/'맥락'/(node['id']+'.html')
        if not target.exists() or 'verified-sources' not in pages[target.resolve()].ids:errors.append((node['id'],'missing dossier or bottom sources'))
        for link in node['links']:
            if link['target'] not in node_ids:errors.append((node['id'],link['target'],'unknown atlas connection'))
        for item in node['evidence']+[x['evidence'] for x in node['links']]+[x['evidence'] for x in node['timeline']]:atlas_evidence[(item['id'],item['hash'],item['quote'])]=item
    for topic,comparison in atlas['comparisons'].items():
        if 'verified-sources' not in pages[(root/'설정'/(topic+'.html')).resolve()].ids:errors.append((topic,'missing bottom sources'))
        for panel in comparison['panels']:
            item=panel['evidence'];atlas_evidence[(item['id'],item['hash'],item['quote'])]=item
    for item in atlas_evidence.values():
        document=json.loads((data/'documents'/(item['id']+'.json')).read_text('utf8'))
        if not any(s['anchor']==item['anchor'] and any(r['hash']==item['hash'] and item['quote'] in r['text'] for r in s['rows']) for s in document['sections']):errors.append((item['id'],item['quote'],'atlas source quote/hash mismatch'))
    if not (root/'atlas-data.json').exists():errors.append(('atlas','missing context endpoint'))
    report={'status':'PASS' if not errors else 'FAIL','htmlPages':len(pages),'linksChecked':links,'documents':len(catalog),'verifiedEvidenceLinks':evidence,'verifiedAtlasQuotes':len(atlas_evidence),'originalParagraphsPreserved':original_rows,'errors':errors}
    if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({**report,'errors':errors[:20],'errorCount':len(errors)},ensure_ascii=False));raise SystemExit(bool(errors))
if __name__=='__main__':main()
