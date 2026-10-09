"""Check that the content reader preserves selected dialogue and source rows."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode=True
from verify_site import Page
from verify_mission_readers import explicitly_owned, passage
from verify_official_caption_site import canonical_scenes

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf8'))


def caption_owned(document,section):
    """Recognize the two exact caption seeds, including an aliased mission part.

    The MainMission seed must identify the same source/path/pointer as the first
    explicit JSON edge. Matching mission numbers or a nonempty arbitrary chain
    alone cannot promote a source into the primary reader.
    """
    owner=section.get('ownership',{});seed=owner.get('ownershipSeed',{})
    chain=owner.get('chain')
    if not isinstance(chain,list) or not chain:return False
    runtime=seed.get('kind')=='EXPLICIT_RUNTIME_OWNERMAINMISSIONID'
    first=chain[0]
    path=seed.get('missionJsonPath');pointer=seed.get('missionJsonPathPointer')
    main=(seed.get('kind')=='EXPLICIT_MAIN_MISSION_ID'
          and isinstance(path,str) and bool(path) and isinstance(pointer,str) and bool(pointer)
          and first.get('kind')=='EXPLICIT_JSON_PATH' and first.get('source')==seed.get('source')
          and first.get('pointer')==pointer and first.get('target')==path)
    return ((runtime or main) and
            'quest-'+str(owner.get('missionId')) in document.get('missionParts',[document['id']]) and
            str(seed.get('missionId'))==str(owner.get('missionId')))


def caption_scope_self_test():
    source=read(ROOT/'data/official-video-captions.json')
    owner,scenes=next((owner,scenes) for owner,scenes in source['missions'].items()
                     if scenes and scenes[0]['ownership']['ownershipSeed']['kind']=='EXPLICIT_MAIN_MISSION_ID')
    section=scenes[0];document={'id':owner}
    assert caption_owned(document,section),'Exact MainMission caption seed rejected'
    for field,value in [('kind','DIRECTORY_MATCH'),('missionJsonPath',''),
                        ('missionJsonPathPointer','/wrong'),('source','foreign.json'),('missionId',0)]:
        changed=json.loads(json.dumps(section));changed['ownership']['ownershipSeed'][field]=value
        assert not caption_owned(document,changed),('Unsafe caption seed accepted',field)
    for field,value in [('kind','EXPLICIT_PERFORMANCE_LOOKUP'),('target','foreign.json')]:
        changed=json.loads(json.dumps(section));changed['ownership']['chain'][0][field]=value
        assert not caption_owned(document,changed),('Unsafe first caption edge accepted',field)
    changed=json.loads(json.dumps(section));changed['ownership']['chain']=[]
    assert not caption_owned(document,changed),'Empty caption chain accepted'
    assert not caption_owned({'id':'quest-foreign'},section),'Foreign mission caption accepted'
    assert caption_owned({'id':'quest-parent','missionParts':[owner]},section),'Exact preserved alias part rejected'


def reading_counts(document,scenes,coverage,message_sections):
    """Partition original, dialogue, caption and message rows by explicit scope."""
    counts=Counter();primary_scenes=reference_scenes=reference_rows=0
    owners=coverage.get('sourceOwnership',{});scopes=coverage.get('sourceTalkScopes',{})
    for section in [*document['sections'],*scenes,*message_sections]:
        rows=section['rows']
        if not rows:continue
        if section.get('recordType')=='CUTSCENE_CAPTION':
            linked=caption_owned(document,section)
            scope=None
        else:
            chain=section.get('_messageOwnership',owners.get(section.get('source'),section.get('ownership',[])))
            linked=explicitly_owned(chain)
            if chain and chain[0].get('kind')=='EXPLICIT_NATIVE_MAIN_MISSION_ID':
                seed=chain[0]
                linked=section.get('recordType') in ('TIMELINE_DIALOGUE','NATIVE_TIMELINE_CHOICES') and seed.get('pointer')=='/OwnerMainMissionID' and seed.get('value')==seed.get('missionId')==seed.get('canonicalMissionId') and 'quest-'+str(seed['missionId']) in document.get('missionParts',[document['id']]) and len(section.get('nativeOwnership',{}).get('edges',[]))==5
            scope=scopes.get(section.get('source')) if '_messageOwnership' not in section else None
            if linked and any(edge.get('kind')=='EXPLICIT_SUBMISSION_FINISH_SCOPE' and edge.get('target')==section.get('source') for edge in chain):
                assert scope and isinstance(scope.get('talkIds'),list),(document['id'],'missing explicit talk scope',section['source'])
            if scope:assert isinstance(scope.get('talkIds'),list),(document['id'],'invalid explicit talk scope')
        selected=[row for row in rows if linked and (not scope or str(row.get('talk_id')) in {str(id) for id in scope['talkIds']})]
        counts.update(passage(row) for row in selected)
        primary_scenes+=bool(selected)
        remaining=len(rows)-len(selected)
        reference_rows+=remaining;reference_scenes+=bool(remaining)
    return {'dialogueCount':counts['dialogue'],'choiceCount':counts['choice'],'gapCount':counts['gap'],
            'captionCount':counts['caption'],'sceneCount':primary_scenes,'referenceRows':reference_rows,
            'referenceSceneCount':reference_scenes,
            'state':'dialogue-linked' if counts['dialogue'] else 'captions-linked' if counts['caption'] else 'choices-only' if counts['choice'] else 'overview-only'}

def main():
    caption_scope_self_test()
    catalogue=read(ROOT/'data/universe-catalog.json');count=0;originals=0
    for mode in catalogue['modes']:
        file=ROOT/'dist/우주'/(mode['id']+'.html');page=Page();page.feed(file.read_text('utf8'))
        assert not page.duplicates,(mode['id'],page.duplicates)
        for group in mode['dialogueGroups']:
            for i,row in enumerate(group['rows'],1):
                assert page.original[f"dialogue-text-{group['id']}-row-{i}"]==row['text'],row['talk_id']
                assert 'talk-'+str(row['talk_id']) in page.ids
                count+=1
        for ref in mode['documents']:
            d=read(ROOT/'data/documents'/(ref['id']+'.json'))
            for s in d['sections']:
                for i,row in enumerate(s['rows'],1):
                    assert page.original[f"{ref['id']}-{s['anchor']}-row-{i}"]==row['text']
                    originals+=1
    assert count==catalogue['counts']['reviewedDialogueRows']
    supplements=read(ROOT/'data/mission-dialogue-supplements.json');mission_rows=caption_rows=timeline_rows=message_rows_checked=0
    timelines=read(ROOT/'data/timeline-mission-dialogue.json')
    native_timelines=read(ROOT/'data/native-timeline-mission-dialogue.json')
    for owner,scenes in native_timelines['missions'].items():
        timelines['missions'].setdefault(owner,[]).extend(scenes)
    for field in ('scenes','rows'):
        timelines['counts'][field]+=native_timelines['counts'][field]
    caption_source=read(ROOT/'data/official-video-captions.json');aliases=read(ROOT/'data/aliases.json')
    native_captions=read(ROOT/'data/native-video-captions.json')
    for owner,scenes in native_captions['missions'].items():
        caption_source['missions'].setdefault(owner,[]).extend(scenes)
    for field in ('scenes','rows'):
        caption_source['counts'][field]+=native_captions['counts'][field]
    caption_source['counts']['missions']=len(caption_source['missions'])
    targets={aliases.get(owner,owner) for owner in caption_source['missions']}
    originals_by_id={target:read(ROOT/'data/documents'/(target+'.json')) for target in targets}
    captions=canonical_scenes(caption_source,aliases,originals_by_id)
    published_catalogue={d['id']:d for d in read(ROOT/'dist/reading-catalog.json')}
    versions=read(ROOT/'dist/versions-data.json')
    checked_missions=set(supplements['missions'])|set(captions)|set(timelines['missions'])
    for mid in sorted(checked_missions):
        dialogue_scenes=supplements['missions'].get(mid,[]);caption_scenes=captions.get(mid,[])
        timeline_scenes=timelines['missions'].get(mid,[])
        scenes=[*dialogue_scenes,*caption_scenes,*timeline_scenes]
        page=Page();page.feed((ROOT/'dist/문서'/(mid+'.html')).read_text('utf8'))
        assert not page.duplicates,(mid,page.duplicates)
        assert 'linked-dialogue' in page.ids,mid
        source=read(ROOT/'data/documents'/(mid+'.json'))
        rows=sum(len(s['rows']) for s in scenes)
        coverage=supplements['coverage'].get(mid,{})
        messages={}
        for ref in coverage.get('relatedDocuments',[]):
            previous=messages.get(ref['id'])
            if not previous or (not explicitly_owned(previous.get('ownership')) and explicitly_owned(ref.get('ownership'))):messages[ref['id']]=ref
        message_sections=[]
        for id,ref in messages.items():
            message=read(ROOT/'data/documents'/(id+'.json'))
            assert message['id']==id and message['category']=='메시지',(mid,id,'message identity changed')
            message_sections.extend({**s,'_messageOwnership':ref.get('ownership',[])} for s in message['sections'])
        message_rows=sum(len(s['rows']) for s in message_sections)
        assert source['count']==sum(len(s['rows']) for s in source['sections']),(mid,'original count changed')
        assert published_catalogue[mid]['count']==source['count']+rows+message_rows,mid
        assert published_catalogue[mid]['addedDialogue']==rows,(mid,'added source rows differ')
        assert published_catalogue[mid]['messageRows']==message_rows,(mid,'message rows differ')
        expected=reading_counts(source,scenes,coverage,message_sections)
        for field,value in expected.items():assert published_catalogue[mid][field]==value,(mid,field,value,published_catalogue[mid][field])
        assert expected['captionCount']==sum(len(s['rows']) for s in caption_scenes),(mid,'caption rows counted as dialogue or reference')
        assert sum(expected[field] for field in ('dialogueCount','choiceCount','gapCount','captionCount','referenceRows'))==source['count']+rows+message_rows,(mid,'original/dialogue/message partition differs')
        message_rows_checked+=message_rows
        assert versions[mid],mid
        for version in versions[mid]:
            assert (ROOT/'dist/versions'/(version+'.html')).exists(),(mid,version)
        for s in dialogue_scenes:
            for i,row in enumerate(s['rows'],1):
                assert page.original[f"{s['anchor']}-row-{i}"]==row['text'],(mid,row['talk_id'])
                mission_rows+=1
        for s in caption_scenes:
            for i,row in enumerate(s['rows'],1):
                assert page.original[f"{s['anchor']}-row-{i}"]==row['text'],(mid,row['hash'])
                caption_rows+=1
        for s in timeline_scenes:
            for i,row in enumerate(s['rows'],1):
                assert page.original[f"{s['anchor']}-row-{i}"]==row['text'],(mid,row['talk_id'])
                timeline_rows+=1
    assert mission_rows==supplements['counts']['rows']
    assert caption_rows==caption_source['counts']['rows']
    assert timeline_rows==timelines['counts']['rows']
    print(json.dumps({'status':'PASS','modePages':len(catalogue['modes']),'originalDialogueRows':count,'documentRows':originals,'missionsWithDialogue':len(supplements['missions']),'missionDialogueRowsPreserved':mission_rows,'missionPagesChecked':len(checked_missions),'captionSourceMissionIds':len(caption_source['missions']),'canonicalCaptionMissionPages':len(captions),'captionScenes':caption_source['counts']['scenes'],'captionRowsPreserved':caption_rows,'messageRowsChecked':message_rows_checked}))

if __name__=='__main__':main()
