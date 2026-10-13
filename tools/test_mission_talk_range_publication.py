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

if __name__=='__main__': unittest.main()
