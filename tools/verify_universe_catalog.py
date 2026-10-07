"""Verify universe discovery projections against preserved source JSON and hashes."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    file=ROOT/'data/universe-catalog.json';x=read(file)
    assert file.read_bytes()==(ROOT/'public/universe-catalog.json').read_bytes()
    assert x['schema']=='starrail-universe-catalog.v1'
    assert x['evidence']['catalogueSha256']==sha(ROOT/'data/catalog.json')
    assert x['evidence']['dialogueIndexSha256']==sha(ROOT/'data/dialogue-index.json')
    docs={};pages={};all_rows={};core=set();items=set()
    def record(r):
        p=ROOT/'data/documents'/(r['id']+'.json');assert p.exists(),r['id']
        assert sha(p)==r['sha256'],r['id']
        d=docs.setdefault(r['id'],read(p));assert d['title']==r['title'] and d['url']==r['url']
        assert d['category']==r['category'] and d['count']==r['count']
        assert r['anchor'] in {s['anchor'] for s in d['sections']}
        return d
    for mode in x['modes']:
        intro=mode['introEvidence']
        if intro['id'].startswith('dialogue-'):
            page=read(ROOT/'data/dialogues'/(intro['id'][9:]+'.json'))
            assert any(row['hash']==intro['hash'] and row['text']==intro['quote'] and 'talk-'+str(row['talk_id'])==intro['anchor'] for row in page['section']['rows'])
        else:
            source=read(ROOT/'data/documents'/(intro['id']+'.json'))
            assert any(sec['anchor']==intro['anchor'] and any(row['hash']==intro['hash'] and row['text']==intro['quote'] for row in sec['rows']) for sec in source['sections'])
        for r in mode['documents']:record(r);core.add(r['id'])
        for r in mode['relatedRecords']:
            d=record(r);assert r['status']=='원문 검색 결과'
            for h in r['matches']:
                assert any(s['anchor']==h['anchor'] and any(row.get('hash','')==h['hash'] and h['quote'] in row['text'] for row in s['rows']) for s in d['sections'])
        for group in mode['dialogueGroups']:
            assert group['role']=='검토한 대사 원문' and group['count']==len(group['rows'])
            for row in group['rows']:
                page=pages.setdefault(row['pageId'],read(ROOT/'data/dialogues'/(row['pageId']+'.json')))
                source=next(r for r in page['section']['rows'] if r['talk_id']==row['talk_id'])
                assert all(row[k]==v for k,v in source.items()),row['talk_id']
                assert row['anchor']=='talk-'+str(row['talk_id'])
                assert row['url']=='대사/'+row['pageId']+'.html#'+row['anchor']
                all_rows[row['talk_id']]=row
    for collection in x['itemCollections']:
        assert collection['count']==len(collection['documents'])
        for r in collection['documents']:
            d=record(r);items.add(r['id'])
            assert r['searchText']=='\n'.join([d['title']]+[row['text'] for s in d['sections'] for row in s['rows']])
    assert x['counts']=={'modes':len(x['modes']),'coreDocuments':len(core),'reviewedDialogueRows':len(all_rows),'itemRecords':len(items)}
    # Preserved archive manifests provide a second source-identity boundary.
    manifested={f['path']:f for manifest in ['dataset/manifest.json','dataset-extra/manifest.json'] for f in read(ROOT/manifest)['files']}
    for pid in pages:
        rel='data/dialogues/'+pid+'.json'; assert manifested[rel]['sha256']==sha(ROOT/rel)
    print(json.dumps({'status':'PASS',**x['counts'],'sourceDialoguePages':len(pages),'sourceDocumentFiles':len(docs)},ensure_ascii=False))
if __name__=='__main__':main()
