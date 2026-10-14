"""Lossless presentation aliases; reading content and functional selectors stay static.

The fixed names below have no client-script consumers. The publication scan also
checks that claim against every generated script before it changes any file.
CSS retains both forms so subsequently inserted source HTML keeps its styles.
"""
import re
import base64
import gzip
import hashlib
import html
import json
from pathlib import Path
from html.parser import HTMLParser

PRESENTATION_CLASSES = (
 'rw-source-speaker','rw-source-body','rw-source-row','source-details',
 'not-content','rw-disclosure','content-panel','cva-reader-frame','sl-container',
 'context-term','universe-source-content','universe-source-excerpt','rw-source-link',
 'universe-source-number','universe-source-entry','document-meta','rw-reader',
 'cva-page','kind-badge','branch-note','main-pane','handbook-original-proof',
 'sl-flex','reading-next','sl-anchor-link','sl-anchor-icon','cva-item-title',
 'cva-item-copy','cva-item-body','jump-link','stage-predecessor',
 'level-h2','stage-context','mission-stage','stage-number','cva-badge','cva-panel',
 'collection-panel',
)
CLASS_ALIASES = {name:'z'+'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'[i] for i,name in enumerate(PRESENTATION_CLASSES)}
REVERSE_CLASSES = {alias:name for name,alias in CLASS_ALIASES.items()}
# Reading bodies, IDs, speakers and query parameters remain literal HTML.
# These repeated presentation/DOM contract names have a reversible wire spelling.
# One shared body-end module restores their canonical DOM contract before clients.
FUNCTIONAL_CLASSES={name:'qz'+chr(65+i)for i,name in enumerate(('original-body','original-row','original-paragraph','original-text','source-section'))}
WIRE_ATTRIBUTES={name:'data-r'+str(i)for i,name in enumerate(('data-reading-template','data-reading-kind','data-reading-variant','data-reading-link','data-pagefind-weight','data-source-link-variant','data-speaker','data-passage','data-pagefind-ignore','data-cva-profile','data-context-key','data-context-talk','data-deep-talk','data-deep-role','data-source-kind-value','data-directory-search'))}
def replace_words(text,mapping):
 pattern=re.compile(r'(?<![\w-])(?:'+'|'.join(map(re.escape,mapping))+r')(?![\w-])')
 return pattern.sub(lambda m:mapping[m[0]],text)
FRAME_NAMES=('data-reading-template','data-reading-kind','data-reading-variant','data-cva','data-cva-profile','data-source-link-variant')
FRAME_RUN=re.compile(r'(?:\s+(?:'+'|'.join(FRAME_NAMES)+r')(?:="[A-Za-z0-9_-]+")?(?=\s|/?>|$)){2,}')
_wire_report=None
def class_groups_html(text,groups,inverse=False):
 if not groups:return text
 reverse={marker:raw for raw,marker in groups.items()}
 if len(reverse)!=len(groups) or any(not re.fullmatch(r' c[0-9]+',marker)or not re.fullmatch(r' class="[A-Za-z0-9_ -]+"',raw)for raw,marker in groups.items()):raise ValueError('Invalid shared class bundle')
 def node(m):
  value=m[0]
  if value.lower().startswith(('<!--','<script','<style','</')):return value
  if inverse:return re.sub(r' c[0-9]+(?=\s|/?>)',lambda a:reverse[a[0]],value)
  return CLASS_ATTR.sub(lambda a:groups.get(a[0],a[0]),value)
 return TOKENS.sub(node,text)

def class_groups_css(text,groups,inverse=False):
 if not groups:return text
 if inverse:
  pattern=re.compile(r':is\((\.[A-Za-z0-9_-]+)(?:,\[c[0-9]+\])+\)')
  return selector_edits(text,pattern,lambda m:m[1])
 members={}
 for raw,marker in groups.items():
  for name in raw[len(' class="'):-1].split():members.setdefault(name,[]).append('['+marker.strip()+']')
 pattern=re.compile(r'\.('+'|'.join(map(re.escape,sorted(members,key=len,reverse=True)))+r')(?![\w-])')
 return selector_edits(text,pattern,lambda m:':is(.'+m[1]+','+','.join(members[m[1]])+')')

def wire_html(text,inverse=False,templates=None,groups=None):
 global _wire_report
 if inverse and ' data-rf="'in text and templates is None:
  if _wire_report is None:_wire_report=json.loads((Path(__file__).resolve().parents[1]/'.codex-work/publication-build-report.json').read_text('utf8'))
  templates=_wire_report.get('rowContract',{}).get('templates',[])
 if inverse and groups is None and re.search(r' c[0-9]+(?=\s|/?>)',text):
  if _wire_report is None:_wire_report=json.loads((Path(__file__).resolve().parents[1]/'.codex-work/publication-build-report.json').read_text('utf8'))
  groups=_wire_report.get('rowContract',{}).get('classGroups',{})
 if inverse:text=class_groups_html(text,groups,inverse=True)
 classes={v:k for k,v in FUNCTIONAL_CLASSES.items()}if inverse else FUNCTIONAL_CLASSES
 attrs={v:k for k,v in WIRE_ATTRIBUTES.items()}if inverse else WIRE_ATTRIBUTES
 text=class_attributes(text,classes)
 def node(m):
  value=m[0]
  if value.lower().startswith(('<!--','<script','<style','</')):return value
  if inverse:
   def restore_frame(marker):
    slot=int(marker[1])
    if templates is None or slot>=len(templates):raise ValueError('Unknown shared row contract')
    return templates[slot]
   value=re.sub(r' data-rf="([0-9]+)"',restore_frame,value)
  elif templates is not None:
   def frame(run):
    raw=run[0]
    if len(raw)<45:return raw
    if raw not in templates:
     if len(templates)>=256:return raw
     templates.append(raw)
    return ' data-rf="'+str(templates.index(raw))+'"'
   value=FRAME_RUN.sub(frame,value)
  return ATTR_TOKENS.sub(lambda a:re.sub(r'^(\s+)'+re.escape(a[1]),lambda n:n[1]+attrs[a[1]],a[0],count=1)if a[1]in attrs else a[0],value)
 text=TOKENS.sub(node,text)
 return text if inverse else class_groups_html(text,groups)
def frame_fields(templates):
 class Attributes(HTMLParser):
  def handle_starttag(self,tag,items):self.items=items
 fields=[]
 for raw in templates:
  if not FRAME_RUN.fullmatch(raw):raise ValueError('Invalid row contract attributes')
  parser=Attributes();parser.feed('<div'+raw+'>')
  if any(name not in FRAME_NAMES for name,_ in parser.items):raise ValueError('Unknown row contract attribute')
  fields.append(parser.items)
 return fields
def wire_css(text,inverse=False,templates=None,groups=None):
 if inverse:text=class_groups_css(text,groups,inverse=True)
 if inverse:
  mapping={f':is(.{name},.{alias})':'.'+name for name,alias in FUNCTIONAL_CLASSES.items()}
  pattern=re.compile('|'.join(map(re.escape,mapping)))
  text=selector_edits(text,pattern,lambda m:mapping[m[0]])
 else:
  pattern=re.compile(r'\.('+'|'.join(map(re.escape,FUNCTIONAL_CLASSES))+r')(?![\w-])')
  text=selector_edits(text,pattern,lambda m:f':is(.{m[1]},.{FUNCTIONAL_CLASSES[m[1]]})')
 if inverse:
  names='|'.join(map(re.escape,(*WIRE_ATTRIBUTES,*FRAME_NAMES)))
  short='|'.join(map(re.escape,WIRE_ATTRIBUTES.values()))
  pattern=re.compile(r':is\((\[(?:'+names+r')[^\]]*\])(?:,\[(?:(?:'+short+r')|data-rf)[^\]]*\])+\)')
  text=selector_edits(text,pattern,lambda m:m[1],literal_match=True)
 else:
  fields=[dict(items)for items in frame_fields(templates or [])]
  pattern=re.compile(r'\[(?:'+'|'.join(map(re.escape,(*WIRE_ATTRIBUTES,*FRAME_NAMES)))+r')(?:[^\]"\x27]|"[^"]*"|\x27[^\x27]*\x27)*\]')
  def alternatives(m):
   raw=m[0];rows=[raw];short=replace_words(raw,WIRE_ATTRIBUTES)
   if short!=raw:rows.append(short)
   condition=re.fullmatch(r'\[([\w-]+)(?:=(?:"([^"]*)"|\x27([^\x27]*)\x27|([^\]\s]+)))?\]',raw)
   if condition:
    name=condition[1];value=next((v for v in condition.groups()[1:]if v is not None),None)
    rows.extend('[data-rf="'+str(i)+'"]'for i,frame in enumerate(fields)if name in frame and(value is None or frame[name]==value))
   return ':is('+','.join(rows)+')'if len(rows)>1 else raw
  text=selector_edits(text,pattern,alternatives,literal_match=True)
 return text if inverse else class_groups_css(text,groups)

def row_contract_runtime(templates,groups=None):
 fields=frame_fields(templates)
 config=json.dumps({'classes':{v:k for k,v in FUNCTIONAL_CLASSES.items()},'attributes':{v:k for k,v in WIRE_ATTRIBUTES.items()},'frames':fields},ensure_ascii=False,separators=(',',':'))
 program='''"use strict";
// One shared row contract; text, source IDs, anchors and order stay in HTML.
// This classic script runs at body end, before deferred/module UI consumers.
(()=>{const c='''+config+''';
const selector=['[data-rf]',...Object.keys(c.classes).map(k=>'.'+k),...Object.keys(c.attributes).map(k=>'['+k+']')].join(',');
for(const node of document.querySelectorAll(selector)){
 const marker=node.getAttribute('data-rf');
 if(marker!==null){const slot=Number(marker);if(!Number.isSafeInteger(slot)||slot<0||!c.frames[slot])throw new Error('Unknown shared row contract');for(const [name,value]of c.frames[slot])node.setAttribute(name,value??'');node.removeAttribute('data-rf');}
 for(const [short,name]of Object.entries(c.attributes))if(node.hasAttribute(short)){node.setAttribute(name,node.getAttribute(short));node.removeAttribute(short);}
 for(const [short,name]of Object.entries(c.classes))if(node.classList.contains(short))node.classList.replace(short,name);
}
})();
'''
 if groups is not None:
  class_groups_html('',groups)
  bundle={marker.strip():raw[len(' class="'):-1]for raw,marker in groups.items()}
  program=program.replace("const selector=['[data-rf]'",'const bundles='+json.dumps(bundle,separators=(',',':'))+';\nconst selector=[...Object.keys(bundles).map(k=>\'[\'+k+\']\'),\'[data-rf]\'')
  program=program.replace(" const marker=node.getAttribute('data-rf');"," for(const [marker,value]of Object.entries(bundles))if(node.hasAttribute(marker)){node.setAttribute('class',value);node.removeAttribute(marker);}\n const marker=node.getAttribute('data-rf');")
 return program

def version_css_links(text,urls):
 def node(m):
  value=m[0]
  if not value.lower().startswith('<link '):return value
  return re.sub(r'(\bhref=")([^"]+)(")',lambda a:a[1]+urls.get(a[2],a[2])+a[3],value)
 return TOKENS.sub(node,text)
TOKENS = re.compile(r'<!--[\s\S]*?-->|<script\b[^>]*>[\s\S]*?</script\s*>|<style\b[^>]*>[\s\S]*?</style\s*>|</?[A-Za-z][^>]*>',re.I)
CLASS_ATTR = re.compile(r'(\sclass\s*=\s*)(["\'])(.*?)\2',re.S|re.I)
ATTR_TOKENS = re.compile(r'\s+([^\s=/>]+)(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+))?')

def class_attributes(text, mapping):
 def tag(m):
  value=m[0]
  if value.lower().startswith(('<!--','<script','<style','</')):return value
  def attribute(a):
   # Preserve every separator, quote and non-class byte.
   return a[1]+a[2]+re.sub(r'\S+',lambda t:mapping.get(t[0],t[0]),a[3])+a[2]
  return ATTR_TOKENS.sub(lambda a:CLASS_ATTR.sub(attribute,a[0]) if a[1].lower()=='class' else a[0],value)
 return TOKENS.sub(tag,text)

def static_html(text):
 """Normalize class attributes only; never materialize reading rows from scripts."""
 text=restore_search(text)
 return class_attributes(wire_html(text,inverse=True),REVERSE_CLASSES)

class StaticHTMLParser(HTMLParser):
 def feed(self,data):return super().feed(static_html(data))

CSS_CLASS = re.compile(r'\.('+'|'.join(map(re.escape,PRESENTATION_CLASSES))+r')(?![\w-])')
CSS_LEX = re.compile(r'/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{};()]|\\.',re.S)

def selector_edits(text,pattern,replace,literal_match=False):
 """Change selector headers only, skipping comments, strings and declarations."""
 edits=[];boundary=0;parens=0;custom_depth=0
 for token in CSS_LEX.finditer(text):
  value=token[0]
  if value=='(':parens+=1
  elif value==')':parens-=1
  elif parens==0 and value=='{':
   if custom_depth:custom_depth+=1;continue
   header=text[boundary:token.start()]
   # Mask literals while retaining their offsets, then locate class selectors.
   masked=CSS_LEX.sub(lambda m:' '*len(m[0]) if m[0].startswith(('/*','"',"'",'\\')) else m[0],header)
   if re.match(r'\s*--[\w-]+\s*:',masked):custom_depth=1;continue
   for match in pattern.finditer(masked):
    original=pattern.match(header,match.start(),match.end())if literal_match else match
    if original is None or original.end()!=match.end():raise ValueError('CSS literal selector boundary differs')
    edits.append((boundary+match.start(),boundary+match.end(),replace(original)))
   boundary=token.end()
  elif parens==0 and value in (';','}'):
   if custom_depth:
    if value=='}':custom_depth-=1
    if custom_depth:continue
   boundary=token.end()
 for start,end,value in reversed(edits):text=text[:start]+value+text[end:]
 return text

def css_aliases(text):
 return selector_edits(text,CSS_CLASS,lambda m:f':is(.{m[1]},.{CLASS_ALIASES[m[1]]})')

def restore_css(text):
 inverse={f':is(.{name},.{alias})':'.'+name for name,alias in CLASS_ALIASES.items()}
 pattern=re.compile('|'.join(map(re.escape,inverse)))
 return selector_edits(text,pattern,lambda m:inverse[m[0]])

def html_styles(text,transform):
 pattern=re.compile(r'(<style\b[^>]*>)([\s\S]*?)(</style\s*>)',re.I)
 def node(m):
  if not m[0].lower().startswith('<style'):return m[0]
  style=pattern.fullmatch(m[0])
  return style[1]+transform(style[2])+style[3] if style else m[0]
 return TOKENS.sub(node,text)

SEARCH_CALL = re.compile(r'(<a\b[^>]*\bdata-search="")([^>]*>)<script>__ss\(([0-9]+)\);</script>')
SEARCH_LOADER = re.compile(r'<script data-search-pool="([0-9a-f]{64})">__sl\("([A-Za-z0-9+/=]+)",([0-9]+)\);</script>')
SEARCH_RUNTIME = '''
window.__sl=function(encoded,expectedBytes){
 if(window.__starrailSearchValues)throw new Error("Duplicate search pool");
 var values=JSON.parse(__starrailPublicationDecode(encoded,expectedBytes));
 if(!Array.isArray(values)||values.some(function(v){return typeof v!=="string"}))throw new Error("Invalid search pool");
 window.__starrailSearchValues=values;
};
window.__ss=function(id){
 var values=window.__starrailSearchValues,node=document.currentScript.parentElement;
 if(!Number.isSafeInteger(id)||id<0||!values||id>=values.length||!node||node.tagName!=="A"||node.getAttribute("data-search")!==""||!(node.hasAttribute("data-source-record")||node.hasAttribute("data-record")))throw new Error("Invalid search attribute target");
 node.setAttribute("data-search",values[id]);
};
'''

def search_attributes(text,records):
 if 'data-search=' not in text:return text,None,0
 raw_values=[];stack=[];void=set('area base br col embed hr img input link meta param source track wbr'.split())
 def node(m):
  tag=m[0]
  if tag.lower().startswith(('<!--','<script','<style')):return tag
  match=re.match(r'</?([A-Za-z][\w:-]*)',tag)
  if not match:return tag
  name=match[1].lower()
  if tag.startswith('</'):
   indexes=[i for i,item in enumerate(stack)if item[0]==name]
   if indexes:del stack[indexes[-1]:]
   return tag
  protected=bool(stack and stack[-1][1]) or bool(re.search(r'\b(?:original-body|original-row|original-paragraph|data-passage|data-reading-kind)\b|data-reading-template="(?:row|reader)"',tag))
  if name not in void:stack.append((name,protected))
  if protected:return tag
  if not tag.lower().startswith('<a '):return tag
  attr=re.search(r'\bdata-search="([^"]*)"',tag)
  if not attr or not re.search(r'\bdata-(?:source-record|record)(?:=|\s|>)',tag):return tag
  if re.search(r'\b(?:original-body|original-row|original-paragraph|data-passage|data-reading-kind)\b|data-reading-template="row"',tag):return tag
  raw=attr[1]
  if len(raw.encode())<128:return tag
  slot=len(raw_values);raw_values.append(raw)
  return tag[:attr.start(1)]+tag[attr.end(1):]+f'<script>__ss({slot});</script>'
 changed=TOKENS.sub(node,text)
 if not raw_values:return text,None,0
 values=[html.unescape(v.replace('\r\n','\n').replace('\r','\n'))for v in raw_values]
 raw=json.dumps(values,ensure_ascii=False,separators=(',',':')).encode()
 encoded=base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode()
 identity=hashlib.sha256(json.dumps(raw_values,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
 loader=f'<script data-search-pool="{identity}">__sl("{encoded}",{len(raw)});</script>'
 if len(loader.encode())+len(changed.encode())>=len(text.encode()):return text,None,0
 if len(loader.encode())>500_000:raise ValueError('Directory search pool exceeds bounded page payload')
 previous=records.setdefault(identity,{'rawAttributes':raw_values,'loader':loader})
 if previous!={'rawAttributes':raw_values,'loader':loader}:raise ValueError('Search pool identity collision')
 return changed,loader,len(raw_values)

_search_report=None
def restore_search(text,records=None):
 global _search_report
 if not SEARCH_LOADER.search(text):
  if SEARCH_CALL.search(text):raise ValueError('Directory search loader missing')
  return text
 if records is None:
  if _search_report is None:_search_report=json.loads((Path(__file__).resolve().parents[1]/'.codex-work/publication-build-report.json').read_text('utf8')).get('searchPagePools',{})
  records=_search_report
 matches=list(SEARCH_LOADER.finditer(text))
 if len(matches)!=1:raise ValueError('Expected one directory search pool')
 loader=matches[0];record=records.get(loader[1])
 if record is None or record['loader']!=loader[0]:raise ValueError('Unknown or changed directory search pool')
 rows=record['rawAttributes'];identity=hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
 if identity!=loader[1]:raise ValueError('Directory search receipt differs')
 raw=gzip.decompress(base64.b64decode(loader[2],validate=True))
 if len(raw)!=int(loader[3]) or json.loads(raw)!=[html.unescape(v.replace('\r\n','\n').replace('\r','\n'))for v in rows]:raise ValueError('Directory search DOM values differ')
 seen=[]
 def attribute(m):
  slot=int(m[3])
  if slot>=len(rows) or slot in seen:raise ValueError('Invalid duplicate search slot')
  seen.append(slot)
  return m[1][:-1]+rows[slot]+'"'+m[2]
 text=SEARCH_CALL.sub(attribute,text)
 if seen!=list(range(len(rows))):raise ValueError('Missing or reordered directory search slot')
 return text.replace(loader[0],'')
