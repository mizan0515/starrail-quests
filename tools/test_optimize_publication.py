"""Focused boundary, exact inverse and real JS codec tests for publication."""
import base64
import gzip
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
spec=importlib.util.spec_from_file_location('publication_optimizer',Path(__file__).with_name('optimize_publication.py'))
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)

class ProofCompressionTests(unittest.TestCase):
 def block(self,body,attrs='class="source-details" id="verified-sources"'):
  return '<details '+attrs+'><summary>원문 근거 · 閱讀</summary>'+body+'</details>'
 def test_declared_quest_navigation_only_shares_metadata(self):
  nav='<section class="quest-reading-nav" data-quest-reading-nav data-pagefind-ignore><details><summary>임무</summary><a id="quest-nav-quest-1-original" href="/문서/quest-1.html#original" data-quest-reading-link>임무의 원문</a></details></section>'
  self.assertTrue(P.quest_navigation_ui(nav));self.assertEqual(P.FRAGMENTS[0].search(nav)[0],nav)
  for bad in [nav.replace(' data-quest-reading-nav',''),nav.replace(' data-pagefind-ignore',''),nav.replace('</details>','<p class="original-row">원문</p></details>'),nav.replace('</details>','<blockquote>인용</blockquote></details>'),nav.replace('</details>','<section>원문</section></details>')]:self.assertFalse(P.quest_navigation_ui(bad))
  report={'replacements':{},'scopes':{},'uiPool':[nav],'proofPool':[],'proofShards':{}}
  passage='<p id="talk-1" class="original-body">보존 원문</p>'
  self.assertEqual(P.expansion_function(report)('<script>__sp(0);</script>'+passage),nav+passage)
 def test_document_guide_boundary_and_nested_ui_exact_inverse(self):
  nav='<nav><a id="guide-origin" href="/문서/quest-1.html#original">원문으로 돌아가기</a></nav>'
  guide='<aside class="reader-guide-rail print:hidden" aria-label="현재 글의 독서 안내"><details id="reader-guide" open><summary>원문 목차</summary><div class="reader-guide-body"><script>__sp(0);</script></div></details></aside>'
  self.assertTrue(P.reading_guide_ui(guide))
  self.assertTrue(any(pattern.search(guide) for pattern in P.FRAGMENTS))
  original='<p id="talk-1" class="original-body" data-speaker="운리">한국어 원문 &amp; 선택지</p>'
  report={'replacements':{},'scopes':{},'uiPool':[nav,guide],'proofPool':[],'proofShards':{}}
  self.assertEqual(P.expansion_function(report)('<script>__sp(1);</script>'+original),guide.replace('<script>__sp(0);</script>',nav)+original)
  self.assertEqual(P.ui_closure([nav,guide])('<script>__sp(1);</script>'),{0,1})
  for protected in [original,'<div data-reading-template="row">원문</div>','<blockquote>원문 인용</blockquote>','<pre>원문</pre>','<main>본문</main>','<h1>본문 제목</h1>','<aside>다른 영역</aside>']:
   self.assertFalse(P.reading_guide_ui(guide.replace('</details>',protected+'</details>')))
  for bad in [guide.replace('reader-guide-rail','another-rail'),guide.replace('id="reader-guide"','id="other"')]:
   self.assertFalse(P.reading_guide_ui(bad))
 def test_shared_guide_frame_is_one_source_with_separate_document_slots(self):
  rows=[];index={}
  def pool(body):
   if body not in index:index[body]=len(rows);rows.append(body)
   return f'<script>__sp({index[body]});</script>'
  prefix='<aside class="reader-guide-rail" aria-label="현재 글의 독서 안내"><details id="reader-guide" open><summary>원문 목차</summary><div class="reader-guide-body">'
  suffix='</div></details></aside>'
  bodies=['<nav><a href="#scene-1">운리</a></nav>','<nav><a href="#scene-2">스파클</a></nav>']
  calls=[P.shared_reading_guide(prefix+body+suffix,pool) for body in bodies]
  self.assertEqual(rows.count(prefix),1);self.assertEqual(rows.count(suffix),1)
  self.assertTrue(all(prefix not in row for row in rows if row!=prefix))
  report={'replacements':{},'scopes':{},'uiPool':rows,'proofPool':[],'proofShards':{}}
  expand=P.expansion_function(report)
  original='<main><p class="original-body" id="talk-1">보존된 한국어 원문</p></main>'
  for call,body in zip(calls,bodies):
   self.assertEqual(expand(call+original),prefix+body+suffix+original)
   self.assertEqual(len(P.ui_closure(rows)(call)),4)
  self.assertIsNone(P.shared_reading_guide(prefix+original+suffix,pool))
  self.assertIsNone(P.shared_reading_guide((prefix+bodies[0]+suffix).replace('reader-guide-body','other'),pool))
 def test_full_optimizer_shared_guide_receipt_and_static_original(self):
  with tempfile.TemporaryDirectory()as directory:
   root=Path(directory)/'dist';root.mkdir();report=Path(directory)/'report.json'
   prefix='<aside class="reader-guide-rail"><details id="reader-guide" open><summary>원문 목차</summary><div class="reader-guide-body">'
   suffix='</div></details></aside>';originals=[]
   for i in range(2):
    original='<html><head></head><body>'+prefix+f'<nav><a href="#talk-{i}">장면 {i}</a></nav>'+suffix+f'<main><p class="original-body" id="talk-{i}">한국어 대사 {i}</p></main></body></html>'
    originals.append(original);(root/f'{i}.html').write_text(original,'utf8')
   P.optimize(root,'/starrail-quests',report);P.verify(root,report)
   data=json.loads(report.read_text('utf8'));expand=P.expansion_function(data)
   self.assertEqual(data['uiPool'].count(prefix),1);self.assertEqual(data['uiPool'].count(suffix),1)
   self.assertEqual(data['counts']['sharedReaderGuideTemplates'],2)
   for i,original in enumerate(originals):
    built=(root/f'{i}.html').read_text('utf8')
    self.assertIn(f'id="talk-{i}">한국어 대사 {i}',built);self.assertNotIn(prefix,built)
    self.assertEqual(expand(built),original)
 def test_declared_technical_dl_preserves_outer_anchor_and_exact_inverse(self):
  metadata='<dl data-publication-metadata="technical"><dt>호출 자료</dt><dd>'+('캐시 SHA-256 0123456789abcdef '*100)+'</dd></dl>'
  original=self.block('<h2 id="caller-proof">호출 근거</h2>'+metadata)
  records={};packed,count,saved=P.compress_proofs(original,records)
  self.assertEqual(count,1);self.assertGreater(saved,0);self.assertIn('<h2 id="caller-proof">',packed);self.assertIn('<dl data-publication-metadata="technical">',packed)
  self.assertEqual(P.expand_proofs(packed,records).encode(),original.encode())
  plain=original.replace(' data-publication-metadata="technical"','');self.assertEqual(P.compress_proofs(plain,{})[:2],(plain,0))
 def test_declared_metadata_cannot_hide_reading_links_quotes_or_descendant_anchors(self):
  for protected in ('<p class="original-body">원문</p>','<a href="#talk-1" data-reading-link>복귀</a>','<p id="talk-1">원문</p>','<blockquote>인용</blockquote>'):
   original=self.block('<h2 id="proof">근거</h2><dl data-publication-metadata="technical"><dd>'+protected+('metadata '*100)+'</dd></dl>')
   self.assertEqual(P.compress_proofs(original,{})[:2],(original,0))
 def test_utf8_quotes_script_end_and_exact_bytes(self):
  body='<pre>'+('한국어 😀 &quot; \\ \r\n </script> &lt;details&gt; '+chr(0xa0))*100+'</pre>'
  original=self.block(body);records={};packed,count,saved=P.compress_proofs(original,records)
  self.assertEqual(count,1);self.assertGreater(saved,0)
  self.assertTrue(packed.startswith('<details class="source-details" id="verified-sources"><summary>'))
  self.assertEqual(packed.count('</script>'),1)
  self.assertEqual(P.expand_proofs(packed,records).encode(),original.encode())
 def test_open_boolean_is_not_closed_even_when_false(self):
  for value in ('open','open="false"','open=""',"open='false'"):
   original=self.block('<pre>'+'hash'*500+'</pre>',attrs='class="source-details" '+value)
   packed,count,_=P.compress_proofs(original,{})
   self.assertEqual((packed,count),(original,0))
 def test_original_rows_anchors_and_return_links_stay_static(self):
  for content in ('<p class="original-body">본문</p>','<div class="rw-source-row">행</div>','<section class="reading-scene">장면</section>','<p id="talk-123">원문</p>','<a href="#talk-1" data-reading-link>복귀</a>','<div data-passage="dialogue">대사</div>'):
   original=self.block(content+'<pre>'+'proof '*300+'</pre>')
   records={};packed,count,_=P.compress_proofs(original,records)
   self.assertEqual(count,1,content);self.assertIn(content,packed)
   self.assertEqual(P.expand_proofs(packed,records),original)
 def test_protected_reading_subtree_and_plain_links_stay_static(self):
  body='<div class="original-body" id="talk-1"><pre>'+'원문 '*500+'</pre></div><a href="#talk-1">복귀</a><pre id="proof-code"><code>'+'metadata '*500+'</code></pre>'
  original=self.block(body);records={};packed,count,_=P.compress_proofs(original,records)
  self.assertEqual(count,1)
  self.assertIn('<div class="original-body" id="talk-1"><pre>'+'원문 '*500+'</pre></div>',packed)
  self.assertIn('<a href="#talk-1">복귀</a>',packed);self.assertIn('<pre id="proof-code">',packed)
  self.assertEqual(P.expand_proofs(packed,records),original)
 def test_quotation_and_reading_pre_are_not_metadata(self):
  for wrapper in ('<blockquote>','<p class="original-paragraph">','<div data-reading-template="reader">'):
   close=wrapper.split()[0].replace('<','</').replace('>','')+'>'
   original=self.block(wrapper+'<pre>'+'원문 '*500+'</pre>'+close)
   self.assertEqual(P.compress_proofs(original,{})[:2],(original,0))
 def test_external_structured_source_pointers_are_metadata_and_return_links_static(self):
  pointer='<a href="https://github.com/example/archive/blob/pinned/Config/Mission.json">구조 원본</a>'
  original=self.block(pointer+'<pre>'+'typed field hash '*500+'</pre>');records={}
  packed,count,_=P.compress_proofs(original,records)
  self.assertEqual(count,1);self.assertNotIn(pointer,packed);self.assertEqual(P.expand_proofs(packed,records),original)
  for link in ('<a href="#talk-1">원문 복귀</a>','<a href="/문서/quest.html#talk-1" data-reading-link>원문 복귀</a>'):
   original=self.block(link+'<pre>'+'typed field '*500+'</pre>');records={}
   packed,count,_=P.compress_proofs(original,records);self.assertEqual(count,1);self.assertIn(link,packed)
   self.assertEqual(P.expand_proofs(packed,records),original)
 def test_nested_technical_anchor_keeps_both_disclosures_static(self):
  inner=self.block('<pre>'+'hash '*300+'</pre>',attrs='class="source-details" id="nested-proof"')
  original=self.block(inner);records={};packed,count,_=P.compress_proofs(original,records)
  self.assertEqual(count,1)
  self.assertIn('id="verified-sources"',packed);self.assertIn('id="nested-proof"',packed)
  self.assertEqual(P.expand_proofs(packed,records),original)
 def test_metadata_only_nested_summary_without_id_restores_whole_interior(self):
  nested='<dl><dt>파일 SHA-256</dt><dd>'+'hash '*500+'</dd></dl><details><summary>표시 정리 전 한국어 원문</summary><pre>보존 운명의 길</pre></details>'
  original=self.block(nested);records={};packed,count,_=P.compress_proofs(original,records)
  self.assertEqual(count,1);self.assertIn('<summary>원문 근거 · 閱讀</summary>',packed)
  self.assertEqual(P.expand_proofs(packed,records),original)
  original=self.block(nested.replace('<details>','<details id="nested">'));records={};packed,_,_=P.compress_proofs(original,records)
  self.assertIn('<details id="nested"><summary>표시 정리 전 한국어 원문</summary>',packed)
  self.assertEqual(P.expand_proofs(packed,records),original)
 def test_script_comment_and_style_literals_are_skipped(self):
  fake=self.block('<pre>'+'hash '*300+'</pre>')
  for original in ('<script>const fake='+json.dumps(fake)+';</script>','<!--'+fake+'-->','<style>/* '+fake+' */</style>'):
   self.assertEqual(P.compress_proofs(original,{})[:2],(original,0))
 def test_native_metadata_id_attribute_is_not_a_dom_anchor(self):
  original=self.block('<pre data-native-talk-id="123">'+'source '*300+'</pre>');records={}
  packed,count,_=P.compress_proofs(original,records)
  self.assertEqual(count,1);self.assertEqual(P.expand_proofs(packed,records),original)
 def test_active_scripts_and_unbalanced_details_are_rejected(self):
  original=self.block('<script>alert(1)</script>'+'hash '*500)
  self.assertEqual(P.compress_proofs(original,{})[:2],(original,0))
  with self.assertRaises(ValueError):P.proof_interiors('<details class="source-details">missing close')
 def test_tampering_and_unknown_digest_fail_exact_inverse(self):
  original=self.block('<pre>'+'sha '*300+'</pre>');records={};packed,_,_=P.compress_proofs(original,records)
  with self.assertRaises(ValueError):P.expand_proofs(packed,{})
  match=P.PROOF_TAG.search(packed)
  bad=packed[:match.start(3)]+str(int(match[3])+1)+packed[match.end(3):]
  with self.assertRaises(ValueError):P.expand_proofs(bad,records)
 def test_real_pinned_js_decoder_utf8_crc_length_and_invalid_utf8(self):
  node=shutil.which('node.exe')or shutil.which('node');self.assertIsNotNone(node)
  codec=Path(P.__file__).resolve().parents[1]/'public/_publication'/P.CODEC_FILE
  self.assertEqual(P.digest(codec.read_bytes()),P.CODEC_SHA256)
  text='한글 😀 " 따옴표 \\ </script>\r\n'+chr(0xa0)
  payload=base64.b64encode(gzip.compress(text.encode(),mtime=0)).decode()
  invalid=base64.b64encode(gzip.compress(b'\xff',mtime=0)).decode()
  corrupt=bytearray(gzip.compress(text.encode(),mtime=0));corrupt[-5]^=1
  program='''const fs=require('fs'),vm=require('vm');const input=JSON.parse(fs.readFileSync(0,'utf8'));let writes=[];
  const ctx={document:{write:t=>writes.push(t)},TextDecoder,Uint8Array,atob:s=>Buffer.from(s,'base64').toString('latin1')};ctx.window=ctx;vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(input.codec,'utf8'),ctx);vm.runInContext(input.runtime,ctx);
  ctx.__starrailPublicationWrite(input.payload,input.bytes);
  let rejected=0;for(const [p,n]of [[input.payload,input.bytes+1],[input.invalid,1],[input.corrupt,input.bytes]]){try{ctx.__starrailPublicationWrite(p,n)}catch(e){rejected++}}
  process.stdout.write(JSON.stringify({writes,rejected}));'''
  run=subprocess.run([node,'-e',program],input=json.dumps({'codec':str(codec),'runtime':P.PROOF_RUNTIME,'payload':payload,'bytes':len(text.encode()),'invalid':invalid,'corrupt':base64.b64encode(corrupt).decode()}),text=True,encoding='utf8',capture_output=True)
  self.assertEqual(run.returncode,0,run.stderr);result=json.loads(run.stdout)
  self.assertEqual(result,{'writes':[text],'rejected':3})
 def test_shared_ui_and_proof_shard_js_guards_and_exact_inverse(self):
  node=shutil.which('node.exe')or shutil.which('node');codec=Path(P.__file__).resolve().parents[1]/'public/_publication'/P.CODEC_FILE
  rows=['<pre>한글 😀 &lt;/script&gt; " \\</pre>','<dl><dt>근거</dt><dd>hash 18446744073709551615</dd></dl>']
  shard=P.proof_shards(rows)[0]
  program='''const fs=require('fs'),vm=require('vm');const input=JSON.parse(fs.readFileSync(0,'utf8'));let writes=[];
  const ctx={document:{write:t=>writes.push(t)},TextDecoder,TextEncoder,Uint8Array,atob:s=>Buffer.from(s,'base64').toString('latin1')};ctx.window=ctx;vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(input.codec,'utf8'),ctx);vm.runInContext(input.runtime,ctx);vm.runInContext(input.shard,ctx);
  ctx.__sp(0);ctx.__spr(0);ctx.__spr(1);
  let rejected=0;for(const call of [()=>ctx.__sp(-1),()=>ctx.__sp(999),()=>ctx.__sp(0.5),()=>ctx.__spr(999),()=>ctx.__spr('0'),()=>vm.runInContext(input.shard,ctx),()=>ctx.__starrailPublicationLoadProofs(3,input.payload,input.bytes+1,input.sizes),()=>ctx.__starrailPublicationLoadProofs(3,input.payload,input.bytes,[1,2])]){try{call()}catch(e){rejected++}}
  process.stdout.write(JSON.stringify({writes,rejected}));'''
  run=subprocess.run([node,'-e',program],input=json.dumps({'codec':str(codec),'runtime':P.pooled_runtime(['<nav>목록</nav>']),'shard':shard['body'],'payload':shard['payload'],'bytes':shard['rawBytes'],'sizes':shard['sizes']}),text=True,encoding='utf8',capture_output=True)
  self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(json.loads(run.stdout),{'writes':['<nav>목록</nav>']+rows,'rejected':8})
  report={'replacements':{},'scopes':{},'uiPool':['<nav>목록</nav>'],'proofPool':[{'sha256':P.digest(row.encode()),'rawBytes':len(row.encode()),'shard':0}for row in rows],'proofShards':{'0':dict(shard,url='/shard.js')}}
  source='<script>__sp(0);</script><script src="/shard.js" data-pr-shard="0"></script><script>__spr(0);</script><script>__spr(1);</script>'
  self.assertEqual(P.expansion_function(report)(source),'<nav>목록</nav>'+''.join(rows))
  bad=json.loads(json.dumps(report));bad['proofPool'][1]['sha256']='0'*64
  with self.assertRaises(ValueError):P.expansion_function(bad)(source)
  with self.assertRaises(ValueError):P.expansion_function(report)('<script>__spr(2);</script>')
 def test_proof_shards_are_deterministic_bounded_and_at_most_128_rows(self):
  rows=[f'<pre>{i} '+'hash 한글 '*100+'</pre>'for i in range(300)]
  a=P.proof_shards(rows);b=P.proof_shards(rows);self.assertEqual(a,b)
  self.assertEqual([r['count']for r in a],[128,128,44])
  self.assertTrue(all(len(r['body'].encode())<=P.MAX_PROOF_SHARD_BYTES for r in a))
  self.assertEqual(a[0]['payload'][0:8],base64.b64encode(gzip.compress(b'x',mtime=0)).decode()[0:8])
 def test_pool_namespace_collision_is_rejected_before_body_mutation(self):
  with tempfile.TemporaryDirectory()as directory:
   root=Path(directory);original='<html><head></head><body><script>__sp(0);</script></body></html>'
   (root/'one.html').write_text(original,'utf8')
   with self.assertRaises(ValueError):P.optimize(root,'/starrail-quests',root.parent/'unused.json')
   self.assertEqual((root/'one.html').read_text('utf8'),original)
 def test_full_optimizer_exact_html_css_js_inverse_and_static_body(self):
  with tempfile.TemporaryDirectory()as directory:
   root=Path(directory)/'dist';root.mkdir();report=Path(directory)/'report.json'
   original='<html><head><meta charset="utf-8"><style>.astro-a1234567{color:red}</style></head><body><header>자료집 제목</header><p class="original-body astro-a1234567" id="talk-9">원문과 앵커</p>'+self.block('<pre>'+'sha source '*400+'</pre>')+'<script type="module" src="/starrail-quests/_astro/reader.js"></script><footer>게임 콘텐츠 출처</footer></body></html>'
   for name in ('one.html','two.html'):(root/name).write_text(original,encoding='utf8')
   (root/'test.css').write_text('.astro-a1234567{color:red}',encoding='utf8')
   (root/'test.js').write_text('const scope="astro-a1234567";',encoding='utf8')
   P.optimize(root,'/starrail-quests',report);P.verify(root,report)
   built=(root/'one.html').read_text('utf8');self.assertIn('id="talk-9">원문과 앵커',built)
   self.assertIn('id="verified-sources"',built);self.assertIn('<summary>원문 근거 · 閱讀</summary>',built)
   data=json.loads(report.read_text('utf8'));expand=P.expansion_function(data)
   self.assertEqual(expand(built),original);self.assertEqual(data['counts']['compressedProof'],2)
   self.assertIn('data-pc-library',built);self.assertLess(built.index('data-pc-library'),built.index('</head>'))
   self.assertNotIn(' async',data['proofCodecTags']);self.assertNotIn(' defer',data['proofCodecTags'])
   self.assertEqual(data['counts']['sharedStandaloneModules'],2)
   self.assertTrue(built.startswith('<html><head><meta charset="utf-8">'))

class SourceContextSharingTests(unittest.TestCase):
 def test_short_generated_scopes_reserve_existing_prose_and_script_tokens(self):
  with tempfile.TemporaryDirectory()as directory:
   root=Path(directory)/'dist';root.mkdir();report=Path(directory)/'report.json'
   original='<html><head><style>.astro-a1234567{color:red}</style></head><body><p class="original-body astro-a1234567" id="talk-1">원문 _a 그대로</p><script>const _b="이름 보존";</script></body></html>'
   (root/'index.html').write_text(original,'utf8');P.optimize(root,'/starrail-quests',report);P.verify(root,report)
   data=json.loads(report.read_text('utf8'));alias=data['scopes']['astro-a1234567']
   self.assertEqual(len(alias),2);self.assertNotIn(alias,{'_a','_b'})
   self.assertEqual(P.expansion_function(data)((root/'index.html').read_text('utf8')),original)
   self.assertIn('원문 _a 그대로',(root/'index.html').read_text('utf8'));self.assertIn('const _b=',(root/'index.html').read_text('utf8'))

 def test_indexed_ui_storage_retains_slots_and_rejects_malformed_pairs(self):
  rows=['<nav>z · 끝</nav>','<nav>a · 처음</nav>','<nav>중간</nav>']
  code=r'''
const fs=require('fs'),vm=require('vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
const writes=[],ctx={window:null,document:{write:value=>writes.push(value)},atob:value=>Buffer.from(value,'base64').toString('binary'),Uint8Array,TextDecoder,TextEncoder};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(input.codec,ctx);vm.runInContext(input.runtime,ctx);
ctx.__sp(0);ctx.__sp(1);ctx.__sp(2);
let rejected=0;for(const [pairs,count] of [[[[0,'a'],[0,'b']],2],[[[2,'a']],1],[[[-1,'a']],1],[[[0.5,'a']],1],[[[0,2]],1],[[[0,'a','b']],1],[[null],1],[[[0,'a']],2],[{},1],[[[0,'a']],0.5]]){
 try{ctx.__starrailPublicationLoadUI(pairs,count)}catch(e){rejected++}
}
console.log(JSON.stringify({writes,rejected,retained:ctx.__starrailPublicationUI}));
'''
  result=subprocess.run(['node','-e',code],input=json.dumps({'runtime':P.pooled_runtime(rows),'codec':(Path(P.__file__).resolve().parents[1]/'public/_publication'/P.CODEC_FILE).read_text('utf8')}),text=True,capture_output=True,check=True)
  actual=json.loads(result.stdout);self.assertEqual(actual['writes'],rows);self.assertEqual(actual['retained'],rows);self.assertEqual(actual['rejected'],10)

 def test_proof_storage_reordering_updates_calls_and_exact_inverse(self):
  with tempfile.TemporaryDirectory()as directory:
   root=Path(directory)/'dist';root.mkdir();report=Path(directory)/'report.json'
   bodies=['z metadata '*150,'a metadata '*150]
   originals=[]
   for i,body in enumerate(bodies):
    value='<html><head></head><body><p class="original-body" id="talk-'+str(i)+'">원문 '+str(i)+'</p><details class="source-details"><summary>근거</summary><pre>'+body+'</pre></details></body></html>'
    originals.append(value);(root/(str(i)+'.html')).write_text(value,'utf8')
   P.optimize(root,'/starrail-quests',report);P.verify(root,report)
   data=json.loads(report.read_text('utf8'));expand=P.expansion_function(data)
   self.assertEqual(expand((root/'0.html').read_text('utf8')),originals[0]);self.assertEqual(expand((root/'1.html').read_text('utf8')),originals[1])
   self.assertIn('__spr(1)',(root/'0.html').read_text('utf8'));self.assertIn('__spr(0)',(root/'1.html').read_text('utf8'))

 def test_only_editor_context_is_eligible(self):
  value='<p class="muted" data-publication-ui="source-context">연출 순서는 실제 플레이 순서와 다를 수 있습니다.</p>'
  self.assertTrue(P.source_context_ui(value))
  for added in (' id="talk-1"',' data-passage="dialogue"',' data-reading-link',' class="original-row"'):
   self.assertFalse(P.source_context_ui(value.replace(' data-publication-ui=',added+' data-publication-ui=')))
  for node in ('<a href="/source">원문</a>','<blockquote>대사</blockquote>','<summary>근거</summary>'):
   self.assertFalse(P.source_context_ui(value.replace('연출 순서는 실제 플레이 순서와 다를 수 있습니다.',node)))
 def test_shared_editor_context_exact_inverse_and_static_original(self):
  with tempfile.TemporaryDirectory()as directory:
   root=Path(directory)/'dist';root.mkdir();report=Path(directory)/'report.json'
   intro='<p class="muted" data-publication-ui="source-context">'+('원문 읽기 순서 안내 '*20)+'</p>'
   original='<html><head></head><body>'+intro+'<p class="original-row" id="talk-1">한국어 원문</p></body></html>'
   for name in ('a.html','b.html'):(root/name).write_text(original,'utf8')
   P.optimize(root,'/starrail-quests',report);P.verify(root,report)
   built=(root/'a.html').read_text('utf8');self.assertNotIn(intro,built);self.assertIn('id="talk-1">한국어 원문',built)
   self.assertEqual(P.expansion_function(json.loads(report.read_text('utf8')))(built),original)

class LocalUIShardTests(unittest.TestCase):
 def report(self,rows):
  records={};assets={};slot_map={}
  for record in P.ui_shards(rows):
   body=record.pop('body').encode();record['assetBytes']=len(body);record['assetSha256']=P.digest(body);record['url']='/starrail-quests/_shared/'+record['assetSha256'][:20]+'.js'
   records[str(record['id'])]=record;assets[record['url'].rsplit('/',1)[1]]={'sha256':record['assetSha256'],'kind':'ui-shard'}
   for slot in record['slots']:slot_map[slot]=record['id']
  body=P.sparse_runtime(len(rows),[records[str(i)]['url']for i in range(len(records))]).encode();digest=P.digest(body);url='/starrail-quests/_shared/'+digest[:20]+'.js'
  assets[url.rsplit('/',1)[1]]={'sha256':digest,'kind':'proof-runtime'}
  report={'base':'/starrail-quests','replacements':{},'scopes':{},'uiPool':rows,'uiShards':records,'assets':assets,'proofPool':[],'proofShards':{},'uiRuntime':{'url':url,'sha256':digest,'bytes':len(body),'totalSlots':len(rows),'maxSlots':512,'maxRawBytes':2000000,'loader':'indexed-local-ui.v1'}}
  report['proofCodecTags']='<script src="/starrail-quests/_publication/'+P.CODEC_FILE+'" data-pc-library></script><script src="'+url+'" data-pc-runtime></script>'
  return report,slot_map

 def test_ui_shards_preserve_b0_sorted_pairs_and_both_bounds(self):
  rows=['<nav>'+str(i)+' · 한글 😀 '+('value '*20)+'</nav>'for i in range(1100)]
  first=P.ui_shards(rows);self.assertEqual(first,P.ui_shards(rows))
  pairs=[]
  for record in first:
   raw=gzip.decompress(base64.b64decode(record['payload']));self.assertLessEqual(len(raw),2000000);self.assertLessEqual(record['count'],512)
   self.assertEqual(len(raw),record['rawBytes']);self.assertEqual(P.digest(raw),record['rawSha256']);pairs.extend(json.loads(raw))
  self.assertEqual(pairs,[list(pair)for pair in sorted(enumerate(rows),key=P.ui_storage_key)])
  fat=P.ui_shards(['한글 '*150000]*4);self.assertGreater(len(fat),1);self.assertTrue(all(r['rawBytes']<=2000000 for r in fat))

 def test_oversized_or_nonstring_ui_slots_are_rejected(self):
  with self.assertRaises(ValueError):P.ui_shards(['x'*2000000])
  with self.assertRaises(ValueError):P.ui_shards(['valid',1])

 def test_complete_ui_closure_rejects_cycles_unknown_and_excessive_depth(self):
  rows=['leaf','<script>__sp(0);</script>','<script>__sp(1);</script>']
  self.assertEqual(P.ui_closure(rows)('<script>__sp(2);</script>'),{0,1,2})
  for bad in [['<script>__sp(0);</script>'],['<script>__sp(1);</script>','<script>__sp(0);</script>'],['<script>__sp(2);</script>'],['leaf']+[f'<script>__sp({i});</script>'for i in range(16)]]:
   with self.assertRaises(ValueError):P.ui_closure(bad)
  with self.assertRaises(ValueError):P.ui_closure(rows)('<script>__sp(99);</script>')

 def test_sparse_real_pako_wire_atomic_guards_and_csv_validation(self):
  raw,payload=P.encoded_array([[0,'<nav>한글 😀</nav>'],[3,'마지막']]);invalid=[]
  for pairs in [[[1,'a'],[1,'b']],[[1,'a'],[8,'out']],[[1,'a'],[-1,'out']],[[1,'a'],[1.5,'out']],[[1,'a'],[2,3]],[[1,'a'],[2,'b','extra']],[[1,'a'],None]]:
   b,p=P.encoded_array(pairs);invalid.append({'payload':p,'bytes':len(b),'count':len(pairs)})
  code=r'''
const fs=require('fs'),vm=require('vm'),input=JSON.parse(fs.readFileSync(0,'utf8')),writes=[];
const ctx={window:null,document:{currentScript:{getAttribute:()=>''},write:v=>writes.push(v)},atob:v=>Buffer.from(v,'base64').toString('latin1'),Uint8Array,TextDecoder,TextEncoder};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(input.codec,ctx);vm.runInContext(input.runtime,ctx);
ctx.__starrailPublicationSelectUI('0,1');let imports=writes.splice(0);
let rejected=0;for(const value of ['1,0','0,0','2','-1','0.5','00',' 0','0,',null,'9007199254740992']){try{ctx.__starrailPublicationSelectUI(value)}catch(e){rejected++}}
if(writes.length)throw new Error('Invalid CSV partially imported scripts');
for(const bad of input.invalid){try{ctx.__starrailPublicationLoadUIShard(1,bad.payload,bad.bytes,bad.count)}catch(e){rejected++}}
if(Object.keys(ctx.__starrailPublicationUI).length||Object.keys(ctx.__starrailPublicationUIShardLoaded).length)throw new Error('Invalid shard partially committed');
ctx.__starrailPublicationLoadUIShard(0,input.payload,input.bytes,2);ctx.__sp(0);ctx.__sp(3);
for(const call of [()=>ctx.__starrailPublicationLoadUIShard(0,input.payload,input.bytes,2),()=>ctx.__starrailPublicationLoadUIShard(1,input.payload,input.bytes,2),()=>ctx.__starrailPublicationLoadUIShard(-1,input.payload,input.bytes,2),()=>ctx.__starrailPublicationLoadUIShard(.5,input.payload,input.bytes,2),()=>ctx.__starrailPublicationLoadUIShard(2,input.payload,input.bytes,2),()=>ctx.__starrailPublicationLoadUIShard(1,input.payload,input.bytes+1,2),()=>ctx.__starrailPublicationLoadUIShard(1,input.payload,2000001,2),()=>ctx.__starrailPublicationLoadUIShard(1,input.payload,input.bytes,513),()=>ctx.__starrailPublicationLoadUIShard(1,input.payload,input.bytes,1),()=>ctx.__sp(1),()=>ctx.__sp(8),()=>ctx.__sp(.5)]){try{call()}catch(e){rejected++}}
console.log(JSON.stringify({imports,writes,rejected,slots:Object.keys(ctx.__starrailPublicationUI),loaded:Object.keys(ctx.__starrailPublicationUIShardLoaded)}));
'''
  result=subprocess.run(['node','-e',code],input=json.dumps({'codec':(Path(P.__file__).resolve().parents[1]/'public/_publication'/P.CODEC_FILE).read_text('utf8'),'runtime':P.sparse_runtime(8,['/a.js','/b.js']),'payload':payload,'bytes':len(raw),'invalid':invalid}),text=True,encoding='utf8',capture_output=True,check=True)
  actual=json.loads(result.stdout);self.assertEqual(actual['imports'],['<script src="/a.js"></script>','<script src="/b.js"></script>']);self.assertEqual(actual['writes'],['<nav>한글 😀</nav>','마지막']);self.assertEqual(actual['rejected'],29);self.assertEqual(actual['slots'],['0','3']);self.assertEqual(actual['loaded'],['0'])

 def test_cross_shard_nested_closure_and_strict_parameterized_bootstrap_inverse(self):
  rows=['<nav>z 마지막</nav>']+[f'<nav>a{i:04}</nav>'for i in range(598)]+['<header><script>__sp(0);</script></header>']
  report,mapping=self.report(rows);self.assertNotEqual(mapping[0],mapping[599])
  selected=sorted({mapping[slot]for slot in P.ui_closure(rows)('<script>__sp(599);</script>')});csv=','.join(map(str,selected))
  tags=report['proofCodecTags'].replace('data-pc-runtime','data-pc-runtime="'+csv+'"');body='<script>__sp(599);</script><p class="original-body" id="talk-1">원문</p>'
  page='<html><head>'+tags+'</head><body>'+body+'</body></html>'
  expected='<html><head></head><body><header><nav>z 마지막</nav></header><p class="original-body" id="talk-1">원문</p></body></html>'
  expand=P.expansion_function(report);self.assertEqual(expand(page),expected)
  for bad in [page.replace('data-pc-runtime="'+csv+'"','data-pc-runtime="'+str(mapping[599])+'"'),page.replace(csv,'1,0'),page.replace(tags,''),page.replace(tags,tags+tags),page.replace('data-pc-runtime="'+csv+'"','data-pc-runtime'),page.replace('<head>'+tags+'</head>','<head></head>').replace('<body>','<body>'+tags)]:
   with self.assertRaises(ValueError):expand(bad)

 def test_sparse_receipt_mutations_reject_slot_string_payload_hash_manifest_and_bounds(self):
  report,_=self.report(['<nav>a</nav>','<nav>b</nav>'])
  changes=[lambda r:r['uiShards']['0'].__setitem__('rawSha256','0'*64),lambda r:r['uiShards']['0'].__setitem__('rawBytes',2000001),lambda r:r['uiShards']['0'].__setitem__('count',513),lambda r:r['uiShards']['0'].__setitem__('slots',[0,0]),lambda r:r['uiPool'].__setitem__(0,'changed'),lambda r:r['uiRuntime'].__setitem__('totalSlots',3),lambda r:r['uiRuntime'].__setitem__('sha256','0'*64),lambda r:r['uiShards']['0'].__setitem__('assetSha256','0'*64),lambda r:r['uiShards']['0'].__setitem__('url','/wrong.js'),lambda r:r['assets'].clear(),lambda r:r.__setitem__('proofCodecTags','wrong')]
  for change in changes:
   bad=json.loads(json.dumps(report));change(bad)
   with self.assertRaises(ValueError):P.expansion_function(bad)

 def test_parser_open_imports_finish_before_parent_and_nested_ui_calls(self):
  rows=['<nav>z 마지막</nav>']+[f'<nav>a{i:04}</nav>'for i in range(598)]+['<header><script>__sp(0);</script></header>']
  records=P.ui_shards(rows);urls=['/shard-'+str(i)+'.js'for i in range(len(records))];mapping={slot:r['id']for r in records for slot in r['slots']}
  csv=','.join(map(str,sorted({mapping[s]for s in P.ui_closure(rows)('<script>__sp(599);</script>')})))
  code=r'''
const fs=require('fs'),vm=require('vm'),input=JSON.parse(fs.readFileSync(0,'utf8')),events=[],bodies=[];
let ctx;const write=value=>{const external=/^<script src="([^"]+)"><\/script>$/.exec(value);if(external){events.push('import:'+external[1]);vm.runInContext(input.assets[external[1]],ctx);return;}events.push('body');bodies.push(value);for(const m of value.matchAll(/<script>__sp\(([0-9]+)\);<\/script>/g))vm.runInContext('__sp('+m[1]+');',ctx);};
ctx={window:null,document:{currentScript:{getAttribute:()=>input.csv},write},atob:v=>Buffer.from(v,'base64').toString('latin1'),Uint8Array,TextDecoder,TextEncoder};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(input.codec,ctx);vm.runInContext(input.runtime,ctx);events.push('runtime-ready');vm.runInContext('__sp(599);',ctx);
console.log(JSON.stringify({events,bodies,loaded:Object.keys(ctx.__starrailPublicationUIShardLoaded)}));
'''
  result=subprocess.run(['node','-e',code],input=json.dumps({'codec':(Path(P.__file__).resolve().parents[1]/'public/_publication'/P.CODEC_FILE).read_text('utf8'),'runtime':P.sparse_runtime(len(rows),urls),'assets':{urls[r['id']]:r['body']for r in records},'csv':csv}),text=True,encoding='utf8',capture_output=True,check=True)
  actual=json.loads(result.stdout);self.assertEqual(actual['events'],['import:/shard-0.js','import:/shard-1.js','runtime-ready','body','body']);self.assertEqual(actual['bodies'],[rows[599],rows[0]]);self.assertEqual(actual['loaded'],['0','1'])

 def test_adjacent_ui_runs_append_only_and_reuse_exact_composites(self):
  rows=['<nav>한글 😀</nav>','<aside>연결</aside>'];original=list(rows);counts=P.Counter()
  def allocate(value):
   if value not in rows:rows.append(value)
   return f'<script>__sp({rows.index(value)});</script>'
  run='<script>__sp(0);</script><script>__sp(1);</script>'
  passage='<p class="original-body" id="talk-1">그대로 읽는 원문</p>'
  compact=P.share_adjacent_ui(run+passage+run,allocate,counts)
  self.assertEqual(rows[:2],original);self.assertEqual(rows[2:],[run])
  self.assertEqual(compact,'<script>__sp(2);</script>'+passage+'<script>__sp(2);</script>')
  self.assertEqual(counts['sharedAdjacentUIRuns'],2);self.assertEqual(counts['sharedAdjacentUICalls'],4)
  self.assertEqual(counts['sharedAdjacentUIBytesSaved'],len((run+passage+run).encode())-len(compact.encode()))
  report={'replacements':{},'scopes':{},'uiPool':rows,'proofPool':[],'proofShards':{}}
  self.assertEqual(P.expansion_function(report)(compact),rows[0]+rows[1]+passage+rows[0]+rows[1])

 def test_adjacent_ui_sharing_preserves_every_noncontiguous_parser_boundary(self):
  call='<script>__sp(0);</script>'
  for boundary in [' ','\n','<!-- -->','<p class="original-body" id="talk-1">원문</p>','<script>__spr(0);</script>','<script type="module">run()</script>']:
   text=call+boundary+call;counts=P.Counter()
   def unexpected(value):raise AssertionError('Noncontiguous parser boundary was pooled')
   self.assertEqual(P.share_adjacent_ui(text,unexpected,counts),text);self.assertFalse(counts)

 def test_adjacent_ui_keeps_the_original_nojs_suffix_slot_boundary(self):
  text='<script>__sp(0);</script><script>__sp(1);</script><noscript><nav>메뉴</nav></noscript>'
  def unexpected(value):raise AssertionError('No-JS suffix slot boundary was pooled')
  counts=P.Counter();self.assertEqual(P.share_adjacent_ui(text,unexpected,counts),text);self.assertFalse(counts)

 def test_adjacent_ui_composite_transitive_closure_and_bootstrap_inverse(self):
  rows=['<nav>원문 메뉴</nav>','<header><script>__sp(0);</script></header>','<aside>연결 목록</aside>']
  rows.append('<script>__sp(1);</script><script>__sp(2);</script>')
  report,mapping=self.report(rows);selected=sorted({mapping[s]for s in P.ui_closure(rows)('<script>__sp(3);</script>')})
  self.assertEqual(P.ui_closure(rows)('<script>__sp(3);</script>'),{0,1,2,3})
  tags=report['proofCodecTags'].replace('data-pc-runtime','data-pc-runtime="'+','.join(map(str,selected))+'"')
  passage='<p class="original-body" id="talk-1">원문·화자·앵커 보존</p>'
  page='<html><head>'+tags+'</head><body><script>__sp(3);</script>'+passage+'</body></html>'
  self.assertEqual(P.expansion_function(report)(page),'<html><head></head><body><header><nav>원문 메뉴</nav></header><aside>연결 목록</aside>'+passage+'</body></html>')

 def test_real_parser_order_for_composite_and_two_level_nested_ui(self):
  rows=['<nav>z 마지막</nav>']+[f'<nav>a{i:04}</nav>'for i in range(598)]+['<header><script>__sp(0);</script></header>']
  rows.append('<script>__sp(599);</script><script>__sp(1);</script>')
  records=P.ui_shards(rows);urls=['/shard-'+str(i)+'.js'for i in range(len(records))];mapping={slot:r['id']for r in records for slot in r['slots']}
  csv=','.join(map(str,sorted({mapping[s]for s in P.ui_closure(rows)('<script>__sp(600);</script>')})))
  code=r'''
const fs=require('fs'),vm=require('vm'),input=JSON.parse(fs.readFileSync(0,'utf8')),events=[],bodies=[];
let ctx;const write=value=>{const external=/^<script src="([^"]+)"><\/script>$/.exec(value);if(external){events.push('import:'+external[1]);vm.runInContext(input.assets[external[1]],ctx);return;}events.push('body');bodies.push(value);for(const m of value.matchAll(/<script>__sp\(([0-9]+)\);<\/script>/g))vm.runInContext('__sp('+m[1]+');',ctx);};
ctx={window:null,document:{currentScript:{getAttribute:()=>input.csv},write},atob:v=>Buffer.from(v,'base64').toString('latin1'),Uint8Array,TextDecoder,TextEncoder};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(input.codec,ctx);vm.runInContext(input.runtime,ctx);events.push('runtime-ready');vm.runInContext('__sp(600);',ctx);
console.log(JSON.stringify({events,bodies,loaded:Object.keys(ctx.__starrailPublicationUIShardLoaded)}));
'''
  result=subprocess.run(['node','-e',code],input=json.dumps({'codec':(Path(P.__file__).resolve().parents[1]/'public/_publication'/P.CODEC_FILE).read_text('utf8'),'runtime':P.sparse_runtime(len(rows),urls),'assets':{urls[r['id']]:r['body']for r in records},'csv':csv}),text=True,encoding='utf8',capture_output=True,check=True)
  actual=json.loads(result.stdout);self.assertEqual(actual['events'],['import:/shard-0.js','import:/shard-1.js','runtime-ready','body','body','body','body'])
  self.assertEqual(actual['bodies'],[rows[600],rows[599],rows[0],rows[1]]);self.assertEqual(actual['loaded'],['0','1'])

 def test_actual_content_hashed_ui_asset_tampering_fails_full_inverse_verifier(self):
  with tempfile.TemporaryDirectory()as directory:
   root=Path(directory)/'dist';root.mkdir();receipt=Path(directory)/'report.json';original='<html><head></head><body><header>목록</header><p class="original-body" id="talk-1">원문</p></body></html>'
   (root/'one.html').write_text(original,'utf8');P.optimize(root,'/starrail-quests',receipt);P.verify(root,receipt)
   report=json.loads(receipt.read_text('utf8'));record=report['uiShards']['0'];file=root/'_shared'/record['url'].rsplit('/',1)[1];file.write_bytes(file.read_bytes()+b' ')
   with self.assertRaisesRegex(ValueError,'Shared asset differs'):P.verify(root,receipt)

 def test_legacy_dense_and_indexed_receipts_remain_exact(self):
  # Legacy receipt wire uses the same original-slot uiPool regardless of how its runtime stores it.
  report={'replacements':{},'scopes':{},'uiPool':['<nav>옛 원문</nav>'],'proofPool':[],'proofShards':{}}
  for kind in ('dense','indexed'):
   self.assertEqual(P.expansion_function(report)('<script>__sp(0);</script>'),'<nav>옛 원문</nav>',kind)

if __name__=='__main__':unittest.main()
