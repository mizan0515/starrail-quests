"""Keep original reading rows and anchors static; share UI and compress metadata.

The audit permits exact expansion back to the pre-optimization HTML/CSS/JS.
Only closed source-details interiors without reading rows or descendant anchors
are compressed. Their outer details and summary remain static. Game inputs,
restoration bundles and source artifacts are never modified.
"""
import argparse
import base64
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from publication_attributes import (CLASS_ALIASES,REVERSE_CLASSES,CLASS_ATTR,
 class_attributes,css_aliases,restore_css,html_styles,search_attributes,
 restore_search,SEARCH_RUNTIME)
CLASS_CONSUMER=re.compile(r'\b(?:'+'|'.join(map(re.escape,CLASS_ALIASES))+r')\b')
RESERVED_CLASS=re.compile(r'\.(?:'+'|'.join(map(re.escape,REVERSE_CLASSES))+r')(?![\w-])')
ALIAS_NAMES=frozenset(REVERSE_CLASSES)

LIMIT=1_000_000_000
REPORT=Path('.codex-work/publication-build-report.json')
CODEC_FILE='pako-inflate-1.0.11.min.js'
CODEC_SHA256='2ca27e9a8dae569cdeac42752ed1aed1afeff7f19282d3cc12c0aaa54a08bc04'
PROOF_TAG=re.compile(r'<script data-pc="([0-9a-f]{64})">__starrailPublicationWrite\("([A-Za-z0-9+/=]+)",([0-9]+)\);</script>')
UI_POOL_TAG=re.compile(r'<script>__sp\(([0-9]+)\);</script>')
ADJACENT_UI_SEQUENCE=re.compile('(?:'+UI_POOL_TAG.pattern+'){2,}')
PROOF_POOL_TAG=re.compile(r'<script>__spr\(([0-9]+)\);</script>')
EXTERNAL_SEQUENCE=re.compile(r'(?:<script\b[^>]*\bsrc="[^"]+"[^>]*></script>|<link\b[^>]*\brel="stylesheet"[^>]*>){2,}')
EXTERNAL_REPLACEMENT=re.compile(r'<script\b[^>]*\bdata-pj\b[^>]*></script>|<link\b[^>]*\bdata-ps\b[^>]*>')
EXTERNAL_MODULE=re.compile(r'<script\b[^>]*\btype="module"[^>]*\bsrc="[^"]+"[^>]*></script>')
MAX_PROOF_SHARD_BYTES=500_000
MAX_UI_SHARD_SLOTS=512
MAX_UI_SHARD_RAW_BYTES=2_000_000
DETAIL_TOKENS=re.compile(r'<script\b[^>]*>[\s\S]*?</script\s*>|<style\b[^>]*>[\s\S]*?</style\s*>|<!--[\s\S]*?-->|</?details\b[^>]*>',re.I)
SUMMARY_PREFIX=re.compile(r'\s*<summary\b[^>]*>[\s\S]*?</summary\s*>',re.I)
READING_PROOF=re.compile(r'<[^>]*\s(?:class\s*=\s*[\"\'][^\"\']*\b(?:original-body|original-row|rw-source-row|reading-scene|reader-paragraph|original-paragraph|original-text|rw-quotation)\b|data-passage\b|data-reading-link\b|data-reading-template\s*=\s*[\"\'](?:row|reader)[\"\'])',re.I)
PROTECTED_PROOF=re.compile(r'<[^>]*\sid\s*=|<(?:script|blockquote)\b|<a\b[^>]*\shref\s*=\s*[\"\']#',re.I)
METADATA_TOKENS=re.compile(r'<!--[\s\S]*?-->|<script\b[^>]*>[\s\S]*?</script\s*>|<style\b[^>]*>[\s\S]*?</style\s*>|</?[A-Za-z][^>]*>',re.I)
VOID_TAGS=set('area base br col embed hr img input link meta param source track wbr'.split())
PROOF_RUNTIME='''"use strict";
// Only trusted, build-generated metadata interiors are passed to this parser.
// This classic script runs synchronously while the document parser is open.
window.__starrailPublicationWrite=function(encoded,expectedBytes){
 var binary=atob(encoded),bytes=new Uint8Array(binary.length);
 for(var i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
 var raw=pako.ungzip(bytes);
 if(raw.length!==expectedBytes)throw new Error("Publication proof byte length differs");
 document.write(new TextDecoder("utf-8",{fatal:true}).decode(raw));
};
'''
POOL_RUNTIME='''
window.__starrailPublicationDecode=function(encoded,expectedBytes){
 var binary=atob(encoded),bytes=new Uint8Array(binary.length);
 for(var i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
 var raw=pako.ungzip(bytes);
 if(raw.length!==expectedBytes)throw new Error("Publication pool byte length differs");
 return new TextDecoder("utf-8",{fatal:true}).decode(raw);
};
window.__starrailPublicationLoadProofs=function(start,encoded,expectedBytes,sizes){
 var rows=JSON.parse(__starrailPublicationDecode(encoded,expectedBytes));
 if(!Number.isSafeInteger(start)||start<0||!Array.isArray(rows)||rows.length!==sizes.length)throw new Error("Invalid proof shard");
 for(var i=0;i<rows.length;i++){
  if(typeof rows[i]!=="string"||new TextEncoder().encode(rows[i]).length!==sizes[i]||Object.prototype.hasOwnProperty.call(__starrailPublicationProofs,start+i))throw new Error("Invalid or duplicate proof slot");
 }
 for(var i=0;i<rows.length;i++)__starrailPublicationProofs[start+i]=rows[i];
};
window.__starrailPublicationProofs=Object.create(null);
window.__spr=function(id){
 if(!Number.isSafeInteger(id)||!Object.prototype.hasOwnProperty.call(__starrailPublicationProofs,id))throw new Error("Unknown publication proof slot");
 document.write(__starrailPublicationProofs[id]);
};
'''

def encoded_array(rows):
 raw=json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode('utf8')
 return raw,base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode('ascii')

def ui_storage_key(entry):
 _,row=entry
 owners=tuple(re.findall(r'data-reading-mission="([^"]+)"',row))
 template=re.sub(r'<a\b[^>]*data-current-reader-title[^>]*>[\s\S]*?</a>','<current-reader>',row)
 template=UI_POOL_TAG.sub('<ui-slot>',template)
 template=re.sub(r'[0-9a-f]{16,64}','<hash>',template)
 return owners,template,row

def pooled_runtime(rows):
 # Legacy indexed runtime retained for existing receipt/codec compatibility.
 pairs=sorted(enumerate(rows),key=ui_storage_key)
 raw,encoded=encoded_array(pairs)
 return PROOF_RUNTIME+POOL_RUNTIME+SEARCH_RUNTIME+'''window.__starrailPublicationLoadUI=function(pairs,count){
 if(!Number.isSafeInteger(count)||count<0||!Array.isArray(pairs)||pairs.length!==count)throw new Error("Invalid UI pool count");
 var rows=new Array(count);
 for(var i=0;i<pairs.length;i++){
  var pair=pairs[i];
  if(!Array.isArray(pair)||pair.length!==2||!Number.isSafeInteger(pair[0])||pair[0]<0||pair[0]>=count||typeof pair[1]!=="string"||Object.prototype.hasOwnProperty.call(rows,pair[0]))throw new Error("Invalid or duplicate UI slot");
  rows[pair[0]]=pair[1];
 }
 window.__starrailPublicationUI=rows;
};
'''+f'__starrailPublicationLoadUI(JSON.parse(__starrailPublicationDecode("{encoded}",{len(raw)})),{len(rows)});\n'+'''window.__sp=function(id){
 if(!Number.isSafeInteger(id)||id<0||id>=__starrailPublicationUI.length||typeof __starrailPublicationUI[id]!=="string")throw new Error("Unknown publication UI slot");
 document.write(__starrailPublicationUI[id]);
};
'''

def ui_shards(rows):
 """Keep b0 physical pair order, original slots and a2MB decoded bound."""
 require(isinstance(rows,list)and all(isinstance(row,str)for row in rows),'Invalid UI pool')
 records=[];entries=[];slots=[];size=2
 def flush():
  nonlocal entries,slots,size
  if not entries:return
  raw=b'['+b','.join(entries)+b']';require(len(raw)==size<=MAX_UI_SHARD_RAW_BYTES,'UI raw shard bound differs')
  encoded=base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode('ascii');identifier=len(records)
  body=f'__starrailPublicationLoadUIShard({identifier},"{encoded}",{len(raw)},{len(slots)});\n'
  records.append({'id':identifier,'count':len(slots),'slots':slots,'rawBytes':len(raw),'rawSha256':digest(raw),'payload':encoded,'body':body})
  entries=[];slots=[];size=2
 for slot,row in sorted(enumerate(rows),key=ui_storage_key):
  require(isinstance(row,str),'UI pool contains non-string slot')
  entry=json.dumps([slot,row],ensure_ascii=False,separators=(',',':')).encode('utf8')
  require(len(entry)+2<=MAX_UI_SHARD_RAW_BYTES,'One UI slot exceeds decoded shard bound')
  if entries and(len(entries)==MAX_UI_SHARD_SLOTS or size+len(entry)+1>MAX_UI_SHARD_RAW_BYTES):flush()
  size+=len(entry)+(1 if entries else 0);entries.append(entry);slots.append(slot)
 flush();return records

def share_adjacent_ui(text,pool_ui,counts):
 """Share only contiguous generated UI calls, using the existing parser wire.

 Original rows and parser boundaries remain unchanged. Call this once after
 the first page pass so any new composite rows follow the original slots.
 """
 def share(match):
  # A no-JS suffix belongs to the immediately preceding original slot.
  # Retain that parser boundary so the existing strict inverse stays exact.
  if text[match.end():match.end()+10]=='<noscript>':return match[0]
  original=match[0];replacement=pool_ui(original)
  saved=len(original.encode('utf8'))-len(replacement.encode('utf8'))
  require(saved>0,'Adjacent UI sharing did not reduce the parser calls')
  counts['sharedAdjacentUIRuns']+=1
  counts['sharedAdjacentUICalls']+=len(list(UI_POOL_TAG.finditer(original)))
  counts['sharedAdjacentUIBytesSaved']+=saved
  return replacement
 return ADJACENT_UI_SEQUENCE.sub(share,text)

def ui_closure(rows):
 """Reject cycles/missing slots, including unused nodes; cache transitive slots."""
 require(isinstance(rows,list)and all(isinstance(row,str)for row in rows),'Invalid UI pool')
 graph=[tuple(sorted({int(m[1])for m in UI_POOL_TAG.finditer(row)}))for row in rows]
 colors=[0]*len(rows);memo=[None]*len(rows);depths=[0]*len(rows)
 def visit(slot,path=()):
  require(0<=slot<len(rows),'Unknown nested UI slot')
  require(colors[slot]!=1,'Cyclic UI pool nesting')
  if colors[slot]==2:return memo[slot]
  require(len(path)<15,'Excessive UI pool nesting')
  colors[slot]=1;result={slot};depth=0
  for child in graph[slot]:result.update(visit(child,path+(slot,)));depth=max(depth,depths[child]+1)
  require(depth<15,'Excessive UI pool nesting');depths[slot]=depth
  colors[slot]=2;memo[slot]=frozenset(result);return memo[slot]
 for slot in range(len(rows)):visit(slot)
 def required(text):
  result=set()
  for match in UI_POOL_TAG.finditer(text):result.update(visit(int(match[1])))
  return result
 return required

def sparse_runtime(total_slots,urls):
 require(type(total_slots)is int and 0<=total_slots<=2**32-1 and isinstance(urls,list)and all(isinstance(url,str)for url in urls),'Invalid sparse UI runtime manifest')
 manifest=json.dumps(urls,ensure_ascii=False,separators=(',',':'))
 return PROOF_RUNTIME+POOL_RUNTIME+SEARCH_RUNTIME+f'window.__starrailPublicationUI=new Array({total_slots});\nwindow.__starrailPublicationUIURLs={manifest};\n'+'''window.__starrailPublicationUIShardLoaded=Object.create(null);
window.__starrailPublicationLoadUIShard=function(id,encoded,expectedBytes,count){
 if(!Number.isSafeInteger(id)||id<0||id>=__starrailPublicationUIURLs.length||Object.prototype.hasOwnProperty.call(__starrailPublicationUIShardLoaded,id)||!Number.isSafeInteger(expectedBytes)||expectedBytes<2||expectedBytes>2000000||!Number.isSafeInteger(count)||count<1||count>512||typeof encoded!=="string")throw new Error("Invalid UI shard");
 var pairs=JSON.parse(__starrailPublicationDecode(encoded,expectedBytes)),seen=Object.create(null);
 if(!Array.isArray(pairs)||pairs.length!==count)throw new Error("Invalid UI shard count");
 for(var i=0;i<pairs.length;i++){
  var pair=pairs[i];
  if(!Array.isArray(pair)||pair.length!==2||!Number.isSafeInteger(pair[0])||pair[0]<0||pair[0]>=__starrailPublicationUI.length||typeof pair[1]!=="string"||Object.prototype.hasOwnProperty.call(seen,pair[0])||Object.prototype.hasOwnProperty.call(__starrailPublicationUI,pair[0]))throw new Error("Invalid or duplicate UI slot");
  seen[pair[0]]=true;
 }
 for(var i=0;i<pairs.length;i++)__starrailPublicationUI[pairs[i][0]]=pairs[i][1];
 __starrailPublicationUIShardLoaded[id]=true;
};
window.__sp=function(id){
 if(!Number.isSafeInteger(id)||id<0||id>=__starrailPublicationUI.length||typeof __starrailPublicationUI[id]!=="string")throw new Error("Unknown publication UI slot");
 document.write(__starrailPublicationUI[id]);
};
window.__starrailPublicationSelectUI=function(value){
 if(typeof value!=="string"||value!==""&&!/^(?:0|[1-9][0-9]*)(?:,(?:0|[1-9][0-9]*))*$/.test(value))throw new Error("Invalid selected UI shards");
 var ids=value===""?[]:value.split(",").map(Number);
 for(var i=0;i<ids.length;i++)if(!Number.isSafeInteger(ids[i])||ids[i]<0||ids[i]>=__starrailPublicationUIURLs.length||i>0&&ids[i]<=ids[i-1])throw new Error("Unknown or unsorted UI shard");
 for(var i=0;i<ids.length;i++)document.write('<script src="'+__starrailPublicationUIURLs[ids[i]]+'"></scr'+'ipt>');
};
__starrailPublicationSelectUI(document.currentScript.getAttribute("data-pc-runtime"));
'''

def proof_shards(rows):
 """At most 128 interiors and 0.5 MB of JS per parser-loaded shard."""
 shards=[];at=0
 while at<len(rows):
  count=min(128,len(rows)-at)
  while True:
   chunk=rows[at:at+count];raw,encoded=encoded_array(chunk);sizes=[len(row.encode('utf8'))for row in chunk]
   body=f'__starrailPublicationLoadProofs({at},"{encoded}",{len(raw)},{json.dumps(sizes,separators=(",",":"))});\n'
   if len(body.encode())<=MAX_PROOF_SHARD_BYTES:break
   require(count>1,'One proof interior exceeds the shared shard byte limit');count=max(1,count//2)
  shards.append({'start':at,'count':count,'rawBytes':len(raw),'rawSha256':digest(raw),'payload':encoded,'sizes':sizes,'body':body})
  at+=count
 return shards
RESTORATION_ONLY={
 'mission-dialogue-supplements.json','dialogue-contexts.json',
 'handbook-originals.json','official-talk-library.json','universe-catalog.json',
 'universe-source-records.json','official-universe-texts.json','catalog.json',
 'official-video-captions.json','official-mission-talks.json',
}
SCOPE=re.compile(r'\bastro-[a-z0-9]{8}\b')
TAG={k:re.compile(r'<'+k+r'\b([^>]*)>(.*?)</'+k+r'>',re.S) for k in ('style','script')}
FRAGMENTS=[
 re.compile(r'<section class="quest-reading-nav"(?=[\s>])[\s\S]*?</section>'),
 re.compile(r'<p\b[^>]*\bdata-publication-ui="source-context"[^>]*>[\s\S]*?</p>'),
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

def quest_navigation_ui(fragment):
 """Share declared navigation metadata while keeping reading bodies outside it."""
 parser=OpeningTag();parser.feed(fragment.split('>',1)[0]+'>')
 if 'data-quest-reading-nav' not in parser.attrs or 'data-pagefind-ignore' not in parser.attrs:return False
 if READING_PROOF.search(fragment) or re.search(r'<(?:blockquote|pre|code|script|style|h[1-6])\b',fragment,re.I):return False
 return len(re.findall(r'<section\b',fragment,re.I))==1 and len(re.findall(r'</section\s*>',fragment,re.I))==1

def source_context_ui(fragment):
 """Only explicitly declared reader context; original rows/anchors stay static."""
 parser=OpeningTag();parser.feed(fragment.split('>',1)[0]+'>');attrs=parser.attrs
 return (attrs.get('data-publication-ui')=='source-context' and 'muted' in attrs.get('class','').split()
         and not READING_PROOF.search(fragment) and not PROTECTED_PROOF.search(fragment)
         and not re.search(r'<(?:a|details|summary|pre|code|blockquote|script|style)\b',fragment,re.I))

def digest(body):return hashlib.sha256(body).hexdigest()
def require(condition,message):
 if not condition:raise ValueError(message)
def text_files(root):return sorted(p for p in root.rglob('*') if p.suffix in ('.html','.css','.js') and '_shared' not in p.parts and 'pagefind' not in p.parts)
def total(root):return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
def write_json(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),'utf8')

class OpeningTag(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=False);self.attrs={}
 def handle_starttag(self,tag,attrs):self.attrs=dict(attrs)

def metadata_segments(s,start,end):
 """Keep protected children static; only declared technical metadata is eligible.

 A pre/code opening tag (including its ID) and closing tag stay static. Reading
 subtrees, summaries, links, scripts and quotations block all their descendants.
 This deliberately does not compress arbitrary prose within a source disclosure.
 """
 stack=[];ranges=[]
 for token in METADATA_TOKENS.finditer(s,start,end):
  text=token[0];lower=text.lower()
  if lower.startswith(('<!--','<script','<style')):continue
  match=re.match(r'</?([A-Za-z][\w:-]*)',text);tag=match[1].lower()
  if lower.startswith('</'):
   # Generated HTML is explicit for these nodes; mismatches fail closed.
   if not stack or stack[-1][0]!=tag:return []
   _,content,blocked,technical=stack.pop()
   if technical and not blocked:
    body=s[content:token.start()]
    if len(body.encode('utf8'))>=512 and not PROTECTED_PROOF.search(body) and not READING_PROOF.search(body):ranges.append((content,token.start()))
  elif tag not in VOID_TAGS and not text.rstrip().endswith('/>'):
   blocked=(bool(stack) and stack[-1][2]) or bool(READING_PROOF.search(text)) or tag in ('a','summary','blockquote','noscript')
   declared=OpeningTag();declared.feed(text)
   technical=tag in ('pre','code') or (tag=='dl' and declared.attrs.get('data-publication-metadata')=='technical')
   stack.append((tag,token.end(),blocked,technical))
 return ranges if not stack else []

def proof_interiors(s):
 """Only balanced, closed source disclosures; outer IDs/summary stay static.

 Script/style/comment tokens are skipped before details balancing. Descendant
 IDs and reading rows/return links are never moved into compressed metadata.
 """
 stack=[];ranges=[]
 for token in DETAIL_TOKENS.finditer(s):
  text=token[0];lower=text.lower()
  if lower.startswith('</details'):
   require(stack,'Unbalanced generated details closing tag')
   opening,start,eligible=stack.pop()
   if eligible:
    summary=SUMMARY_PREFIX.match(s,start,token.start())
    if summary:
     a,b=summary.end(),token.start();body=s[a:b]
     if len(body.encode('utf8'))>=512:
      if not PROTECTED_PROOF.search(body) and not READING_PROOF.search(body):ranges.append((a,b))
      else:ranges.extend(metadata_segments(s,a,b))
  elif lower.startswith('<details'):
   parser=OpeningTag();parser.feed(text);attrs=parser.attrs
   eligible='source-details' in attrs.get('class','').split() and 'open' not in attrs and not text.rstrip().endswith('/>')
   stack.append((token.start(),token.end(),eligible))
 require(not stack,'Unbalanced generated details opening tag')
 # Prefer an eligible outer interior to a nested candidate; never overlap.
 selected=[]
 for a,b in sorted(ranges,key=lambda r:(r[0],-r[1])):
  if selected and a<selected[-1][1]:continue
  selected.append((a,b))
 return selected

def compress_proofs(s,records):
 ranges=proof_interiors(s);pieces=[];at=0;count=0;saved=0
 for a,b in ranges:
  raw=s[a:b].encode('utf8');packed=gzip.compress(raw,compresslevel=9,mtime=0);encoded=base64.b64encode(packed).decode('ascii');key=digest(raw)
  replacement=f'<script data-pc="{key}">__starrailPublicationWrite("{encoded}",{len(raw)});</script>'
  if len(replacement.encode())>=len(raw):continue
  pieces.extend((s[at:a],replacement));at=b;count+=1;saved+=len(raw)-len(replacement.encode())
  record={'rawBytes':len(raw),'gzipBytes':len(packed),'encoding':'gzip+base64/UTF-8','occurrences':0}
  previous=records.setdefault(key,record)
  require(all(previous[k]==record[k]for k in ('rawBytes','gzipBytes','encoding')),'Proof hash collision')
  previous['occurrences']+=1
 pieces.append(s[at:]);return ''.join(pieces),count,saved

def expand_proofs(s,records):
 def expand(m):
  key,encoded,size=m.groups();require(key in records,'Unknown compressed proof')
  packed=base64.b64decode(encoded,validate=True);raw=gzip.decompress(packed)
  require(len(raw)==int(size)==records[key]['rawBytes'] and len(packed)==records[key]['gzipBytes'] and digest(raw)==key,'Compressed proof differs')
  return raw.decode('utf8',errors='strict')
 return PROOF_TAG.sub(expand,s)

def optimize(root,base,report_path):
 require(not (root/'_shared').exists(),'Already optimized: rebuild HTML first')
 before=total(root);files=text_files(root);originals={};scopes=set();aliases=set();pools={k:Counter() for k in TAG};references={name:False for name in RESTORATION_ONLY}
 # Two bounded passes avoid retaining the complete 1.5 GB HTML in memory.
 def scan(file):
  raw=file.read_bytes();s=raw.decode('utf8');tags={k:[] for k in TAG}
  for attribute in CLASS_ATTR.finditer(s):require(not(set(attribute[3].split())&ALIAS_NAMES),'Presentation class alias collision')
  require(not any(f':is(.{name},.{alias})' in s for name,alias in CLASS_ALIASES.items()),'CSS presentation alias namespace collision')
  if file.suffix=='.css':require(not RESERVED_CLASS.search(s),'Presentation CSS alias collision')
  if file.suffix=='.js':require(not CLASS_CONSUMER.search(s),'Presentation class has a generated client-script consumer '+str(file))
  if file.suffix=='.html':
   require(not re.search(r'<script>\s*__(?:sp|spr|ss|sl)\(|<script\b[^>]*\bdata-(?:pc|pr-shard|search-pool)(?:=|-library|-runtime)',s),'Publication pool namespace already exists')
   for kind,pattern in TAG.items():
    for m in pattern.finditer(s):
     if kind=='script' and ('src=' in m[1] or 'application/' in m[1]):continue
     if kind=='script':require(not CLASS_CONSUMER.search(m[2]),'Presentation class has an inline client-script consumer '+str(file))
     else:require(not RESERVED_CLASS.search(m[2]),'Presentation inline CSS alias collision')
     tags[kind].append((m[1],m[2]))
  return digest(raw),SCOPE.findall(s),re.findall(r'\b_(?:[A-Za-z0-9]|q[A-Za-z0-9]+)\b',s),[name for name in references if name in s],tags
 # Bound pending reads to64files; aggregation and all later writes remain serial.
 with ThreadPoolExecutor(max_workers=4)as readers:
  for start in range(0,len(files),64):
   for position,(file,result)in enumerate(zip(files[start:start+64],readers.map(scan,files[start:start+64])),start):
    checksum,found_scopes,found_aliases,found_refs,tags=result
    originals[file.relative_to(root).as_posix()]=checksum;scopes.update(found_scopes);aliases.update(found_aliases)
    for name in found_refs:references[name]=True
    for kind,values in tags.items():pools[kind].update(values)
    if position%5000==0:print(f'Publication scan {position+1}/{len(files)}',flush=True)
 alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
 candidates=['_'+letter for letter in alphabet if '_'+letter not in aliases]
 # Existing short tokens in any HTML, CSS or script are reserved, including prose.
 mapping={scope:(candidates[i] if i<len(candidates) else '_q'+str(i)) for i,scope in enumerate(sorted(scopes))}
 require(not(set(mapping.values())&aliases),'Generated scope alias collision')
 reverse_scopes={value:key for key,value in mapping.items()}
 alias_pattern=re.compile(r'\b(?:'+'|'.join(map(re.escape,reverse_scopes))+r')\b')
 shared=root/'_shared';shared.mkdir();assets={};replacements={};counts=Counter();proof_records={};proof_tags=None;proof_saved=0;codec_records={};ui_records={};ui_runtime=None
 ui_rows=[];ui_index={};proof_rows=[];proof_index={};page_proofs={};pool_pages=[];search_records={};page_search={}
 def pool_ui(body):
  if body not in ui_index:ui_index[body]=len(ui_rows);ui_rows.append(body)
  counts['uiPoolCalls']+=1
  return f'<script>__sp({ui_index[body]});</script>'
 def asset(body,suffix,kind):
  raw=body.encode();key=digest(raw)[:20]+suffix;target=shared/key
  if key in assets:require(assets[key]['sha256']==digest(raw),'Asset hash collision')
  else:target.write_bytes(raw);assets[key]={'sha256':digest(raw),'kind':kind}
  return f'{base}/_shared/{key}'
 def remember(replacement,original):
  require(replacement not in replacements or replacements[replacement]==original,'Conflicting replacement')
  replacements[replacement]=original;return replacement
 def codec_tags():
  nonlocal proof_tags,ui_runtime
  if proof_tags is None:
   vendor_source=Path(__file__).resolve().parents[1]/'public/_publication'
   vendor=root/'_publication';vendor.mkdir(exist_ok=True)
   for name in (CODEC_FILE,'pako-LICENSE.txt','pako-ZLIB-LICENSE.txt'):
    source=vendor_source/name;require(source.is_file(),'Publication codec/license missing '+name)
    raw=source.read_bytes()
    if name==CODEC_FILE:require(digest(raw)==CODEC_SHA256,'Pinned pako codec differs')
    target=vendor/name
    if target.exists():require(target.read_bytes()==raw,'Built codec/license differs '+name)
    else:target.write_bytes(raw)
    codec_records[name]={'sha256':digest(raw),'bytes':len(raw)}
   runtime=sparse_runtime(len(ui_rows),[ui_records[str(i)]['url']for i in range(len(ui_records))])
   url=asset(runtime,'.js','proof-runtime')
   ui_runtime={'url':url,'sha256':digest(runtime.encode()),'bytes':len(runtime.encode()),'totalSlots':len(ui_rows),'maxSlots':MAX_UI_SHARD_SLOTS,'maxRawBytes':MAX_UI_SHARD_RAW_BYTES,'loader':'indexed-local-ui.v1'}
   proof_tags=f'<script src="{base}/_publication/{CODEC_FILE}" data-pc-library></script><script src="{url}" data-pc-runtime></script>'
  return proof_tags
 fallback=f'<noscript><nav aria-label="자료집 탐색"><a href="{base}/index.html">자료집 탐색</a></nav></noscript>'
 footer_fallback=f'<noscript><small>비공식 자료집 · 게임 콘텐츠 권리: HoYoverse 등 해당 권리자 <a href="{base}/자료안내.html">자료 안내</a> · <a href="https://github.com/mizan0515/starrail-quests/tree/main/src/lib/reading-kit/cva">CVA 소스 · GPLv3</a></small></noscript>'
 for position,file in enumerate(files):
  s=file.read_bytes().decode('utf8')
  if mapping:s=SCOPE.sub(lambda m:mapping[m[0]],s)
  if file.suffix=='.css':s=css_aliases(s)
  if file.suffix=='.html':
   s=html_styles(s,css_aliases)
   require(not re.search(r'<script>\s*__(?:sp|spr)\(',s),'Publication pool namespace already exists')
   # Identical external modules execute once per URL. Keep any module that
   # originally has multiple occurrences on this page inline.
   module_counts=Counter((m[1],m[2]) for m in TAG['script'].finditer(s) if 'type="module"' in m[1])
   for kind,pattern in TAG.items():
    def extract(m):
     attrs,body=m[1],m[2]
     if kind=='script' and ('src=' in attrs or 'application/' in attrs or len(body)<128 or 'import.meta' in body):return m[0]
     original_body=alias_pattern.sub(lambda m:reverse_scopes[m[0]],body) if reverse_scopes else body
     if kind=='style':original_body=restore_css(original_body)
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
     if fragment.startswith('<section class="quest-reading-nav"') and not quest_navigation_ui(fragment):return fragment
     if 'data-publication-ui=' in fragment and not source_context_ui(fragment):return fragment
     # A classic, parser-blocking script inserts the exact original subtree
     # in its original parser position. Its existing scripts retain order.
     replacement=pool_ui(fragment)
     if fragment.startswith('<header'):replacement+=fallback
     if fragment.startswith('<footer'):replacement+=footer_fallback
     counts['fragment']+=1;return remember(replacement,fragment)
    s=pattern.sub(extract_fragment,s)
   require(not re.search(r'<script\b[^>]*\bdata-pc(?:=|-library|-runtime)',s),'Compressed proof marker already exists')
   s,compressed,saved=compress_proofs(s,proof_records)
   if compressed:
    ids=[]
    def share_proof(match):
     key,encoded,size=match.groups();raw=gzip.decompress(base64.b64decode(encoded,validate=True))
     require(digest(raw)==key and len(raw)==int(size),'Generated compressed proof differs')
     if key not in proof_index:proof_index[key]=len(proof_rows);proof_rows.append(raw.decode('utf8',errors='strict'))
     slot=proof_index[key];ids.append(slot)
     return f'<script>__spr({slot});</script>'
    s=PROOF_TAG.sub(share_proof,s);page_proofs[file.relative_to(root).as_posix()]=sorted(set(ids))
    counts['compressedProof']+=compressed;counts['compressedProofPages']+=1;proof_saved+=saved
   def share_shell(match):
    counts['sharedShellRuns']+=1
    return pool_ui(match[0])
   s=EXTERNAL_SEQUENCE.sub(share_shell,s)
   # Standalone generated UI scripts/styles retain their exact external tags.
   # Pooling them changes only their representation and parser insertion call.
   s=EXTERNAL_REPLACEMENT.sub(lambda m:pool_ui(m[0]) if m[0] in replacements else m[0],s)
   def share_module(match):
    parser=OpeningTag();parser.feed(match[0]);url=parser.attrs.get('src','')
    if not url.startswith((f'{base}/_astro/',f'{base}/_shared/')):return match[0]
    counts['sharedStandaloneModules']+=1;return pool_ui(match[0])
   s=EXTERNAL_MODULE.sub(share_module,s)
   s=class_attributes(s,CLASS_ALIASES)
   s,search_loader,search_count=search_attributes(s,search_records)
   if search_loader:page_search[file.relative_to(root).as_posix()]=search_loader;counts['searchAttributes']+=search_count
   if UI_POOL_TAG.search(s) or PROOF_POOL_TAG.search(s) or search_loader:pool_pages.append(file)
  file.write_text(s,'utf8',newline='')
  if position%5000==0:print(f'Publication shared UI {position+1}/{len(files)}',flush=True)
 # Keep the original UI slot census intact, then append shared call runs.
 # The existing transitive closure loads every nested slot before parsing.
 for position,file in enumerate(pool_pages):
  original=file.read_bytes().decode('utf8')
  compact=share_adjacent_ui(original,pool_ui,counts)
  if compact!=original:file.write_text(compact,'utf8',newline='')
  if position%5000==0:print(f'Publication adjacent UI {position+1}/{len(pool_pages)}',flush=True)
 required_ui=ui_closure(ui_rows);ui_slot_shard={}
 for record in ui_shards(ui_rows):
  body=record.pop('body');record['url']=asset(body,'.js','ui-shard');record['assetSha256']=digest(body.encode());record['assetBytes']=len(body.encode())
  ui_records[str(record['id'])]=record
  for slot in record['slots']:ui_slot_shard[slot]=record['id']
 # Nearby equal prefixes improve gzip packing while retaining exact rows.
 order=sorted(range(len(proof_rows)),key=lambda slot:proof_rows[slot])
 proof_remap={old:new for new,old in enumerate(order)}
 proof_rows=[proof_rows[old] for old in order]
 require(not any(PROOF_POOL_TAG.search(row)for row in proof_rows),'Nested proof pool calls are not supported')
 shards=proof_shards(proof_rows);shard_for={};shard_records={}
 for shard_id,record in enumerate(shards):
  body=record.pop('body');url=asset(body,'.js','proof-shard');record['url']=url;record['assetSha256']=digest(body.encode())
  shard_records[str(shard_id)]=record
  for slot in range(record['start'],record['start']+record['count']):shard_for[slot]=shard_id
 if pool_pages:
  tags=codec_tags()
  for position,file in enumerate(pool_pages):
   s=file.read_bytes().decode('utf8');heads=list(re.finditer(r'<head\b[^>]*>',s,re.I));require(len(heads)==1,'Pooled page requires one head')
   s=PROOF_POOL_TAG.sub(lambda match:f'<script>__spr({proof_remap[int(match[1])]});</script>',s)
   selected=sorted({ui_slot_shard[slot]for slot in required_ui(s)})
   page_tags=tags.replace('data-pc-runtime','data-pc-runtime="'+','.join(map(str,selected))+'"')
   imports=''.join(f'<script src="{shard_records[str(shard_id)]["url"]}" data-pr-shard="{shard_id}"></script>'for shard_id in sorted({shard_for[proof_remap[slot]]for slot in page_proofs.get(file.relative_to(root).as_posix(),[])}))
   head=heads[0];at=head.end()
   # Keep the existing encoding declaration at the beginning of the head.
   charset=re.match(r'\s*<meta\b[^>]*\bcharset\s*=[^>]*>',s[at:],re.I)
   if charset:at+=charset.end()
   s=s[:at]+page_tags+imports+page_search.get(file.relative_to(root).as_posix(),'')+s[at:];file.write_text(s,'utf8',newline='')
   if position%5000==0:print(f'Publication pools {position+1}/{len(pool_pages)}',flush=True)
 # Only known build-time mirrors can be omitted. Runtime JSON, linked raw
 # dialogue JSON, and every reading-data shard stay available.
 removed={}
 for name,used in references.items():
  file=root/name
  if not used and file.exists():
   removed[name]={'bytes':file.stat().st_size,'sha256':digest(file.read_bytes())};file.unlink()
 after=total(root)
 report={'schema':'starrail-publication-dedup.v3','base':base,'beforeBytes':before,'afterBytes':after,'limitBytes':LIMIT,'scopes':mapping,'originalFiles':originals,'assets':assets,'replacements':replacements,'removedBuildMirrors':removed,'counts':dict(counts),'compressedProofs':proof_records,'proofCodecTags':proof_tags,'proofCodecFiles':codec_records,'proofCompressionSavedBytes':proof_saved,'uiPool':ui_rows,'proofPool':[{'sha256':digest(row.encode()),'rawBytes':len(row.encode()),'shard':shard_for[slot]}for slot,row in enumerate(proof_rows)],'proofShards':shard_records,'proofCodec':{'package':'pako','version':'1.0.11','license':'MIT AND Zlib','file':CODEC_FILE,'sha256':CODEC_SHA256,'mode':'gzip+base64, synchronous classic parser script; static outer details/summary/anchors and original dialogue'} }
 report['presentationClasses']=CLASS_ALIASES;report['searchPagePools']=search_records
 if pool_pages:report['uiShards']=ui_records;report['uiRuntime']=ui_runtime
 write_json(report_path,report)
 print(json.dumps({'status':'PASS' if after<=LIMIT else 'OVER_LIMIT','beforeBytes':before,'afterBytes':after,'savedBytes':before-after,'removedMirrors':list(removed),'sharedAssets':len(assets),'counts':dict(counts)},ensure_ascii=False),flush=True)
 require(after<=LIMIT,'Published site exceeds 1 GB')

def expansion_function(report):
 require(report.get('presentationClasses',CLASS_ALIASES)==CLASS_ALIASES,'Presentation class receipt differs')
 local_ui='uiShards'in report;ui_slot_shard={};required_ui=None
 if local_ui:
  records=report['uiShards'];rows=report.get('uiPool',[]);required_ui=ui_closure(rows)
  require(isinstance(records,dict)and set(records)=={str(i)for i in range(len(records))},'UI shard IDs are not dense')
  urls=[]
  for identifier in range(len(records)):
   record=records[str(identifier)]
   require(set(record)=={'id','count','slots','rawBytes','rawSha256','payload','url','assetSha256','assetBytes'},'UI shard receipt fields differ')
   require(type(record['id'])is int and record['id']==identifier and type(record['count'])is int and 1<=record['count']<=MAX_UI_SHARD_SLOTS,'UI shard ID/count differs')
   require(type(record['rawBytes'])is int and 2<=record['rawBytes']<=MAX_UI_SHARD_RAW_BYTES,'UI shard raw byte bound differs')
   require(isinstance(record['slots'],list)and len(record['slots'])==record['count']and all(type(slot)is int and 0<=slot<len(rows)for slot in record['slots']),'UI shard slot list differs')
   raw=gzip.decompress(base64.b64decode(record['payload'],validate=True))
   require(len(raw)==record['rawBytes']and digest(raw)==record['rawSha256'],'UI shard payload hash/bytes differ')
   pairs=json.loads(raw.decode('utf8',errors='strict'))
   require(isinstance(pairs,list)and len(pairs)==record['count'],'UI shard pair count differs')
   for slot,pair in zip(record['slots'],pairs):
    require(isinstance(pair,list)and len(pair)==2 and type(pair[0])is int and pair[0]==slot and isinstance(pair[1],str)and pair[1]==rows[slot]and slot not in ui_slot_shard,'UI shard original slot/string or uniqueness differs')
    ui_slot_shard[slot]=identifier
   body=f'__starrailPublicationLoadUIShard({identifier},"{record["payload"]}",{record["rawBytes"]},{record["count"]});\n'.encode()
   require(len(body)==record['assetBytes']and digest(body)==record['assetSha256'],'UI shard asset receipt differs')
   require(record['url']==report['base']+'/_shared/'+record['assetSha256'][:20]+'.js','UI shard content-hash URL differs')
   asset=report.get('assets',{}).get(record['url'].rsplit('/',1)[1]);require(asset is not None and asset['sha256']==record['assetSha256']and asset['kind']=='ui-shard','UI shard shared asset hash differs')
   urls.append(record['url'])
  require(set(ui_slot_shard)==set(range(len(rows))),'UI shard slot coverage differs')
  runtime=report.get('uiRuntime');body=sparse_runtime(len(rows),urls).encode()
  expected={'url':report['base']+'/_shared/'+digest(body)[:20]+'.js','sha256':digest(body),'bytes':len(body),'totalSlots':len(rows),'maxSlots':MAX_UI_SHARD_SLOTS,'maxRawBytes':MAX_UI_SHARD_RAW_BYTES,'loader':'indexed-local-ui.v1'}
  require(runtime==expected,'UI runtime manifest/loader receipt differs')
  asset=report.get('assets',{}).get(runtime['url'].rsplit('/',1)[1]);require(asset is not None and asset['sha256']==runtime['sha256']and asset['kind']=='proof-runtime','UI runtime shared asset differs')
  expected_tags=f'<script src="{report["base"]}/_publication/{CODEC_FILE}" data-pc-library></script><script src="{runtime["url"]}" data-pc-runtime></script>'
  require(report.get('proofCodecTags')==expected_tags,'UI bootstrap tag receipt differs')
 replacements=report['replacements']
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
 decoded_shards={}
 def proof(slot):
  pool=report.get('proofPool',[]);require(0<=slot<len(pool),'Unknown publication proof slot')
  record=pool[slot];shard_id=str(record['shard']);require(shard_id in report['proofShards'],'Unknown proof shard')
  if shard_id not in decoded_shards:
   shard=report['proofShards'][shard_id];raw=gzip.decompress(base64.b64decode(shard['payload'],validate=True))
   require(len(raw)==shard['rawBytes'] and digest(raw)==shard['rawSha256'],'Proof shard payload differs')
   rows=json.loads(raw.decode('utf8',errors='strict'));require(isinstance(rows,list)and len(rows)==shard['count']==len(shard['sizes']),'Proof shard count differs')
   for local,row in enumerate(rows):
    require(isinstance(row,str),'Proof shard contains a non-string slot');encoded=row.encode('utf8');original=pool[shard['start']+local]
    require(len(encoded)==shard['sizes'][local]==original['rawBytes']and digest(encoded)==original['sha256']and str(original['shard'])==shard_id,'Proof shard slot differs')
   decoded_shards[shard_id]=rows
  offset=slot-report['proofShards'][shard_id]['start'];require(0<=offset<len(decoded_shards[shard_id]),'Proof slot outside shard')
  return decoded_shards[shard_id][offset]
 ui_suffixes={r[UI_POOL_TAG.match(r).end():]for r in replacements if UI_POOL_TAG.match(r)and r[UI_POOL_TAG.match(r).end():]}
 ui_suffix='(?:'+'|'.join(map(re.escape,sorted(ui_suffixes,key=len,reverse=True)))+')?'if ui_suffixes else ''
 ui_pattern=re.compile(UI_POOL_TAG.pattern+ui_suffix)
 def expand_ui(s):
  def ui(m):
   slot=int(m[1]);rows=report.get('uiPool',[]);require(0<=slot<len(rows)and isinstance(rows[slot],str),'Unknown publication UI slot')
   # Exact injected no-JS suffixes belong to the replacement receipt. They
   # were not present in the original HTML and must be removed on inversion.
   if m[0] in replacements:
    require(replacements[m[0]]==rows[slot],'Publication UI replacement differs')
    return replacements[m[0]]
   require(UI_POOL_TAG.fullmatch(m[0]) is not None,'Unknown publication UI fallback suffix')
   return rows[slot]
  for _ in range(16):
   new=ui_pattern.sub(ui,s)
   if new==s:return s
   s=new
  raise ValueError('Cyclic or excessive UI pool nesting')
 shard_tag=re.compile(r'<script src="([^"]+)" data-pr-shard="([0-9]+)"></script>')
 def remove_shard(m):
  shard=report.get('proofShards',{}).get(m[2]);require(shard is not None and shard['url']==m[1],'Proof shard import differs');return ''
 def expand(s,is_html=True):
  if is_html:
   if local_ui:
    selectors=list(re.finditer(r'<script\b[^>]*\bdata-pc-runtime\b[^>]*></script>',s))
    needs_runtime=bool(UI_POOL_TAG.search(s)or PROOF_POOL_TAG.search(s)or 'data-search-pool'in s)
    require(len(selectors)==(1 if needs_runtime else 0),'UI bootstrap missing or duplicated/unexpected')
    if selectors:
     selected=sorted({ui_slot_shard[slot]for slot in required_ui(s)})
     exact=report['proofCodecTags'].replace('data-pc-runtime','data-pc-runtime="'+','.join(map(str,selected))+'"')
     require(s.count(exact)==1,'UI bootstrap selector/closure coverage differs')
     head=re.findall(r'<head\b[^>]*>[\s\S]*?</head>',s,re.I)
     require(len(head)==1 and exact in head[0],'UI bootstrap is not inside the single page head')
     call=re.search(r'<script>__(?:sp|spr|ss|sl)\(',s)
     require(call is None or s.index(exact)<call.start(),'UI bootstrap follows a parser pool call')
     s=s.replace(exact,'',1)
   s=restore_search(s,report.get('searchPagePools',{}))
   s=class_attributes(s,REVERSE_CLASSES)
   s=PROOF_POOL_TAG.sub(lambda m:proof(int(m[1])),s)
   s=expand_proofs(s,report.get('compressedProofs',{}))
   if report.get('proofCodecTags'):s=s.replace(report['proofCodecTags'],'')
   s=shard_tag.sub(remove_shard,s);s=expand_ui(s)
   for _ in range(16):
    new=expand_fragment(s)
    if new==s:break
    s=new
   else:raise ValueError('Cyclic or excessive shared fragment nesting')
   s=expand_inline(s)
  s=html_styles(s,restore_css) if is_html else restore_css(s)
  if reverse:s=scope.sub(lambda m:reverse[m[0]],s)
  return s
 return expand

def verify(root,report_path):
 report=json.loads(report_path.read_text('utf8'));expand=expansion_function(report)
 for name,record in report['assets'].items():
  file=root/'_shared'/name;require(file.is_file() and digest(file.read_bytes())==record['sha256'],'Shared asset differs '+name)
 for name,expected in report['originalFiles'].items():
  file=root/name;require(file.is_file(),'Generated file missing '+name)
  s=expand(file.read_bytes().decode('utf8'),file.suffix=='.html')
  require(digest(s.encode())==expected,'Generated UI/HTML does not expand exactly '+name)
 for name in report['removedBuildMirrors']:require(name in RESTORATION_ONLY and not(root/name).exists(),'Unexpected removed asset')
 for name,record in report.get('proofCodecFiles',{}).items():
  file=root/'_publication'/name;require(file.is_file()and file.stat().st_size==record['bytes']and digest(file.read_bytes())==record['sha256'],'Publication codec/license differs '+name)
 size=total(root);require(size==report['afterBytes'] and size<=LIMIT,'Publication size changed or exceeds 1 GB')
 print(json.dumps({'status':'PASS','exactExpandedFiles':len(report['originalFiles']),'sharedAssets':len(report['assets']),'staticOriginalHtml':True,'afterBytes':size,'limitBytes':LIMIT},ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('dist'));p.add_argument('--base',default='/starrail-quests');p.add_argument('--report',type=Path,default=REPORT);p.add_argument('--verify',action='store_true');a=p.parse_args()
 if a.verify:verify(a.root,a.report)
 else:optimize(a.root,a.base.rstrip('/'),a.report);verify(a.root,a.report)
