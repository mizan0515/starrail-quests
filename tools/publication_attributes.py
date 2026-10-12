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
 return class_attributes(text,REVERSE_CLASSES)

class StaticHTMLParser(HTMLParser):
 def feed(self,data):return super().feed(static_html(data))

CSS_CLASS = re.compile(r'\.('+'|'.join(map(re.escape,PRESENTATION_CLASSES))+r')(?![\w-])')
CSS_LEX = re.compile(r'/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{};()]|\\.',re.S)

def selector_edits(text,pattern,replace):
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
    edits.append((boundary+match.start(),boundary+match.end(),replace(match)))
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
 return re.sub(r'(<style\b[^>]*>)([\s\S]*?)(</style\s*>)',lambda m:m[1]+transform(m[2])+m[3],text,flags=re.I)

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
