"""Reject cross-domain voice IDs and undeclared table consumers."""
import unittest
from multivoice_configuration_refs import SOURCE,KIND,references,source_record

class MultiVoiceDomainTests(unittest.TestCase):
 def test_native_canary_keeps_voice_ids_out_of_talk_targets(self):
  row={'TalkSentenceID':546040001,'VoiceIDList':[546040101,546040102]}
  self.assertEqual(list(references(row,SOURCE,'/17')),[(546040001,'/17/TalkSentenceID',KIND)])
  record=source_record(row,'/17')
  self.assertEqual(record['sourceRole'],'NON_SPOKEN_CONFIGURATION_REFERENCE')
  self.assertEqual(record['recordContext']['fields']['VoiceIDList'],[546040101,546040102])
 def test_same_number_in_other_table_does_not_establish_consumer(self):
  row={'TalkSentenceID':546040001,'VoiceIDList':[546040101]}
  self.assertEqual(list(references(row,'ExcelOutput/OtherVoice.json','/17')),[])
 def test_flat_scan_and_schema_drift_cannot_create_lookups(self):
  for row in ({'VoiceIDList':[546040001]}, {'TalkSentenceID':True,'VoiceIDList':[546040101]}, {'TalkSentenceID':546040001,'VoiceIDList':[]}, {'TalkSentenceID':546040001,'VoiceIDList':[546040101],'FloorID':546040102}):
   self.assertEqual(list(references(row,SOURCE,'/17')),[])
   with self.assertRaises(ValueError):source_record(row,'/17')

if __name__=='__main__':unittest.main()
