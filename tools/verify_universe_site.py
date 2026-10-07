"""Check that the content reader preserves selected dialogue and source rows."""
import json
from pathlib import Path
from verify_site import Page

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf8'))

def main():
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
    supplements=read(ROOT/'data/mission-dialogue-supplements.json');mission_rows=0
    published_catalogue={d['id']:d for d in read(ROOT/'dist/reading-catalog.json')}
    versions=read(ROOT/'dist/versions-data.json')
    for mid,scenes in supplements['missions'].items():
        page=Page();page.feed((ROOT/'dist/문서'/(mid+'.html')).read_text('utf8'))
        assert not page.duplicates,(mid,page.duplicates)
        assert 'linked-dialogue' in page.ids,mid
        source=read(ROOT/'data/documents'/(mid+'.json'))
        rows=sum(len(s['rows']) for s in scenes)
        assert published_catalogue[mid]['count']==source['count']+rows,mid
        assert versions[mid],mid
        for version in versions[mid]:
            assert (ROOT/'dist/versions'/(version+'.html')).exists(),(mid,version)
        for s in scenes:
            for i,row in enumerate(s['rows'],1):
                assert page.original[f"{s['anchor']}-row-{i}"]==row['text'],(mid,row['talk_id'])
                mission_rows+=1
    assert mission_rows==supplements['counts']['rows']
    print(json.dumps({'status':'PASS','modePages':len(catalogue['modes']),'originalDialogueRows':count,'documentRows':originals,'missionsWithDialogue':len(supplements['missions']),'missionDialogueRowsPreserved':mission_rows}))

if __name__=='__main__':main()
