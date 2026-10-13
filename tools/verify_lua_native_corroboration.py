"""Strict one-scene cached caller corroboration of the preserved Lua corpus.

source_check(repo,data) returns the validated overlay. Default requires only this
stdlib file and three repository JSON files. External byte replays are explicit;
no producer, game, Lua or JavaScript code is executed.
"""
import sys
sys.dont_write_bytecode = True
import argparse
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tarfile

SITE = Path(__file__).resolve().parents[1]
SCENE = 'lua-timeline-9192c8b22d0d8304'
BASE = '10113f8c168b04e331d1c723d6e80553acbce679e3c7d6c7704c9c097f3214b6'
BRIDGE = '4f0e94bb85a96f92618ffa51ef45dbc040819ee34a78bb8a7ce525db12b1c138'
OVERLAY = 'b3827023d6546a57599cf63b56bd35dda1fd3b45a434f84a11ba36dcd0370822'
CANONICAL = '07679535fc5d68e737fe65cc24b9c01daed91f20d107179e6899a24e41e646d1'
ACTUAL_AUDIT = 'da59d2ee66ec60041ca80776b6832e1b964ded05181a7c27b312b940371bef7f'
CORRECTED = '캐시된 호출 자료의 전체 경계와 연출 호출 필드를 확인했습니다.'
STALE = '호출자 바이너리의 전체 해석은 미지원 상태'


def require(value, message):
    if not value: raise AssertionError(message)


def sha(raw): return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return sha(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8'))


def file_sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(4*1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def load(path): return json.loads(Path(path).read_bytes())


def at(value,pointer):
    for token in pointer.split('/')[1:]:
        key=token.replace('~1','/').replace('~0','~');value=value[int(key)] if isinstance(value,list) else value[key]
    return value


def safe(value):
    if isinstance(value,dict):
        require(not any(k in value for k in ('privateReplay','packPath','objectFolder','nativePackPath')),'Private field in public overlay')
        for item in value.values():safe(item)
    elif isinstance(value,list):
        for item in value:safe(item)
    elif isinstance(value,str):require(not re.search(r'[A-Z]:[/\\]|file://|\\\\',value,re.I),'Private absolute path leaked')
    elif type(value)is int:require(abs(value)<=2**53-1,'Unsafe public integer precision')


def baseline(repo):
    raw=(Path(repo)/'data/lua-timeline-dialogue.json').read_bytes();require(sha(raw)==BASE,'Preserved Lua projection changed')
    bridge=(Path(repo)/'data/lua-snapshot-owner-bridges.json').read_bytes();require(sha(bridge)==BRIDGE,'Preserved Lua owner bridge changed')
    data=json.loads(raw);scene,=[s for s in data['scenes'] if s['id']==SCENE]
    reference,=scene['proof']['references'];source=data['sourceProofs'][reference['sourceIndex']]
    return data,scene,reference,source


def source_check(repo,data):
    """Return the one hard-closed Lua overlay; never reuse public-corpus indices."""
    safe(data)
    require(data['schema']=='starrail-lua-timeline-cached-caller-corroboration.v1','Lua corroboration schema differs')
    require(data['baseProjectionSha256']==BASE and data['ownerBridgeSha256']==BRIDGE,'Original Lua version boundary differs')
    base,scene,ref,old=baseline(repo)
    require(data['sceneId']==SCENE and data['referenceIndex']==0 and data['snapshotSourceIndex']==ref['sourceIndex']=='snapshot-1ca2d056df4a8452dd4f','Exact sole Lua scene/reference differs')
    source,proof=data['source'],data['proof']
    require(source['logicalJsonPath']==old['logicalJsonPath'] and source['pointer']==ref['pointer']
            and source['timelineName']==ref['timelineName']==ref['snapshotTask']['TimelineName'],'Exact original source/pointer/name differs')
    require(ref['nativeCallerWholeEOF'] is False and old['nativeCallerWholeEOF'] is False
            and ref['nativeInstalledCallerClaim'] is False,'Old frozen caller boundary changed')
    require(ref['context']['typedContainer']=={'type':'RPG.GameCore.PlayTimeline','pointer':source['pointer'].rsplit('/',1)[0]}
            and ref['snapshotTask']['$type']=='RPG.GameCore.PlayTimeline' and ref['snapshotTask']['Parameters']==[],'Exact original typed consumer differs')
    require(source['typedConsumer']=='RPG.GameCore.PlayTimeline' and source['wholeEOFStatus']=='WHOLE_NATIVE_FIELDS_EOF_PASS'
            and source['trailingByteRejected'] is True,'Typed full cached source proof differs')
    frontier=old['rawConsumerByteFrontier']
    require(source['entrySha256']==frontier['entrySha256'] and source['consumedBytes']==frontier['nativeBytes']==971,'Exact previously stopped entry identity differs')
    require(source['fieldSpan']==[596,652] and source['terminalSpan']==[593,654] and source['mask']==14 and source['nativeType']==8,'Exact serialized terminal bounds/type differ')
    require(source['catalogMatch']['length']==971 and source['catalogMatch']['packExpectedBytes']==source['callerPack']['bytes']
            and 0<=source['catalogMatch']['offset']<source['catalogMatch']['offset']+971<=source['callerPack']['bytes'],'Caller entry escapes cached pack')
    require(source['callerEditionStatus']=='CACHED_SNAPSHOT_CURRENT_INSTALLED_EDITION_UNVERIFIED'
            and source['runtimePlaybackStatus']=='UNVERIFIED','Edition/runtime uncertainty weakened')
    require('assets/asbres/'+source['timelineName'].lower()==scene['source']==scene['proof']['container']['key']==proof['containerKey']
            and proof['rootSha256']==scene['proof']['root']['sha256'] and proof['rootPathID']==scene['proof']['root']['pathID']
            and proof['cabSha256']==scene['proof']['receipt']['cabSha256'],'Exact Lua corpus native root/container/CAB differs')
    require(proof['ownerChainSha256']==canonical(old['ownerChain']) and old['mission']=='quest-1040554'
            and scene['owners']==[{'mission':'quest-1040554','canonicalMission':'quest-1040554','title':'Fate/침묵의 시대로의 귀환'}],'Exact original owner chain differs')
    require(proof['captionRowsSha256']==canonical(scene['rows']) and len(scene['rows'])==4
            and sorted(row['slot'] for row in scene['rows'])==[1,2,3,4] and proof['existingScreenRole']=='SCREEN_TEXT','Exact four caption slots differ')
    for row in scene['rows']:
        require(row['role']=='SCREEN_TEXT' and row['object']['class']=='ShowFateShowCaptionDialogClip'
                and row['nativeConsumer']['lookupClass']=='RPG.GameCore.TalkSentenceConfigExcelTable'
                and row['nativeConsumer']['textField']=='TalkSentenceText' and row['nativeConsumer']['screenCall']=='SafeSetTextID','Existing caption consumer domain differs')
    require(canonical(data)==CANONICAL,'Closed Lua caller overlay changed')
    return data


class Primitive:
    def __init__(self,raw,start,end):
        require(0<=start<=end<=len(raw),'Native terminal bounds');self.raw,self.at,self.end=raw,start,end
    def uint(self):
        value,shift=0,0
        while self.at<self.end and shift<35:
            byte=self.raw[self.at];self.at+=1;value|=(byte&127)<<shift
            if not byte&128:
                require(value<2**32 and not(shift and byte==0),'Native UInt32 invalid encoding');return value
            shift+=7
        raise AssertionError('Truncated/overflowing native UInt32')
    def string(self):
        count=self.uint();require(self.at+count<=self.end,'Native string bound');value=self.raw[self.at:self.at+count].decode('utf8',errors='strict');self.at+=count;return value


def terminal_check(raw,source):
    rd=Primitive(raw,*source['terminalSpan']);require(rd.uint()==1976 and rd.uint()==14,'Actual PlayTimeline discriminator/mask differs')
    start=rd.at;require(rd.string()==source['timelineName'] and[start,rd.at]==source['fieldSpan'],'Actual TimelineName literal/span differs')
    require(rd.uint()==8 and rd.uint()==0 and rd.at==rd.end,'Actual Timeline type/empty parameters/whole terminal differs')


def audit_check(repo,data,directory,native_inputs=None,legacy_audit=None,installed_root=None,archive=None):
    raw=(Path(directory)/'phase11-lua-caller-actual-audit.json').read_bytes();require(sha(raw)==ACTUAL_AUDIT,'Frozen bounded actual audit SHA differs');audit=json.loads(raw)
    fields=Path(native_inputs) if native_inputs else Path(directory).parent/'star-fields'
    code=data['sourceCodeReceipt'];replayraw=(fields/'phase8-new-field-replay.json').read_bytes();require(sha(replayraw)==code['wholeSourceReplaySha256'],'Frozen whole caller source replay differs')
    require(file_sha(fields/code['file'])==code['sha256'] and file_sha(fields/'phase8-field-contracts.json')==code['schemaContractsSha256']
            and file_sha(fields/'phase8-independent-replay.json')==code['independentReplaySha256']
            and file_sha(fields/'phase8-current-native-profile-raw-replay.json')==code['currentProfileSha256'],'Source code/schema/current profile hash boundary differs')
    source=data['source'];receipt,=[r for r in json.loads(replayraw)['results'] if r['source']==source['logicalJsonPath'] and r['sha256']==source['entrySha256']]
    require(receipt['status']=='WHOLE_NATIVE_FIELDS_EOF_PASS' and receipt['bytes']==971 and receipt['trailingByteRejected'] is True,'Frozen cached source whole EOF differs')
    _,scene,ref,old=baseline(repo);require(receipt['descriptor']['ownerChain']==old['ownerChain'] and receipt['descriptor']['mission']==old['mission'],'Exact actual caller owner chain differs')
    pack=Path(receipt['pack']['path']).read_bytes();require(sha(pack)==source['callerPack']['sha256'] and len(pack)==source['callerPack']['bytes'],'Actual cached pack SHA/size differs')
    c=source['catalogMatch'];body=pack[c['offset']:c['offset']+971];require(sha(body)==source['entrySha256'] and len(body)==971,'Actual whole cached entry SHA/size differs')
    spans={s['pointer']:s for s in receipt['fieldSpans']};require(len(spans)==len(receipt['fieldSpans']) and spans['']=={'pointer':'','start':0,'end':971},'Frozen whole source EOF field partition differs')
    for span in spans.values():
        require(0<=span['start']<=span['end']<=971,'Source field span escapes caller')
        if span['pointer']:at(receipt['fields'],span['pointer'])
    parent=source['pointer'].rsplit('/',1)[0]
    require(spans[source['pointer']]=={'pointer':source['pointer'],'start':596,'end':652}
            and spans[parent]=={'pointer':parent,'start':593,'end':654},'Exact typed terminal/pointer span differs')
    typed=at(receipt['fields'],parent);require(typed['$type']=='RPG.GameCore.PlayTimeline' and typed['TimelineName']==source['timelineName'] and typed['Parameters']==[],'Whole caller exact consumer/value differs');terminal_check(body,source)
    result={'wholeCachedCallerEntries':1,'wholeCachedCallerBytes':971,'independentPlayTimelineTerminals':1,'wholeSourceBoundary':'Frozen full-EOF/schema receipt rebound to actual bytes; terminal independently decoded','currentNativeInputs':0,'callerEditionStatus':source['callerEditionStatus'],'runtimePlaybackStatus':'UNVERIFIED'}
    if installed_root:
        root=Path(installed_root)
        for name,path in [('GameAssembly.dll','GameAssembly.dll'),('global-metadata.dat','StarRail_Data/il2cpp_data/Metadata/global-metadata.dat')]:
            proof=data['nativeInputReceipts'][name];require((root/path).stat().st_size==proof['bytes'] and file_sha(root/path)==proof['sha256'],'Actual current DLL/metadata profile differs');result['currentNativeInputs']+=1
    if legacy_audit:
        require(installed_root,'Actual current CAB replay needs --installed-root')
        import verify_fresh_native_timeline as native
        require(file_sha(Path(native.__file__))==audit['nativePrimitivesSHA'],'Frozen independent native primitive source differs')
        olddir=Path(legacy_audit);raw=(olddir/'fate-screen-korean-delta.json').read_bytes();require(sha(raw)==audit['inputPins']['originalFateAudit'],'Original Lua consumer/CAB audit SHA differs');original=json.loads(raw)
        base,_,_,_=baseline(repo)
        for file,digest in base['evidence']['sourceGuards'].items():require(file_sha(olddir/file)==digest,'Original frozen Lua/native consumer guard differs')
        receipt=scene['proof']['receipt'];folder=olddir/'cab-replay'/receipt['cab'];canary=next(c for c in load(olddir/'fate-current-cab-canaries.json')['canaries'] if c['candidate']['cab']==receipt['cab'])
        raw=(folder/'inventory.json').read_bytes();require(sha(raw)==canary['inventorySha256'],'Actual Lua CAB inventory differs');inventory=json.loads(raw);cab,=inventory['cabs']
        require(inventory['sourceSha256']==receipt['blockSha256'] and cab['sha256']==receipt['cabSha256'],'Actual Lua CAB/source receipt differs')
        require(file_sha(Path(installed_root)/'StarRail_Data/StreamingAssets/Asb/Windows'/receipt['blockFile'])==receipt['blockSha256'],'Actual current installed Lua block differs')
        b,obj=native.raw_object(folder,receipt['cab'],cab,scene['proof']['root']);native_root=native.decode_root(b,obj);tracks={};modules=set()
        for row in scene['rows']:
            previous=next(r for r in original['readableDelta'] if r['route']['rootContainer']['key']==scene['source'] and r['captionSlot']==row['slot']);route=previous['route']
            require(row['argument']==previous['uiParamTokenProof'] and row['luaConsumer']==previous['luaConsumerProof'] and row['nativeConsumer']==previous['nativeConsumerProof'],'Existing exact four-slot argument/consumer differs')
            require(native_root['eof']==route['rootEOF'] and route['rootObject']==scene['proof']['root'] and route['rootContainer']==scene['proof']['container'],'Actual exact root EOF/container differs')
            for pathid in row['parentRoute'][:-1]:
                if pathid in tracks:continue
                obj=next(o for o in cab['objects'] if str(o['pathID'])==pathid);script=next(o for o in cab['objects'] if o['pathID']==obj['scriptPointer']['m_PathID']);kind=script['script']['m_ClassName'];proof=dict(obj,**{'class':kind})
                b,obj=native.raw_object(folder,receipt['cab'],cab,proof);tracks[pathid]=native.decode_track(b,obj,kind)
            for child,parentid in zip(row['parentRoute'],row['parentRoute'][1:]):
                require(tracks[child]['parent']=={'fileID':0,'pathID':parentid},'Actual track parent PPtr differs');siblings=native_root['tracks'] if parentid==row['parentRoute'][-1] else tracks[parentid]['children'];require({'fileID':0,'pathID':child} in siblings,'Actual reciprocal root/track PPtr differs')
            clip=tracks[row['track']['pathID']]['clips'][row['trackClipIndex']];require(clip==native.normalize_fields(route['timelineClip']) and clip['m_Asset']=={'fileID':0,'pathID':row['object']['pathID']},'Actual caption clip/track/timing differs')
            b,obj=native.raw_object(folder,receipt['cab'],cab,row['object']);reader=native.Native(b);reader.base(obj);require(reader.string()=='Ui.Fate.Performance.FateShowCaptionDialog' and reader.at==row['argument']['serializedField']['span'][0],'Actual typed caption UI field differs');require(reader.string()==row['argument']['raw'],'Actual UIParam differs');reader.eof()
            a,z=row['argument']['tokenByteSpanRelativeToObject'];require(b[a:z].decode('utf8')==str(row['talkId']),'Actual caption Talk token/slot differs')
            m=row['luaConsumer']['module']
            if m['entryHash'] not in modules:
                b=(Path(installed_root)/'StarRail_Data/StreamingAssets/Lua/Windows'/m['file']).read_bytes();require(sha(b[m['entryOffset']:m['entryOffset']+m['entryLength']])==m['entrySha256'],'Actual installed caption Lua module differs');modules.add(m['entryHash'])
        result.update(actualCurrentLuaBlocks=1,actualCABRootsEOF=1,actualTrackEOF=len(tracks),actualCaptionClipEOF=1,exactCaptionSlots=4,actualLuaEntries=len(modules))
    if archive:
        require(file_sha(archive)==old['archiveSha256'],'Actual owner archive SHA differs');needed={old['logicalJsonPath']}|{e[k] for e in old['ownerChain'] for k in ('source','tableSource') if k in e};docs={};digests={}
        with tarfile.open(archive,'r|gz') as tf:
            for member in tf:
                name=member.name.split('/',1)[-1]
                if name in needed:
                    require(member.isfile() and name not in docs,'Actual archive source duplicate/nonfile');raw=tf.extractfile(member).read();docs[name]=json.loads(raw);digests[name]=sha(raw)
        require(set(docs)==needed,'Actual caller/owner archive source missing');target=None
        for edge in old['ownerChain']:
            require(digests[edge['source']]==edge['sourceSha256'] and(target is None or target==edge['source']),'Owner chain source SHA/continuity differs');value=at(docs[edge['source']],edge['pointer'])
            if edge['kind']=='EXPLICIT_MAIN_MISSION_ID':require(value==edge['missionId'],'Explicit owner mission ID differs')
            elif edge['kind']=='EXPLICIT_JSON_PATH':require(value==edge['target'],'Explicit owner path differs');target=edge['target']
            elif edge['kind']=='EXPLICIT_PERFORMANCE_LOOKUP':
                table=docs[edge['tableSource']];require(digests[edge['tableSource']]==edge['tableSha256'] and value==edge['performanceId']==at(table,edge['idPointer']) and at(table,edge['pathPointer'])==edge['target'],'Exact typed owner performance lookup differs');task=at(docs[edge['source']],edge['pointer'].rsplit('/',1)[0]);require(task['$type']=='RPG.GameCore.TriggerPerformance' and task['PerformanceType']==edge['performanceType'],'Owner trigger domain differs');target=edge['target']
            else:raise AssertionError('Unsupported owner edge')
        require(target==source['logicalJsonPath'] and digests[target]==old['sourceSha256'] and at(docs[target],source['pointer'].rsplit('/',1)[0])==ref['snapshotTask'],'Exact archived caller context differs');result.update(actualArchiveSources=len(docs),ownerEdges=len(old['ownerChain']))
    return result


class HTML(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.stack=[];self.markers={};self.text=[];self.proof=[]
    def handle_starttag(self,tag,values):
        attrs=dict(values);marker=attrs.get('data-lua-native-corroboration')
        if marker is not None:
            require(marker not in self.markers and any(p for _,_,p in self.stack),'Duplicate/outside-disclosure Lua corroboration marker');self.markers[marker]=[]
        if tag not in('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.stack.append((tag,marker,tag=='details' and attrs.get('id')=='verified-sources'))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:del self.stack[i:];break
    def handle_data(self,value):
        self.text.append(value)
        for _,marker,proof in self.stack:
            if marker is not None:self.markers[marker].append(value)
            if proof:self.proof.append(value)


def rendered_check(data,text):
    parsed=HTML();parsed.feed(text);parsed.close();marker=SCENE+':0';require(set(parsed.markers)=={marker},'Exact one Lua corroboration marker absent')
    proof=''.join(parsed.proof);value=''.join(parsed.markers[marker]);require(CORRECTED in proof and STALE not in ''.join(parsed.text),'Sole affected Lua unsupported sentence remains stale')
    for token in(data['source']['logicalJsonPath'],data['source']['pointer'],data['source']['entrySha256'],'971','596–652'):require(token in value,'Rendered exact cached Lua caller proof absent: '+token)
    edition_unknown=('판본 일치는 미확인' in proof or '판본 일치 및 실제 재생 여부는 미확인' in proof)
    require(edition_unknown and '실제 재생 여부는 미확인' in proof,'Rendered cached edition/runtime boundary absent')
    return {'readers':1,'exactMarkers':1,'screenSlotsPreservedByBaseVerifier':4}


def dist_check(repo,data,directory,report=None):
    path=Path(directory)/'대화'/('연출-'+SCENE+'.html');text=path.read_text(encoding='utf8')
    if re.search(r'__spr\(|__starrailPublicationWrite\(',text):
        # Existing independent verifier codec, never a producer import.
        from verify_snapshot_native_corroboration import expand_proof_slots
        publication=load(report or Path(repo)/'.codex-work/publication-build-report.json')
        for shard in publication.get('proofShards',{}).values():
            from urllib.parse import unquote
            url=unquote(shard['url']);require(url.startswith('/starrail-quests/'),'Publication shard base differs');relative=url[len('/starrail-quests/'):];require(not any(p in('..','.')for p in relative.split('/')),'Publication shard path differs');require(file_sha(Path(directory)/relative)==shard['assetSha256'],'Actual publication shard SHA differs')
        text=expand_proof_slots(text,publication)
    return rendered_check(data,text)


def self_tests(repo,data):
    tests=[]
    def reject(name,fn):
        try:fn()
        except(AssertionError,KeyError,IndexError,ValueError,TypeError):tests.append(name);return
        raise AssertionError('Negative accepted: '+name)
    def mutate(name,edit):
        changed=deepcopy(data);edit(changed);reject(name,lambda:source_check(repo,changed))
    for name,edit in[
        ('wrong Lua scene',lambda d:d.__setitem__('sceneId','wrong')),
        ('public corpus index mixing',lambda d:d.__setitem__('snapshotSourceIndex','snapshot-5202c66ee1c44b2565a1')),
        ('wrong original caller path',lambda d:d['source'].__setitem__('logicalJsonPath','wrong.json')),
        ('wrong field pointer',lambda d:d['source'].__setitem__('pointer','/wrong/TimelineName')),
        ('wrong literal name',lambda d:d['source'].__setitem__('timelineName','wrong.playable')),
        ('wrong whole caller entry SHA',lambda d:d['source'].__setitem__('entrySha256','0'*64)),
        ('partial EOF promoted',lambda d:d['source'].__setitem__('consumedBytes',970)),
        ('wrong native root',lambda d:d['proof'].__setitem__('rootSha256','0'*64)),
        ('wrong owner chain',lambda d:d['proof'].__setitem__('ownerChainSha256','0'*64)),
        ('SCREEN_TEXT role promoted',lambda d:d['proof'].__setitem__('existingScreenRole','SPOKEN')),
        ('VoiceConfig consumer substituted',lambda d:d['source'].__setitem__('typedConsumer','RPG.GameCore.PlayVOSequence')),
        ('wrong terminal span',lambda d:d['source'].__setitem__('terminalSpan',[593,655])),
        ('runtime edition promotion',lambda d:d['source'].__setitem__('callerEditionStatus','CURRENT')),
        ('runtime playback promotion',lambda d:d['source'].__setitem__('runtimePlaybackStatus','PASS')),
        ('private path leaked',lambda d:d['source'].__setitem__('logicalJsonPath','D:/private/source')),
    ]:mutate(name,edit)
    from html import escape
    text='<details id="verified-sources"><div data-lua-native-corroboration="'+SCENE+':0">'+escape(' '.join([data['source']['logicalJsonPath'],data['source']['pointer'],data['source']['entrySha256'],'971','596–652']))+' '+CORRECTED+' 판본 일치는 미확인 실제 재생 여부는 미확인</div></details>'
    rendered_check(data,text)
    reject('rendered exact marker missing',lambda:rendered_check(data,text.replace('data-lua-native-corroboration','data-wrong')))
    reject('rendered native SHA missing',lambda:rendered_check(data,text.replace(data['source']['entrySha256'],'wrong')))
    reject('rendered stale unsupported label',lambda:rendered_check(data,text+STALE))
    reject('rendered runtime uncertainty removed',lambda:rendered_check(data,text.replace('실제 재생 여부는 미확인','')))
    reject('rendered installed edition promotion',lambda:rendered_check(data,text.replace('판본 일치는 미확인','판본 일치 확인')))
    return {'negativeCases':len(tests),'rejected':tests}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=SITE);p.add_argument('--data',type=Path);p.add_argument('--self-test',action='store_true');p.add_argument('--audit',type=Path);p.add_argument('--native-inputs',type=Path);p.add_argument('--legacy-audit',type=Path);p.add_argument('--installed-root',type=Path);p.add_argument('--archive',type=Path);p.add_argument('--dist',type=Path);p.add_argument('--publication-report',type=Path);p.add_argument('--report',type=Path)
    args=p.parse_args();repo=args.repo.resolve();raw=(args.data or repo/'data/lua-native-caller-corroboration.json').read_bytes();require(sha(raw)==OVERLAY and b'\r'not in raw,'Exact compact UTF8 LF Lua overlay changed');data=source_check(repo,json.loads(raw));checks={'source':{'scene':SCENE,'exactReferences':1,'captionSlots':4,'newBodies':0,'scope':'Exact old Lua/owner bridge/root/caption consumer and independent caller overlay pins','callerEditionStatus':data['source']['callerEditionStatus']}}
    require(not(args.installed_root or args.legacy_audit or args.archive)or args.audit,'External actual source replay requires --audit')
    if args.self_test:checks['selfTests']=self_tests(repo,data)
    if args.audit:checks['actual']=audit_check(repo,data,args.audit,args.native_inputs,args.legacy_audit,args.installed_root,args.archive)
    if args.dist:checks['dist']=dist_check(repo,data,args.dist,args.publication_report)
    result={'status':'PASS','verifierSha256':file_sha(Path(__file__)),'overlaySha256':sha(raw),'checks':checks}
    if args.report:args.report.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
