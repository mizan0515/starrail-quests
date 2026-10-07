"""Validate mission affiliation, exact metadata pointers and unchanged local text."""
import argparse, hashlib, json, re, tarfile
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text('utf8'))
def sha(b):return hashlib.sha256(b).hexdigest()
def main(archive=None):
    p=SITE/'data/mission-dialogue-supplements.json'; out=read(p)
    assert p.read_bytes()==(SITE/'public/mission-dialogue-supplements.json').read_bytes()
    evidence=out['evidence']; index=read(SITE/'data/dialogue-index.json')
    assert out['schema']=='starrail-mission-dialogue-supplements.v1'
    assert re.fullmatch(r'[a-f0-9]{64}',evidence['archiveSha256'])
    assert re.fullmatch(r'[a-f0-9]{40}',evidence['commit'])
    assert evidence['repository']=='DimbreathBot/TurnBasedGameData'
    assert evidence['dialogueIndexSha256']==sha((SITE/'data/dialogue-index.json').read_bytes())
    assert evidence['preservedLocalSources']==index['evidence']['sources']
    assert all(re.fullmatch(r'[a-f0-9]{64}',s['sha256']) and s['size']>0 for s in evidence['preservedLocalSources'])
    assert all(re.fullmatch(r'[a-f0-9]{64}',h) for h in evidence['structureFiles'].values())
    local={r['talk_id']:r for p in (SITE/'data/dialogues').glob('*.json') for r in read(p)['section']['rows']}
    local_pages={r['talk_id']:p.stem for p in (SITE/'data/dialogues').glob('*.json') for r in read(p)['section']['rows']}
    assert len(local)==240078
    scenes={s['source']:s for ss in out['missions'].values() for s in ss}
    verified=set(); unique=set(); row_count=0
    for mid,ss in out['missions'].items():
        doc=read(SITE/'data/documents'/(mid+'.json'))
        assert doc['id']==mid
        assert len({s['anchor'] for s in ss})==len(ss)
        for s in ss:
            match=re.match(r'(?:Story/(?:Discussion/)?Mission|Config/Level/Mission)/(\d+)(?:/|\.)',s['source'])
            assert match and mid=='quest-'+match[1]
            assert s['sourceSha256']==evidence['structureFiles'][s['source']]
            assert s['sourceUrl']==f"https://github.com/{evidence['repository']}/blob/{evidence['commit']}/{s['source']}"
            assert s['mapping']=='EXACT_PUBLIC_STRUCTURE_REFERENCE_TO_PRESERVED_LOCAL_TALK'
            old={r.get('talk_id') for sec in doc['sections'] if sec.get('source')==s['source'] for r in sec['rows']}
            assert not old.intersection(r['talk_id'] for r in s['rows'])
            assert len({r['talk_id'] for r in s['rows']})==len(s['rows'])
            for r in s['rows']:
                orig=local[r['talk_id']]
                for k,v in orig.items(): assert r[k]==v,(s['source'],r['talk_id'],k)
                assert r['anchor']=='talk-'+str(r['talk_id'])
                assert r['pageId']==local_pages[r['talk_id']]
                assert r['url']=='대사/'+r['pageId']+'.html#'+r['anchor']
                assert (SITE/'data/dialogues'/(r['pageId']+'.json')).exists()
                assert r['references']
                for ref in r['references']:
                    assert ref['pointer'].startswith('/')
                    assert ref['kind'] in ('TalkSentenceID','TalkSentenceIDList','TalkSentence event reference')
                unique.add(r['talk_id']); row_count+=1
    assert out['counts']['rows']==row_count
    assert out['counts']['missions']==len(out['missions'])
    assert out['counts']['scenes']==len(scenes)
    assert out['counts']['structureFiles']==len(evidence['structureFiles'])
    assert out['counts']['localKoreanRows']==len(local)
    assert out['counts']['missingStructurePaths']==len(out['missingExistingStructurePaths'])
    assert out['counts']['unresolvedReferences']==len(out['unresolvedReferences'])
    if archive:
      assert evidence['archiveSha256']==sha(archive.read_bytes())
      with tarfile.open(archive,'r:gz') as tf:
        for m in tf:
            name=m.name.split('/',1)[-1]
            if name not in scenes:continue
            raw=tf.extractfile(m).read(); obj=json.loads(raw); s=scenes[name]
            assert sha(raw)==s['sourceSha256']==out['evidence']['structureFiles'][name]
            for r in s['rows']:
                for ref in r['references']:
                    x=obj
                    for component in ref['pointer'].split('/')[1:]:
                        x=x[int(component)] if isinstance(x,list) else x[component]
                    assert x==r['talk_id'] or x=='TalkSentence_'+str(r['talk_id'])
            verified.add(name)
      assert set(scenes)==verified
    assert any(r['talk_id']==803130057 for s in out['missions']['quest-8031301'] for r in s['rows'])
    assert any(r['talk_id']==845000106 for s in out['missions']['quest-8041500'] for r in s['rows'])
    print(json.dumps({'status':'PASS','scope':'local-original-preservation-and-provenance-plus-archive-pointers' if archive else 'local-original-preservation-and-provenance','archivePointersVerified':bool(archive),'archiveScenesVerified':len(verified),'missions':len(out['missions']),'scenes':len(scenes),'supplementRows':row_count,'uniqueTalkIds':len(unique),'unchangedLocalKoreanRows':len(local),'requiredExamples':[803130057,845000106]}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);main(p.parse_args().archive)
