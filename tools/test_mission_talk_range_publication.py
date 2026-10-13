"""Independent wire/receipt rejection cases for range reader metadata replay."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_mission_talk_ranges import ui_wire_rows,publication_metadata_expander

def wire(values,count=None,dense=False,byte_delta=0):
 raw=json.dumps(values,ensure_ascii=False,separators=(',',':')).encode('utf8')
 encoded=base64.b64encode(gzip.compress(raw,mtime=0)).decode('ascii')
 inner=f'JSON.parse(__starrailPublicationDecode("{encoded}",{len(raw)+byte_delta}))'
 return f'window.__starrailPublicationUI={inner};' if dense else f'__starrailPublicationLoadUI({inner},{len(values) if count is None else count});'

def shard_wire(identifier,pairs,byte_delta=0,count_delta=0):
 raw=json.dumps(pairs,ensure_ascii=False,separators=(',',':')).encode('utf8')
 payload=base64.b64encode(gzip.compress(raw,mtime=0)).decode()
 return f'__starrailPublicationLoadUIShard({identifier},"{payload}",{len(raw)+byte_delta},{len(pairs)+count_delta});\n',raw,payload

def sparse_wire(count,urls):
 return f'window.__starrailPublicationUI=new Array({count});\nwindow.__starrailPublicationUIURLs='+json.dumps(urls,separators=(',',':'))+';\n'

class WireCases(unittest.TestCase):
 def test_indexed_storage_restores_original_slots(self):
  self.assertEqual(ui_wire_rows(wire([[1,'뒤쪽 원문'],[0,'앞쪽 원문']])),['앞쪽 원문','뒤쪽 원문'])
 def test_legacy_dense_wire_is_preserved(self):
  self.assertEqual(ui_wire_rows(wire(['앞쪽 원문','뒤쪽 원문'],dense=True)),['앞쪽 원문','뒤쪽 원문'])
 def test_malformed_slot_domains_are_rejected(self):
  cases=[([[True,'x']],1),([[0,'x'],[0,'y']],2),([[-1,'x']],1),([[1,'x']],1),([[0,7]],1),([[0]],1),([{'slot':0,'text':'x'}],1),([[0,'x']],2)]
  for values,count in cases:
   with self.subTest(values=values,count=count),self.assertRaises(ValueError): ui_wire_rows(wire(values,count))
 def test_byte_length_drift_is_rejected(self):
  with self.assertRaises(ValueError): ui_wire_rows(wire([[0,'원문']],byte_delta=1))
 def test_multiple_wire_declarations_are_rejected(self):
  with self.assertRaises(ValueError): ui_wire_rows(wire([[0,'원문']])*2)
 def test_dense_nontext_is_rejected(self):
  with self.assertRaises(ValueError): ui_wire_rows(wire([False],dense=True))
 def test_sparse_wire_preserves_original_slots(self):
  shards={'/a.js':shard_wire(0,[[1,'뒤쪽']])[0],'/b.js':shard_wire(1,[[0,'앞쪽']])[0]}
  self.assertEqual(ui_wire_rows(sparse_wire(2,list(shards)),shards),['앞쪽','뒤쪽'])
 def test_sparse_actual_wire_rejects_corrupt_domains(self):
  cases=[(2,[[0,'a']],[[0,'b']],0,0),(2,[[0,'a']],[[2,'b']],0,0),(2,[[0,'a']],[[1,'b']],1,0),(2,[[0,'a']],[[1,'b']],0,1),(3,[[0,'a']],[[1,'b']],0,0),(2,[[True,'a']],[[1,'b']],0,0)]
  for count,first,second,byte_delta,count_delta in cases:
   with self.subTest(case=(count,first,second,byte_delta,count_delta)),self.assertRaises(ValueError):
    ui_wire_rows(sparse_wire(count,['/a.js','/b.js']),{'/a.js':shard_wire(0,first,byte_delta,count_delta)[0],'/b.js':shard_wire(1,second)[0]})
 def test_sparse_manifest_cannot_substitute_or_duplicate_assets(self):
  body=shard_wire(0,[[0,'a']])[0]
  for urls,shards in [(['/a.js'],{'/b.js':body}),(['/a.js','/a.js'],{'/a.js':body})]:
   with self.subTest(urls=urls),self.assertRaises(ValueError):ui_wire_rows(sparse_wire(1,urls),shards)

class ReceiptCases(unittest.TestCase):
 def fixture(self,root,rows):
  shared=root/'_shared';shared.mkdir()
  runtime=wire([[i,row] for i,row in reversed(list(enumerate(rows)))]).encode()
  name=hashlib.sha256(runtime).hexdigest()[:20]+'.js';(shared/name).write_bytes(runtime)
  report={'schema':'starrail-publication-dedup.v3','assets':{name:{'kind':'proof-runtime','sha256':hashlib.sha256(runtime).hexdigest()}},'uiPool':rows,'proofShards':{},'proofPool':[],'proofCodecFiles':{},'compressedProofs':{}}
  path=root/'receipt.json';path.write_text(json.dumps(report,ensure_ascii=False),'utf8')
  return report,path,name
 def test_catalog_return_is_replayed_from_actual_wire(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);_,path,_=self.fixture(root,['<a data-catalog-return href="/index.html">목록</a>'])
   self.assertIn('data-catalog-return',publication_metadata_expander(root,path)('<script>__sp(0);</script>'))
 def test_changed_actual_runtime_is_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);_,path,name=self.fixture(root,['원문']);(root/'_shared'/name).write_text('changed','utf8')
   with self.assertRaises(ValueError): publication_metadata_expander(root,path)
 def test_receipt_cannot_substitute_ui_for_actual_wire(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);report,path,_=self.fixture(root,['원문']);report['uiPool']=['다른 문구'];path.write_text(json.dumps(report),'utf8')
   with self.assertRaises(ValueError): publication_metadata_expander(root,path)
 def test_ui_slot_out_of_range_is_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);_,path,_=self.fixture(root,['원문']);expand=publication_metadata_expander(root,path)
   with self.assertRaises(ValueError): expand('<script>__sp(1);</script>')
 def test_self_referencing_ui_is_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);_,path,_=self.fixture(root,['<script>__sp(0);</script>']);expand=publication_metadata_expander(root,path)
   with self.assertRaises(ValueError): expand('<script>__sp(0);</script>')
 def test_changed_actual_proof_shard_is_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);report,path,_=self.fixture(root,['원문']);name='a'*20+'.js';(root/'_shared'/name).write_text('changed','utf8')
   report['proofShards']={'0':{'url':'/starrail-quests/_shared/'+name,'assetSha256':'0'*64}};path.write_text(json.dumps(report),'utf8')
   with self.assertRaises(ValueError): publication_metadata_expander(root,path)
 def test_changed_actual_codec_is_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);report,path,_=self.fixture(root,['원문']);(root/'_publication').mkdir();(root/'_publication'/'codec.js').write_text('changed','utf8')
   report['proofCodecFiles']={'codec.js':{'bytes':7,'sha256':'0'*64}};path.write_text(json.dumps(report),'utf8')
   with self.assertRaises(ValueError): publication_metadata_expander(root,path)

class SparseReceiptCases(unittest.TestCase):
 def fixture(self,root,rows):
  shared=root/'_shared';shared.mkdir();records={};assets={};urls=[]
  for index,row in enumerate(rows):
   body,raw,payload=shard_wire(index,[[index,row]]);body=body.encode();digest=hashlib.sha256(body).hexdigest();name=digest[:20]+'.js';url='/starrail-quests/_shared/'+name;urls.append(url);(shared/name).write_bytes(body)
   assets[name]={'kind':'ui-shard','sha256':digest};records[str(index)]={'id':index,'url':url,'assetSha256':digest,'assetBytes':len(body),'rawBytes':len(raw),'rawSha256':hashlib.sha256(raw).hexdigest(),'payload':payload,'slots':[index],'count':1}
  runtime=sparse_wire(len(rows),urls).encode();digest=hashlib.sha256(runtime).hexdigest();name=digest[:20]+'.js';(shared/name).write_bytes(runtime);assets[name]={'kind':'proof-runtime','sha256':digest}
  runtime_record={'url':'/starrail-quests/_shared/'+name,'sha256':digest,'bytes':len(runtime),'totalSlots':len(rows),'maxSlots':512,'maxRawBytes':2000000,'loader':'indexed-local-ui.v1'}
  report={'schema':'starrail-publication-dedup.v3','assets':assets,'uiPool':rows,'uiShards':records,'uiRuntime':runtime_record,'proofShards':{},'proofPool':[],'proofCodecFiles':{},'compressedProofs':{}}
  path=root/'receipt.json';path.write_text(json.dumps(report,ensure_ascii=False),'utf8')
  tag=lambda selected:f'<head><script src="{runtime_record["url"]}" data-pc-runtime="{selected}"></script></head>'
  return report,path,tag
 def test_page_selection_must_cover_nested_ui_before_first_call(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);_,path,tag=self.fixture(root,['<script>__sp(1);</script>','<a data-catalog-return>목록</a>']);expand=publication_metadata_expander(root,path)
   self.assertIn('data-catalog-return',expand(tag('0,1')+'<script>__sp(0);</script>'))
   for selection in ('0','1','1,0','0,0','2','00',''):
    with self.subTest(selection=selection),self.assertRaises(ValueError):expand(tag(selection)+'<script>__sp(0);</script>')
 def test_missing_or_changed_bootstrap_is_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);_,path,tag=self.fixture(root,['원문']);expand=publication_metadata_expander(root,path)
   for text in ['<script>__sp(0);</script>',tag('0')+tag('0')+'<script>__sp(0);</script>',tag('0').replace('src="','src="wrong')+'<script>__sp(0);</script>']:
    with self.subTest(text=text),self.assertRaises(ValueError):expand(text)
 def test_actual_sparse_receipt_cannot_relabel_original_slots(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);report,path,_=self.fixture(root,['원문']);report['uiShards']['0']['slots']=[1];path.write_text(json.dumps(report),'utf8')
   with self.assertRaises(ValueError):publication_metadata_expander(root,path)
 def test_bootstrap_must_precede_body_calls_inside_head(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);_,path,tag=self.fixture(root,['원문']);expand=publication_metadata_expander(root,path)
   for text in [tag('0').replace('<head>','').replace('</head>','')+'<script>__sp(0);</script>','<script>__sp(0);</script>'+tag('0')]:
    with self.subTest(text=text),self.assertRaises(ValueError):expand(text)
 def test_sparse_cycle_is_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);_,path,tag=self.fixture(root,['<script>__sp(0);</script>']);expand=publication_metadata_expander(root,path)
   with self.assertRaises(ValueError):expand(tag('0')+'<script>__sp(0);</script>')

if __name__=='__main__': unittest.main()
