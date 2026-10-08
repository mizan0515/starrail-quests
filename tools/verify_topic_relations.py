"""Preserve the reviewed actor/predicate/object meaning of all legacy topics.

The review digest is a regression snapshot of human-readable editorial decisions,
not an automatic semantic judgment. Original citations are checked independently
against preserved source manifests and exact Korean rows.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
REVIEW_SHA = '2cd9d8bfb73192932011c5ec358f4d9fbbc7f8c0762cedce79ca947c6952151b'
COHORT = {'paths-and-factions': 3, 'xianzhou-immortality': 4,
          'borisin-and-foxians': 3, 'belobog-preservation': 3,
          'penacony-memory': 4, 'amphoreus-myth-and-life': 4,
          'herta-life-and-knowledge': 2}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text('utf8'))


def reviewed_projection(topics):
    return [(t['id'], t['relations'], [
        {k: e[k] for k in ('statementType', 'relationKind', 'speaker', 'reason')}
        | {'sources': [v['id'] for v in e['evidence']]}
        for e in t['relationEvidence']]) for t in topics]


def verify(topics=None, site=SITE, generated=False):
    topics = read(site / 'editorial/topics.json') if topics is None else topics
    require(len(topics) == len(COHORT) and {t['id'] for t in topics} == set(COHORT),
            'Reviewed topic cohort differs')
    manifests, docs = {}, {}
    for name in ('dataset/manifest.json', 'dataset-extra/manifest.json'):
        for item in read(site / name)['files']:
            key = item['path']
            require(key not in manifests or manifests[key] == item['sha256'],
                    'Conflicting original source manifest')
            manifests[key] = item['sha256']

    def doc(ident):
        require(isinstance(ident, str) and '/' not in ident and '\\' not in ident,
                'Invalid original identity')
        if ident not in docs:
            path = site / 'data/documents' / (ident + '.json')
            key = path.relative_to(site).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            require(manifests.get(key) == digest, 'Preserved original SHA differs: ' + ident)
            docs[ident] = (read(path), digest)
        return docs[ident]

    relations, quotes, section_needles, reading_links = 0, 0, 0, 0
    for t in topics:
        require(len(t['relations']) == COHORT[t['id']] and
                len(t['relationEvidence']) == len(t['relations']), 'Missing relation review')
        for relation, proof in zip(t['relations'], t['relationEvidence']):
            require(len(relation) == 4 and all(isinstance(v, str) and v.strip() for v in relation),
                    'Invalid actor/predicate/object/source tuple')
            require(relation[0] != relation[2], 'Identical relation endpoints')
            require(proof['statementType'] in ('explicit', 'attributed', 'inference'),
                    'Unknown statement scope')
            require(proof['relationKind'] in ('source', 'reading') and proof['reason'].strip(),
                    'Missing relation criterion')
            if proof['statementType'] == 'attributed':
                require(proof['speaker'].strip(), 'Missing claim author')
            if proof['relationKind'] == 'reading':
                require(proof['statementType'] == 'inference' and '읽는다' in relation[1],
                        'Editorial reading connection promoted to an action')
                reading_links += 1
            require(proof['evidence'] and relation[3] in {e['id'] for e in proof['evidence']},
                    'Primary cited document lacks relation evidence')
            for e in proof['evidence']:
                d, digest = doc(e['id'])
                require(e['sourceSha256'] == digest and e['title'] == d['title'],
                        'Original document identity differs')
                require(isinstance(e['quote'], str) and e['quote'].strip(), 'Empty original quote')
                matches = [r for s in d['sections'] if s['anchor'] == e['anchor']
                           for r in s['rows'] if str(r.get('hash')) == str(e['hash'])
                           and e['quote'] in r.get('text', '')]
                require(len(matches) == 1, 'Exact original anchor/hash/quote differs: ' + e['id'])
                quotes += 1
            relations += 1
        for s in t['sections']:
            for e in s['evidence']:
                d, _ = doc(e['id'])
                require(e['needle'] and any(e['needle'] in r.get('text', '')
                        for section in d['sections'] for r in section['rows']),
                        'Section evidence missing from original')
                section_needles += 1
        for e in t['reading']:
            doc(e['id'])
    projection = json.dumps(reviewed_projection(topics), ensure_ascii=False, separators=(',', ':'))
    require(hashlib.sha256(projection.encode()).hexdigest() == REVIEW_SHA,
            'Reviewed actor/direction/predicate/attribution changed; reread originals before updating review')
    if generated:
        exported = read(site / 'data/topics.json')
        require([(t['id'], t['relations'], t.get('relationEvidence')) for t in exported] ==
                [(t['id'], t['relations'], t['relationEvidence']) for t in topics],
                'Generated topics lost reviewed relation semantics or evidence')
    return dict(topics=len(topics), relations=relations, exactQuotes=quotes,
                originalDocuments=len(docs), sectionNeedles=section_needles,
                editorialReadingRelations=reading_links, generatedChecked=generated)


def self_test(site=SITE):
    original = read(site / 'editorial/topics.json')
    mutations = [
        ('foreign target', lambda t: t[0]['relations'][1].__setitem__(2, '은하열차')),
        ('reverse direction', lambda t: t[0]['relations'][2].__setitem__(slice(0, 3, 2),
            [t[0]['relations'][2][2], t[0]['relations'][2][0]])),
        ('wrong quote', lambda t: t[0]['relationEvidence'][0]['evidence'][0].__setitem__('quote', '변형된 원문')),
        ('wrong hash', lambda t: t[0]['relationEvidence'][0]['evidence'][0].__setitem__('hash', '0')),
        ('wrong source SHA', lambda t: t[0]['relationEvidence'][0]['evidence'][0].__setitem__('sourceSha256', '0' * 64)),
        ('missing relation', lambda t: t[1]['relations'].pop()),
        ('lost author', lambda t: t[6]['relationEvidence'][1].__setitem__('speaker', '')),
        ('reading made factual', lambda t: t[3]['relationEvidence'][0].__setitem__('statementType', 'explicit')),
        ('unsupported causality', lambda t: t[3]['relations'][0].__setitem__(1, '도시 건설을 일으켰다')),
        ('false membership', lambda t: t[0]['relations'][2].__setitem__(1, '소속된다')),
        ('missing secondary party', lambda t: t[5]['relationEvidence'][3]['evidence'].pop()),
        ('wrong section needle', lambda t: t[0]['sections'][0]['evidence'][0].__setitem__('needle', '본문에 없는 구절')),
    ]
    rejected = []
    for label, mutate in mutations:
        changed = deepcopy(original)
        mutate(changed)
        try:
            verify(changed, site)
        except (ValueError, KeyError):
            rejected.append(label)
        else:
            raise ValueError('Mutation accepted: ' + label)
    return rejected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generated', action='store_true', help='Also check prepared data/topics.json')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    result = verify(generated=args.generated)
    if args.self_test:
        result['rejectedMutations'] = self_test()
    print(json.dumps(result, ensure_ascii=False, indent=2))
