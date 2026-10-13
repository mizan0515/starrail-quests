"""Music-screen references qualified by installed native/Lua consumer domains."""
import hashlib,json
from pathlib import Path

KIND='MUSIC_RHYTHM_SCREEN_TALK_SENTENCE_ID'
PROOF_SHA='e2a4d9d46dfa668494508f6dad6833607e622345b1cb56ee6137ae835d16b130'
raw=Path(__file__).with_name('music_rhythm_text_proof.json').read_bytes()
if hashlib.sha256(raw).hexdigest()!=PROOF_SHA:raise ValueError('Music-screen consumer proof changed')
PROOF=json.loads(raw)
SOURCES=PROOF['configurationSources']

def uint(v):return type(v)is int and 0<v<2**32

def references(obj,path,pointer=''):
    if path not in SOURCES or not isinstance(obj,dict):return
    bubble=obj.get('BubbleConfig')
    if obj.get('NotifyType')=='Bubble' and isinstance(bubble,dict) and uint(bubble.get('BubbleId')):
        yield bubble['BubbleId'],pointer+'/BubbleConfig/BubbleId',KIND
    auto=obj.get('AutoBubble')
    if isinstance(auto,dict) and uint(auto.get('HitTextId')) and uint(auto.get('MissTextId')):
        for field in ('HitTextId','MissTextId'):yield auto[field],pointer+'/AutoBubble/'+field,KIND

def at(obj,pointer):
    if not pointer:return obj
    for part in pointer.strip('/').split('/'):
        obj=obj[int(part)]if isinstance(obj,list)else obj[part.replace('~1','/').replace('~0','~')]
    return obj

def source_record(obj,pointer):
    parent,field=pointer.rsplit('/',1);node=at(obj,parent)
    if field=='BubbleId':
        owner=at(obj,parent.rsplit('/',1)[0]);valid=owner.get('NotifyType')=='Bubble' and parent.endswith('/BubbleConfig');usage='말풍선'
    else:
        valid=field in ('HitTextId','MissTextId')and parent.endswith('/AutoBubble')and uint(node.get('HitTextId'))and uint(node.get('MissTextId'));usage='성공 시 문구'if field=='HitTextId'else'실패 시 문구'
    if not valid or not uint(node.get(field)):raise ValueError('Unqualified music-screen field')
    return {'sourceRole':'SCREEN_TEXT','usageLabel':usage,'recordContext':{'pointer':parent,'fields':node,'serialized':json.dumps(node,ensure_ascii=False,indent=2)},'screenReference':{'field':field,'consumerProofSha256':PROOF_SHA,'callerSourceKind':PROOF['callerSourceKind'],'installedConfigEditionMatch':None,'runtimeDisplayConfirmed':False}}

def public_proof():
    return {'schema':PROOF['schema'],'proofSha256':PROOF_SHA,'role':'SCREEN_TEXT','callerSourceKind':PROOF['callerSourceKind'],'installedConfigEditionMatch':None,'runtimeDisplayConfirmed':False,'assemblySha256':next(p['sha256']for p in PROOF['nativeInputs']if p['name']=='GameAssembly.dll'),'luaModuleSha256':PROOF['lua']['entrySha256'],'consumer':'TalkSentenceConfigExcelTable.GetData → TalkSentenceText → SafeSetTextID','fields':{'BubbleId':'말풍선','HitTextId':'성공 시 문구','MissTextId':'실패 시 문구'},'nativeFunctions':[{'method':f['label'],'sha256':f['sha256'],'bytes':f['bytes']}for f in PROOF['functions']]}
