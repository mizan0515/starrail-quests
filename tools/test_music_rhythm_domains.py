"""Reject actual wrong-domain/conditional music-screen inputs."""
import copy,unittest
from music_rhythm_text_refs import references,source_record,SOURCES

class MusicDomains(unittest.TestCase):
    def setUp(self):
        self.path=next(iter(SOURCES))
        self.bubble={'NotifyType':'Bubble','BubbleConfig':{'BubbleId':821215000}}
        self.auto={'AutoBubble':{'HitTextId':821216203,'MissTextId':821216001}}
    def test_declared_screen_fields(self):
        self.assertEqual([r[0]for r in references(self.bubble,self.path)],[821215000])
        self.assertEqual([r[0]for r in references(self.auto,self.path)],[821216203,821216001])
    def test_voice_id_is_not_bubble(self):
        self.bubble['BubbleConfig']={'VoiceID':821215000}
        self.assertEqual(list(references(self.bubble,self.path)),[])
    def test_wrong_notification_route(self):
        for route in ('Sound','Animation','2',2,True,None):
            self.bubble['NotifyType']=route
            self.assertEqual(list(references(self.bubble,self.path)),[])
    def test_wrong_source_or_dynamic_argument(self):
        self.assertEqual(list(references(self.bubble,'Story/Mission/example.json')),[])
        for value in (True,-1,0,2**32,'821215000',{'IsDynamic':True,'Value':821215000}):
            self.bubble['BubbleConfig']['BubbleId']=value
            self.assertEqual(list(references(self.bubble,self.path)),[])
    def test_actual_both_auto_ids_guard(self):
        for field in ('HitTextId','MissTextId'):
            for value in (0,None,True,{},'821216001',2**32):
                obj=copy.deepcopy(self.auto);obj['AutoBubble'][field]=value
                self.assertEqual(list(references(obj,self.path)),[])
    def test_source_position_role_and_limits(self):
        record=source_record(self.bubble,'/BubbleConfig/BubbleId')
        self.assertEqual(record['sourceRole'],'SCREEN_TEXT')
        self.assertIsNone(record['screenReference']['installedConfigEditionMatch'])
        self.assertFalse(record['screenReference']['runtimeDisplayConfirmed'])
        self.assertEqual(record['recordContext']['fields'],{'BubbleId':821215000})
        for obj,pointer in [({'NotifyType':'Sound','BubbleConfig':{'BubbleId':821215000}},'/BubbleConfig/BubbleId'),(self.auto,'/AutoBubble/VoiceID')]:
            with self.assertRaises(ValueError):source_record(obj,pointer)

if __name__=='__main__':unittest.main()
