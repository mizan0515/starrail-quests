"""Check every added reader, stable source anchor and additive discovery in built HTML.

This is source/HTML QA. Browser filter, focus and layout need a real UI check.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote,urlsplit
from verify_universe_source_site import SourcePage
from verify_discovery import parsed,descendants,check_directory
from verify_handbook_originals import artifact_check

SITE=Path(__file__).resolve().parents[1]
def read(path):return json.loads(path.read_text('utf8'))
class HandbookPage(SourcePage):
 def __init__(self):
  super().__init__();self.source_scope=None;self.source_cursor=0;self.strike_stack=[];self.strikes={}
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='p' and 'original-body' in a.get('class','').split():self.source_scope=a['id'];self.source_cursor=0;self.strikes[a['id']]=[]
  if tag=='s' and self.source_scope:self.strike_stack.append((self.source_scope,self.source_cursor))
  super().handle_starttag(tag,attrs)
 def handle_endtag(self,tag):
  if tag=='s' and self.strike_stack:
   anchor,start=self.strike_stack.pop();assert anchor==self.source_scope
   if start<self.source_cursor:self.strikes[anchor].append([start,self.source_cursor])
  if tag=='p' and self.source_scope:assert not self.strike_stack;self.source_scope=None
  super().handle_endtag(tag)
 def handle_data(self,text):
  if self.source_scope:self.source_cursor+=len(text)
  super().handle_data(text)
def page(path):
 p=HandbookPage();p.feed(path.read_text('utf8'));p.close();assert not p.duplicates and not p.nested_p,path;return p
def address(href):return unquote(urlsplit(href).path).removeprefix('/starrail-quests/')
def verify_document(p,d,added_only=False):
 expected={s['anchor']+'-row-'+str(i):r for s in d['sections'] for i,r in enumerate(s['rows'],1)}
 if not added_only:assert set(p.original)==set(expected),(d['id'],'row membership')
 for anchor,row in expected.items():
  assert p.original.get(anchor)==row['text'],(d['id'],anchor,'display text differs')
  body=p.bodies[anchor];assert body['scene']==anchor.rsplit('-row-',1)[0]
  assert body['row'].get('data-reading-template')=='row' and 'rw-source-body' in p.classes(body['attrs'])
  merged=[]
  for start,end in sorted(p.strikes.get(anchor,[])):
   if merged and merged[-1][1]==start:merged[-1][1]=end
   else:merged.append([start,end])
  assert merged==row.get('strikeRanges',[]),(d['id'],anchor,'source strike intervals differ')
 return len(expected)
def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,default=SITE/'dist');args=a.parse_args();root=args.root
 h=read(SITE/'data/handbook-originals.json');artifact_check(h);docs={d['id']:d for d in h['documents']};rows=0
 endpoint=read(root/'reading-catalog.json');ids=[d['id'] for d in endpoint];assert len(ids)==len(set(ids)) and set(docs)<=set(ids)
 graph=read(root/'reading-data/graph.json');sources={s['id']:s for s in graph['sources']};assert set(docs)<=set(sources)
 all_shards={}
 for d in h['documents']:
  p=page(root/'문서'/(d['id']+'.html'));assert p.h1==[d['title']];rows+=verify_document(p,d)
  assert any(address(link)=='도감.html' for link in p.links),(d['id'],'missing navigation')
  for id in d['sameTitleDocumentIds']:
   if id!=d['id']:assert any(address(link)=='문서/'+id+'.html' for link in p.links),(d['id'],'variant omitted',id)
  if d['sameTitleDocumentIds'][0]!=d['id']:assert d['sameTitleRepresentativeId'] in d['sameTitleDocumentIds']
  shard=sources[d['id']]['blockIndex']
  if shard not in all_shards:all_shards[shard]={s['id']:s for s in read(root/'reading-data'/shard)['sources']}
  blocks=all_shards[shard][d['id']]['blocks']
  actual={b['id']:(b['length'],b['sha256'],b['locator']['stringHash']) for b in blocks}
  expected={s['anchor']+'-row-'+str(i):(len(r['text'].encode('utf-16-le'))//2,hashlib.sha256(r['text'].encode()).hexdigest(),r['hash']) for s in d['sections'] for i,r in enumerate(s['rows'],1)}
  assert actual==expected,(d['id'],'graph source differs')
 for id,sections in h['extensions'].items():
  original=read(SITE/'data/documents'/(id+'.json'));p=page(root/'문서'/(id+'.html'));verify_document(p,original,True);rows+=verify_document(p,{'id':id,'sections':sections},True)
  catalog=next(d for d in endpoint if d['id']==id);assert '외톨이 개구리' in catalog['searchText']
 pearl=page(root/'대상/person-1503.html');assert pearl.h1==['펄']
 pearl_expected={**docs['avatar-1503'],'sections':[{**s,'anchor':'story-text-'+str(s['rows'][0]['story_id'])} for s in docs['avatar-1503']['sections']]};verify_document(pearl,pearl_expected)
 for s in docs['avatar-1503']['sections']:assert any(address(link)=='문서/avatar-1503.html' and unquote(urlsplit(link).fragment)==s['anchor'] for link in pearl.links)
 directory=parsed((root/'도감.html').read_text('utf8'));expected={}
 for g in h['sameTitleGroups']:
  id=g['representativeId'];d=docs[id];expected[id]={'id':id,'name':d['title'],'axis':'','group':d['handbookGroup'],'url':d['url'],'search':d['sections'][0]['rows'][0]['text']}
 expected['book-647']={'id':'book-647','name':read(SITE/'data/documents/book-647.json')['title'],'axis':'','group':'books','url':'문서/book-647.html','search':h['extensions']['book-647'][0]['rows'][0]['text']}
 check_directory(directory,'handbook',expected)
 for node in directory.nodes:
  if 'data-directory-entry' in node['attrs']:assert '<s>' not in node['text'] and '</s>' not in node['text'] and '<s>' not in node['attrs']['data-directory-search']
 assert (root/'pagefind/pagefind.js').exists()
 print(json.dumps({'status':'PASS','newDocumentReaders':len(docs),'addedOriginalRows':rows,'extendedDocuments':len(h['extensions']),'foldedDirectoryCards':len(expected),'pearlStories':5,'graphOriginalsVerified':True,'scope':'All added HTML readers and source graph; browser runtime/layout separate'},ensure_ascii=False))
if __name__=='__main__':main()
