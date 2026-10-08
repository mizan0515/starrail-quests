"""Compare every newly available official Talk original with compiled HTML."""
import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote
from verify_official_caption_site import Dom, Node, one, by_attr, direct_pairs
from verify_official_mission_site import expected_fields
from verify_mission_readers import ReadingTemplatePage

SITE = Path(__file__).resolve().parents[1]
BASE = '/starrail-quests'

def require(value, message):
    if not value:
        raise AssertionError(message)

def original(node, anchor):
    body = one(by_attr(node, 'id', anchor), 'exact original anchor')
    require(body.tag == 'p' and 'original-body' in body.classes(), 'original paragraph template differs')
    return body.text(False)

def check(content, row, evidence):
    dom = Dom(content)
    template = ReadingTemplatePage(); template.feed(content)
    require(not template.finish(), 'shared reading/disclosure template differs')
    section = one(by_attr(dom.root, 'data-official-talk-library', row['talk_id']), 'official original section')
    require(section.attrs.get('id') == 'original' and section.attrs.get('data-reading-template') == 'reader' and section.attrs.get('data-reading-variant') == 'scene', 'source reading section differs')
    source_row = one(section.elements(lambda n: 'original-row' in n.classes()), 'source row')
    require(source_row.attrs.get('data-passage') == 'original' and source_row.attrs.get('data-speaker') == row['speaker'], 'source classification or speaker differs')
    require(source_row.attrs.get('data-reading-template') == 'row', 'source row template missing')
    require(original(source_row, 'talk-'+str(row['talk_id'])) == row['text'], 'exact official original text differs')
    require(one(source_row.elements(lambda n: 'rw-source-speaker' in n.classes()), 'speaker').text() == row['speaker'], 'visible original speaker differs')
    proof = one(by_attr(source_row, 'data-official-talk-proof', row['talk_id']), 'official source proof')
    require(proof.tag == 'details' and proof.attrs.get('data-reading-template') == 'disclosure' and 'data-pagefind-ignore' in proof.attrs, 'proof disclosure template or search exclusion differs')
    require(one(proof.immediate('summary'), 'source summary').text() == '공식 한국어 원문 · '+row['officialSource']['clientVersion'].removeprefix('OSPRODWin'), 'official version differs')
    require(direct_pairs(one(proof.immediate('dl'), 'source fields')) == expected_fields(row, evidence), 'official byte position/hash/raw proof differs')
    old = row.get('previous')
    if old:
        baseline = one(by_attr(dom.root, 'data-talk-baseline'), 'preserved baseline')
        current = one(by_attr(dom.root, 'data-talk-current'), 'current counterpart')
        require(original(baseline, 'talk-'+str(row['talk_id'])+'-baseline') == old['text'], 'preserved original differs')
        require(original(current, 'talk-'+str(row['talk_id'])+'-current') == row['text'], 'current comparison original differs')
        require(one(baseline.elements(lambda n: 'speaker' in n.classes()), 'baseline speaker').text() == old['speaker'], 'baseline speaker differs')
        require(one(current.elements(lambda n: 'speaker' in n.classes()), 'current speaker').text() == row['speaker'], 'current speaker differs')
        expected_url = BASE+'/'+old['url']
        require(any(n.attrs.get('href') == expected_url for n in baseline.elements(lambda n:n.tag=='a')), 'preserved source link differs')
    else:
        require(not by_attr(dom.root, 'data-talk-baseline') and not by_attr(dom.root, 'data-talk-current'), 'invented baseline comparison')
    assignments = row.get('missionLinks', [])
    proofs = by_attr(dom.root, 'data-talk-mission-proof')
    require(Counter(n.attrs['data-talk-mission-proof'] for n in proofs) == Counter(a['missionId'] for a in assignments), 'exact mission assignment coverage differs')
    for proof, assignment in zip(proofs, assignments):
        chain = one(proof.immediate('ol'), 'mission owner chain').immediate('li')
        require(len(chain) == len(assignment['ownership']), 'mission owner chain length differs')
        for node, edge in zip(chain, assignment['ownership']):
            require(edge['source'] in node.text() and (not edge.get('pointer') or edge['pointer'] in node.text()), 'mission source path/pointer missing')
            require(any(n.attrs.get('href') == f"https://github.com/{evidence['metadataRepository']}/blob/{evidence['metadataCommit']}/{edge['source']}" for n in node.elements(lambda n:n.tag=='a')), 'mission source URL differs')
        require(assignment['referencePointer'] in proof.text(), 'Talk reference pointer missing')
        if assignment.get('conditions'):
            conditions = one(proof.elements(lambda n:n.tag=='pre'), 'exact source conditions')
            require(json.loads(conditions.text()) == assignment['conditions'], 'mission conditions differ')
    require(bool(by_attr(dom.root, 'data-talk-unassigned')) == (not assignments), 'mission attribution status differs')
    return dom

def main(dist):
    library=json.loads((SITE/'data/official-talk-library.json').read_text('utf8'))
    rows=library['rows']; evidence=library['evidence']
    require(len(rows)==3922 and len({r['talk_id'] for r in rows})==len(rows), 'whole Talk delta cohort differs')
    files=set((dist/'대사').glob('official-4.6-*.html'))
    require(files == {dist/'대사'/f"official-4.6-{r['talk_id']}.html" for r in rows}, 'whole original page coverage differs')
    index=Dom((dist/'대사/official-4.6.html').read_text('utf8'))
    entries=by_attr(index.root,'data-source-record')
    require(len(entries)==len(rows), 'whole source index count differs')
    mapped={n.attrs['data-source-record']:n for n in entries}
    mutation_rejections=0; tested=set()
    for i,row in enumerate(rows):
        identity='official-4.6-'+str(row['talk_id'])
        entry=mapped.get(identity)
        require(entry is not None and entry.attrs.get('href')==BASE+'/대사/'+identity+'.html', 'individual original link missing')
        require(entry.attrs.get('data-source-kind-value')==row['changeKind'] and entry.attrs.get('data-search')==row['text'], 'index change kind/search original differs')
        require(('hidden' in entry.attrs)==(i>=12), 'initial source index subset differs')
        path=dist/'대사'/(identity+'.html');content=path.read_text('utf8')
        dom=check(content,row,evidence)
        family=(row['changeKind'],bool(row.get('missionLinks')),bool(row.get('previous') and row['previous']['speaker']!=row['speaker']))
        if family in tested: continue
        tested.add(family)
        for old,new in [
            (f'data-official-talk-library="{row["talk_id"]}"','data-removed-original="missing"'),
            (f'data-official-talk-proof="{row["talk_id"]}"','data-removed-proof="missing"'),
            ('공식 한국어 원문 · 4.6.0','공식 한국어 원문 · 4.5.0'),
            (evidence['koreanPack']['sha256'],'0'*64),
            (row['hash'],'1'),
            ('data-talk-baseline','data-removed-baseline') if row.get('previous') else ('data-talk-unassigned','data-removed-attribution') if not row.get('missionLinks') else ('data-talk-mission-proof','data-removed-assignment')
        ]:
            require(old in content, 'mutation source absent')
            try:check(content.replace(old,new),row,evidence)
            except AssertionError:mutation_rejections+=1
            else:raise AssertionError('accepted source HTML mutation: '+old)
    require('대사/official-4.6.html' in (dist/'대사.html').read_text('utf8'), 'original library entry absent')
    print(json.dumps({'status':'PASS','originalPages':len(rows),'indexLinks':len(entries),'comparisonPages':sum(bool(r.get('previous')) for r in rows),'missionAssignedRows':sum(bool(r.get('missionLinks')) for r in rows),'htmlMutationRejections':mutation_rejections},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dist',type=Path,default=SITE/'dist');main(p.parse_args().dist)
