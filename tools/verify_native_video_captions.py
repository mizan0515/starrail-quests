"""Verify the native playback addition and its compiled original Korean reader.

Frozen canary constants are independently observed raw-input identities. The
existing public-JSON caption cohort keeps its original validation contract.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from verify_official_caption_site import Dom, by_attr, one, timestamp, replace_inside
from verify_mission_readers import MissionPage
from verify_official_universe_texts import safe

ROOT=Path(__file__).resolve().parents[1]
SOURCE='Config/Level/Mission/1054417/Act/Act105441716.json'
CAPTION='Config/CutSceneCaption/CS_Chap05_Act450_Caption.json'
HASHES=['1763227277226850104','13627081222599137072','13960297433703089132','6460476967229725619']
TEXTS=['마지막으로——','아무리\u00a0국면이\u00a0혼란스러워도——','앞만\u00a0바라보며——','혼돈을\u00a0부숴버린다!']
TIMES=[(2.5,3.200000047683716),(3.9830000400543213,5.915999889373779),(6.400000095367432,8.149999618530273),(11.482999801635742,13.232999801635742)]
CAPTION_SPANS=[(2,25),(25,49),(49,73),(73,96)]
KOREAN_SPANS=[(57589829,57589866),(57665310,57665373),(57530797,57530840),(58039935,58039978)]
LEGACY=[630353577,1436922631,1695245250,888676196]
def check(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(path.read_text('utf8'))
def validate(data):
    safe(data)
    check(data['schema']=='starrail-native-video-captions.v1' and data['counts']=={'missions':1,'scenes':1,'rows':4},'Native caption cohort')
    evidence=data['evidence']
    check(evidence['clientVersion']=='OSPRODWin4.6.0' and evidence['metadataRepository']=='DimbreathBot/TurnBasedGameData' and evidence['metadataCommit']=='8b178dd48698e5e7b12f0cc319ddab149f2ffc5c','Native source version/repository')
    check(evidence['manifestSha256']=='cfcc82e9dd1bb0b86d18aaf94e72fd5273caa79f9b3981a789fa3aee61d2a284' and evidence['catalogSha256']=='ae92b3dd2417efbb9cd08e463891051ed515df2f97d40137223cec394a7e6132' and evidence['metadataArchiveSha256']=='e1eee10139b338e271467e1823cedb0ceba0c5c1c608771f2386639db308f02a','Native source manifest/catalog/archive hashes')
    check(evidence['officialBaseUrl']=='https://autopatchos.starrails.com/design_data/V4.6Live/output_16707949_49849fe93fe6_7e5dfd5e6cd1a8/client/Windows','Native official origin')
    check(set(data['missions'])=={'quest-1054419'} and len(data['missions']['quest-1054419'])==1,'Native caption mission membership')
    s=data['missions']['quest-1054419'][0];n=s['nativePlaybackSource'];o=s['ownership'];r=s['captionReference']
    check(o['missionId']==o['ownershipSeed']['missionId']==1054419,'Foreign native caption owner')
    check(o['ownershipSeed']['kind']=='EXPLICIT_RUNTIME_OWNERMAINMISSIONID' and o['ownershipSeed']['pointer']=='/OwnerMainMissionID','Native caption owner kind')
    check(o['ownershipSeed']['source']=='Config/LevelOutput/SharedRuntimeGroup/Groups_P40546_F40546001/LevelGroup_P40546_F40546001_G12.json','Native caption group identity')
    check(len(o['chain'])==2 and o['chain'][0]['kind']=='EXPLICIT_JSON_PATH' and o['chain'][0]['source']==o['ownershipSeed']['source'] and o['chain'][0]['pointer']=='/LevelGraph','Native graph source chain')
    edge=o['chain'][1]
    check(o['ownershipSeed']['sourceSha256']==o['chain'][0]['sourceSha256']=='9dcc5cc1c89bdb5d40e809b15d9089be0d486da1ddbb9bd71edfd4a947f6c309' and edge['sourceSha256']=='541f75ace76a2f320d46feee4357e3e8b869864e6da194a47ac02146c30688b1','Native owner source hashes')
    check(edge['source']==o['chain'][0]['target']=='Config/Level/GroupGraph/F40546001/Group_F40546001_G12.json','Native graph target identity')
    check(edge['kind']=='EXPLICIT_PERFORMANCE_LOOKUP' and edge['performanceType']=='PlayVideo' and edge['performanceId']==105441716 and edge['target']==SOURCE and edge['tableSource']=='ExcelOutput/PerformanceVideo.json' and edge['idPointer']=='/239/PerformanceID' and edge['pathPointer']=='/239/PerformancePath','Native typed performance identity')
    check(edge['tableSha256']=='bfd6e6b22698c0cba9c15b4748482a70e56abf64e0cdc692d4d37af189a08aaf' and edge['pointer']=='/OnStartSequece/0/TaskList/0/PerformanceID' and edge['lookupScope']=='PLAYVIDEO_EXACT_ID_VIDEO_TABLE_CROSS_TABLE_UNIQUE','Native performance lookup proof')
    check(n['nativePath']=='BakedConfig/'+SOURCE[:-5]+'.bytes' and n['nameHash']=='8810646640179724789' and n['entryOffset']==68091057 and n['entryLength']==n['consumedBytes']==39,'Native playback entry identity/EOF')
    check(n['entrySha256']==s['sourceSha256']=='de36f4e1a6cd54bb5cc5aa12be5a0dbbd6ec1020b8e5e3c432c64edaf012ec55','Native playback SHA')
    check(n['packFile']=='904d542abb3940ea5972a4ad151697a8.bytes' and n['packSha256']=='fa5fe2f887c83f370945981cc4e5c38a8e263be1ab5fa0dadbaf037c99a8dcb6','Native playback pack identity')
    check(s['source']==SOURCE and s['sourceUrl']==data['evidence']['officialBaseUrl'].rstrip('/')+'/'+n['packFile'] and s['conditions']==[],'Native playback source link/conditions')
    check(n['videoIdSpan']=={'start':26,'end':28} and n['identityStatus']=='EXACT_NATIVE_PATH_CATALOG_KEY_SCHEMA_EOF','Native VideoID field span')
    check(s['videoId']==n['videoId']==r['videoId']==5450 and r['target']==s['captionPath']==CAPTION and r['idPointer']=='/331/VideoID' and r['captionPathPointer']=='/331/CaptionPath','Native video/caption foreign key')
    check(r['source']==SOURCE and r['sourceSha256']==n['entrySha256'] and r['pointer']==n['videoTaskPointer']+'/VideoID','Native video field pointer')
    check(r['kind']=='EXACT_VIDEOID_CAPTIONPATH_FK' and r['tableSource']=='ExcelOutput/VideoConfig.json' and r['tableSha256']=='af37c10ac8d836e401d04d049ca9fed5d708e46266368b35d67159f77308eefa' and r['videoPathPointer']=='/331/VideoPath','Native video table proof')
    check(s['recordType']=='CUTSCENE_CAPTION' and s['speakerStatus']=='UNSPECIFIED_BY_CAPTIONLIST' and len(s['rows'])==4,'Native caption role')
    key=[1054419,SOURCE,n['videoTaskPointer'],CAPTION]
    check(s['anchor']=='video-caption-'+hashlib.sha256(json.dumps(key,separators=(',',':')).encode()).hexdigest()[:20],'Native caption anchor')
    for i,row in enumerate(s['rows']):
        cap,tm=row['officialCaptionSource'],row['officialTextMapSource']
        check(row['hash']==HASHES[i] and row['text']==row['raw']==TEXTS[i] and (row['startTime'],row['endTime'])==TIMES[i],'Native original Korean/hash/time')
        check(row['label']=='영상 자막' and cap['captionPath']==CAPTION and cap['rowIndex']==i and cap['entryKey']=='7326724291321385419' and cap['entryOffset']==38251331 and cap['entryLength']==96 and cap['entrySha256']=='1ca8c30b7b97b9b93793d2ecc2f7e491d25896618711acfad1e15c810cc3e3a8','Native caption source row')
        check(cap['absoluteOffset']==cap['entryOffset']+cap['rowOffset'] and cap['rowOffset']<cap['rowEnd']<=96,'Native caption source span')
        check(cap['packFile']==n['packFile'] and cap['packSha256']==n['packSha256'] and cap['identityStatus']==n['identityStatus'] and (cap['rowOffset'],cap['rowEnd'])==CAPTION_SPANS[i] and cap['legacy']==LEGACY[i],'Native caption exact source pack/span/legacy')
        check(tm['entryKey']=='15229857389724683600' and tm['packSha256']=='99dadf3786823c934ff12e970df594a77d413f8b090d2645f58cc8ad903fda20' and tm['entrySha256']=='a99fb2c4bb36d7e048d04b92d76805fb42a82bf39c69930fe4efaf66b107c3e9' and tm['absoluteOffset']==tm['entryOffset']+tm['rowOffset'] and tm['rowOffset']<tm['rowEnd']<=tm['entryLength'],'Native Korean source span/hash')
        check(tm['packFile']=='kr/e14f29d5d59324f4df2ee6a67a5755f7.bytes' and (tm['entryOffset'],tm['entryLength'])==(0,61356007) and (tm['rowOffset'],tm['rowEnd'])==KOREAN_SPANS[i] and tm['legacy']==LEGACY[i] and tm['hasParams']==0,'Native Korean exact pack/span/legacy/params')
    return s
def html_check(content,s):
    dom=Dom(content);mission=MissionPage();mission.feed(content)
    section=one(dom.root.elements(lambda x:x.tag=='section' and x.attrs.get('id')==s['anchor']),'Native caption section')
    placement=one([x for x in mission.sections if x['id']==s['anchor']],'Native caption placement')
    check(placement['insideReader'] and placement['isPrimary'] and not placement['isReference'],'Native caption outside primary reader')
    proof=one(by_attr(section,'data-native-caption-proof',s['anchor']),'Native caption disclosure')
    check(proof.tag=='details' and proof.attrs.get('data-reading-template')=='disclosure','Native caption disclosure semantics')
    actual=section.elements(lambda x:x.attrs.get('data-passage')=='caption')
    check(len(actual)==4,'Native caption HTML rows')
    for i,(node,row) in enumerate(zip(actual,s['rows'])):
        body=one(node.elements(lambda x:'original-body' in x.classes()),'Native caption body')
        check(body.text(False)==row['raw'],'Native caption visible original')
        time=one(node.elements(lambda x:'caption-time' in x.classes()),'Native caption time')
        check(time.text(False)==timestamp(row['startTime'])+'–'+timestamp(row['endTime']),'Native caption visible time')
        located=one(by_attr(proof,'data-native-caption-row-proof',str(i)),'Native caption row proof')
        check(row['hash'] in located.text() and row['raw'] in located.text(),'Native caption raw source proof')
    links={x.attrs.get('href') for x in proof.elements(lambda x:x.tag=='a')}
    check(s['sourceUrl'] in links and not any(SOURCE in x for x in links if x),'Native playback source link must use actual official pack')
    return dom,actual
def main(args):
    data=read(ROOT/'data/native-video-captions.json');s=validate(data);reject=0
    if args.self_test:
        cases=[lambda x:x['ownership'].update(missionId=1),lambda x:x['ownership']['chain'][1].update(performanceType='D'),lambda x:x['nativePlaybackSource'].update(entryLength=40),lambda x:x['nativePlaybackSource'].update(nameHash='1'),lambda x:x.update(sourceUrl='https://example.org/missing.json'),lambda x:x['rows'][0].update(raw='changed'),lambda x:x['rows'][0].update(hash='1'),lambda x:x['rows'][0].update(startTime=0),lambda x:x['captionReference'].update(videoId=1),lambda x:x['ownership']['ownershipSeed'].update(sourceSha256='0'*64),lambda x:x['captionReference'].update(tableSha256='0'*64),lambda x:x['rows'][0]['officialCaptionSource'].update(packFile='foreign.bytes'),lambda x:x['rows'][0]['officialCaptionSource'].update(rowOffset=1),lambda x:x['rows'][0]['officialTextMapSource'].update(rowOffset=1,absoluteOffset=1),lambda x:x['rows'][0]['officialTextMapSource'].update(hasParams=1)]
        for mutate in cases:
            changed=deepcopy(data);mutate(changed['missions']['quest-1054419'][0])
            try:validate(changed)
            except (ValueError,KeyError):reject+=1
            else:raise ValueError('Native caption artifact mutation accepted')
    if args.dist:
        content=(args.dist/'문서/quest-1054419.html').read_text('utf8');dom,actual=html_check(content,s)
        catalog=read(args.dist/'reading-catalog.json');item=next(x for x in catalog if x['id']=='quest-1054419')
        check(item['captionCount']==4 and item['state']=='captions-linked','Native caption catalogue state')
        check(sum(len(re.findall('data-native-caption-proof=',p.read_text('utf8'))) for p in (args.dist/'문서').glob('quest-*.html'))==1,'Native caption whole-site proof coverage')
        if args.self_test:
            body=one(actual[0].elements(lambda x:'original-body' in x.classes()),'Native original mutation body')
            try:html_check(replace_inside(content,body,'changed'),s)
            except (ValueError,AssertionError):reject+=1
            else:raise ValueError('Native caption visible text mutation accepted')
    print(json.dumps({'status':'PASS','missions':1,'scenes':1,'rows':4,'mutationRejections':reject,'htmlChecked':bool(args.dist)},ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dist',type=Path);p.add_argument('--self-test',action='store_true')
    main(p.parse_args())
