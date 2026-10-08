"""Check reviewed relation direction and exact original citations.

Natural-language review is recorded separately; this gate preserves its
explicit decisions and verifies the generated endpoints against those inputs.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
INCOMING = {('swarm-research', 1): ('ruan-mei', '완•매'),
            ('swarm-research', 2): ('person-1013', '아마도라고 정정해야겠어'),
            ('unknowable-research', 1): ('person-1013', '제왕의 외장 사고 유닛을 재현')}


def require(value, label):
    if not value:
        raise ValueError(label)


def read(path):
    return json.loads(path.read_text('utf8'))


def verify(site=SITE, atlas=None, graph=None, sources_only=False):
    atlas = atlas or read(site / 'editorial/context-atlas.json')
    manifests = {}
    for name in ('dataset/manifest.json', 'dataset-extra/manifest.json'):
        for item in read(site / name)['files']:
            key = item['path']
            require(key not in manifests or manifests[key] == item['sha256'], 'Conflicting preserved source SHA')
            manifests[key] = item['sha256']
    docs, cited_rows = {}, []

    def evidence(e):
        ident = e.get('id', e.get('docId'))
        if ident not in docs:
            path = site / 'data/documents' / (ident + '.json')
            relative = path.relative_to(site).as_posix()
            require(relative in manifests and hashlib.sha256(path.read_bytes()).hexdigest() == manifests[relative],
                    'Original source SHA differs: ' + ident)
            docs[ident] = read(path)
        matches = [r for s in docs[ident]['sections'] if s['anchor'] == e['anchor'] for r in s['rows']
                   if ('hash' not in e or str(r.get('hash')) == str(e['hash']))
                   and (e.get('talkId') is None or r.get('talk_id') == e['talkId'])
                   and e['quote'] in r.get('text', '')]
        require(len(matches) == 1, 'Original quote/anchor/hash/TalkID differs: ' + ident)
        cited_rows.append((ident, e, matches[0]))
        return matches[0]

    if not sources_only:
        graph = graph or read(site / 'public/reading-data/graph.json')
        relations = {r['id']: r for r in graph['relations']}
        require(len(relations) == len(graph['relations']), 'Duplicate relation ID')
        claims = {c['id']: c for c in graph['claims']}
        proof = {e['id']: e for e in graph['evidence']}
    all_ids, count, topology_edges, events, comparisons = set(), 0, 0, 0, 0
    incoming = set()
    for node in atlas['nodes']:
        require(node['id'] not in all_ids, 'Duplicate context entity')
        all_ids.add(node['id'])
        for e in node['evidence']:
            evidence(e)
        for index, relation in enumerate(node['links']):
            key = (node['id'], index)
            direction = relation.get('direction')
            require(direction in ('incoming', 'outgoing'), 'Explicit reviewed direction required')
            require((direction == 'incoming') == (key in INCOMING), 'Relation direction differs from semantic review: ' + str(key))
            require(relation['target'] != node['id'] and relation['verb'].strip(), 'Invalid relation endpoints/predicate')
            original = evidence(relation['evidence'])
            if key == ('sanctus-medicus', 1):
                require(relation['target'] == 'lore-10054' and relation['status'] == '편집자의 연결' and
                        relation['verb'] == '풍요의 백성의 정의와 함께 읽는다', 'Related definition promoted to inferred membership')
            if key in INCOMING:
                target, original_needle = INCOMING[key]
                require(relation['target'] == target and original.get('speaker') == '헤르타' and
                        original_needle in original['text'], 'Incoming actor proof differs')
                incoming.add(key)
            if not sources_only:
                ident = 'atlas/' + node['id'] + '/relation-' + str(index)
                require(ident in relations, 'Missing generated relation')
                r = relations[ident]
                left, right = (relation['target'], node['id']) if direction == 'incoming' else (node['id'], relation['target'])
                require((r['from'], r['to'], r['label']) == (left, right, relation['verb']), 'Generated actor/predicate/target differs: ' + ident)
                claim = claims[r['reasonClaimId']]
                require(claim['text'] == relation['why'], 'Relation reason changed')
                expected_kind = 'inference' if '편집' in relation.get('status', '') else ('attributed' if
                    relation['evidence'].get('status') != '원문 서술' else 'explicit')
                require(claim['kind'] == expected_kind, 'Relation fact/claim/interpretation differs')
                evs = [proof[e] for e in claim['evidenceIds']]
                require(len(evs) == 1 and evs[0]['sourceId'] == relation['evidence']['id'] and
                        evs[0]['quote'] == relation['evidence']['quote'] and
                        evs[0]['sourceSha256'] == hashlib.sha256(original['text'].encode()).hexdigest(), 'Relation cited original differs')
            count += 1
        for event in node.get('timeline', []):
            evidence(event['evidence'])
            events += 1
        for edge in (node.get('topology') or {}).get('edges', []):
            for e in edge['evidence']:
                evidence(e)
            topology_edges += 1
    require(incoming == set(INCOMING), 'Reviewed incoming relation missing')
    if not sources_only:
        require(count == len(graph['relations']), 'Unreviewed generated relation')
    for comparison in atlas['comparisons'].values():
        for panel in comparison['panels']:
            evidence(panel['evidence'])
            comparisons += 1
    universe = read(site / 'data/universe-reading-clusters.json')
    panels = 0
    for cluster in universe['clusters']:
        for panel in cluster['panels']:
            for e in panel['evidence']:
                evidence(e)
            panels += 1
    return {'nodes': len(all_ids), 'relations': count, 'incomingRelations': len(incoming),
            'topologyEdges': topology_edges, 'timelineEvents': events, 'comparisonPanels': comparisons,
            'universeClusters': len(universe['clusters']), 'universePanels': panels,
            'originalReferences': len(cited_rows), 'originalDocuments': len(docs), 'generatedGraphChecked': not sources_only}


def self_test(site, sources_only):
    atlas = read(site / 'editorial/context-atlas.json')
    rejected = []
    for label, mutate in [
        ('INCOMING_REVERSED', lambda a: next(n for n in a['nodes'] if n['id'] == 'swarm-research')['links'][1].update(direction='outgoing')),
        ('OUTGOING_REVERSED', lambda a: a['nodes'][0]['links'][0].update(direction='incoming')),
        ('UNKNOWN_DIRECTION', lambda a: a['nodes'][0]['links'][0].update(direction='sideways')),
        ('WRONG_CITED_HASH', lambda a: a['nodes'][0]['links'][0]['evidence'].update(hash='1')),
        ('WRONG_QUOTE', lambda a: a['nodes'][0]['links'][0]['evidence'].update(quote='invented quotation')),
        ('WRONG_ACTOR', lambda a: next(n for n in a['nodes'] if n['id'] == 'swarm-research')['links'][1].update(target='bronya')),
        ('RELATED_DEFINITION_AS_MEMBERSHIP', lambda a: next(n for n in a['nodes'] if n['id'] == 'sanctus-medicus')['links'][1].update(status='원문 서술', verb='풍요의 축복을 받은 사람들'))]:
        edited = deepcopy(atlas)
        mutate(edited)
        try:
            verify(site, atlas=edited, sources_only=sources_only)
        except (ValueError, KeyError):
            rejected.append(label)
        else:
            raise ValueError('Accepted contaminated relation: ' + label)
    if not sources_only:
        graph = read(site / 'public/reading-data/graph.json')
        edited = deepcopy(graph)
        target = next(r for r in edited['relations'] if r['id'] == 'atlas/swarm-research/relation-1')
        target['from'], target['to'] = target['to'], target['from']
        try:
            verify(site, graph=edited)
        except ValueError:
            rejected.append('GENERATED_ACTOR_REVERSED')
        else:
            raise ValueError('Accepted reversed generated actor')
    return rejected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=SITE)
    parser.add_argument('--sources-only', action='store_true', help='Do not check stale generated graph before regeneration')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    result = verify(args.site, sources_only=args.sources_only)
    result['mutationRejections'] = self_test(args.site, args.sources_only) if args.self_test else []
    print(json.dumps({'status': 'PASS', **result}, ensure_ascii=False))
