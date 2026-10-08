"""Verify reading-cluster citations against preserved documents and manifests.

Read-only, standard-library CLI. It checks source identity and attribution
metadata; it does not judge the editor's prose or derive facts from wording.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUPERT_RECORDS = {
    'miracle-64': ('RogueMiracleDisplay:64.MiracleBGDesc', '2500265928394483654'),
    'miracle-123': ('RogueMiracleDisplay:123.MiracleBGDesc', '7449709905334827150'),
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(site=ROOT, data_file=None):
    site = Path(site).resolve()
    data_file = Path(data_file).resolve() if data_file else site / 'data/universe-reading-clusters.json'
    data_hash = digest(data_file)
    catalogue = read(site / 'data/universe-catalog.json')
    modes = {m['id'] for m in catalogue['modes']}
    manifested = {}
    for name in ('dataset/manifest.json', 'dataset-extra/manifest.json'):
        for row in read(site / name)['files']:
            previous = manifested.get(row['path'])
            require(previous is None or previous['sha256'] == row['sha256'],
                    'Conflicting preserved manifests: ' + row['path'])
            manifested[row['path']] = row

    documents = {}
    source_hashes = {}

    def document(doc_id):
        require(isinstance(doc_id, str) and re.fullmatch(r'[A-Za-z0-9_-]+', doc_id),
                'Invalid document ID')
        if doc_id not in documents:
            rel = 'data/documents/' + doc_id + '.json'
            path = site / rel
            require(path.is_file(), 'Missing original document: ' + doc_id)
            source_hashes[rel] = digest(path)
            require(rel in manifested, 'Original missing from preserved manifests: ' + doc_id)
            require(manifested[rel]['sha256'] == source_hashes[rel],
                    'Preserved original SHA mismatch: ' + doc_id)
            original = read(path)
            require(original['id'] == doc_id, 'Original ID mismatch: ' + doc_id)
            documents[doc_id] = original
        return documents[doc_id]

    data = read(data_file)
    require(data.get('schemaVersion') == 1, 'Unsupported cluster schema')
    clusters = data.get('clusters')
    require(isinstance(clusters, list) and clusters, 'No reading clusters')
    ids = set()
    panels = citations = related_count = 0
    cited_rupert = set()
    for cluster in clusters:
        cid = cluster['id']
        require(cid not in ids, 'Duplicate cluster: ' + cid)
        ids.add(cid)
        require(cluster['modeId'] in modes, 'Unknown universe mode: ' + cid)
        require(cluster.get('titleKind') in {'editorial', 'source'}, 'Invalid title kind: ' + cid)
        require(cluster.get('layout') in {'comparison', 'split', 'sequence'}, 'Invalid layout: ' + cid)
        for key in ('title', 'question', 'intro'):
            require(isinstance(cluster.get(key), str) and cluster[key].strip(), 'Empty ' + key + ': ' + cid)
        require(cluster.get('panels'), 'No panels: ' + cid)
        source_titles = set()
        for index, panel in enumerate(cluster['panels']):
            label = cid + '/' + str(index)
            panels += 1
            require(panel.get('statementType') in {'explicit', 'interpretation'}, 'Invalid statement type: ' + label)
            for key in ('title', 'author', 'text'):
                require(isinstance(panel.get(key), str) and panel[key].strip(), 'Empty ' + key + ': ' + label)
            require(panel.get('evidence'), 'Panel has no evidence: ' + label)
            if 'parts' in panel:
                parts = panel['parts']
                require(isinstance(parts, list) and len(parts) >= 2, 'Invalid split parts: ' + label)
                require(isinstance(panel.get('partsRelation'), str) and panel['partsRelation'].strip(),
                        'Missing split relationship: ' + label)
                require('partsEvidenceTalkId' in panel, 'Missing split source Talk ID: ' + label)
                split_evidence = [e for e in panel['evidence']
                                  if e['talkId'] == panel['partsEvidenceTalkId']]
                require(split_evidence, 'Split source is outside panel evidence: ' + label)
                titles = set()
                for part in parts:
                    require(isinstance(part.get('title'), str) and part['title'].strip()
                            and isinstance(part.get('text'), str) and part['text'].strip(),
                            'Empty split role: ' + label)
                    require(part['title'] not in titles, 'Duplicate split role: ' + label)
                    titles.add(part['title'])
                    require(any(part['title'] in e['quote'] for e in split_evidence),
                            'Split role name absent from cited original: ' + label)
            for evidence in panel['evidence']:
                citations += 1
                original = document(evidence['docId'])
                source_titles.add(original['title'])
                require('talkId' in evidence, 'Missing Talk ID metadata: ' + label)
                sections = [s for s in original['sections'] if s.get('anchor') == evidence['anchor']]
                require(len(sections) == 1, 'Original section membership mismatch: ' + label)
                matches = [r for r in sections[0]['rows']
                           if r.get('talk_id') == evidence['talkId'] and r.get('text') == evidence['quote']]
                require(matches, 'Exact original quotation/Talk ID mismatch: ' + label)
                require(evidence['quote'], 'Empty quotation: ' + label)
                # The original row supplies the voice, including multi-author panels.
                speakers = {r.get('speaker', '') for r in matches}
                require(len(speakers) == 1, 'Ambiguous original speaker: ' + label)
                speaker = next(iter(speakers))
                if speaker and speaker != '화자 미지정':
                    require(speaker in panel['author'], 'Speaker attribution mismatch: ' + label)
                if 'speaker' in evidence:
                    require(evidence['speaker'] == speaker, 'Evidence speaker mismatch: ' + label)
                if evidence['docId'] in RUPERT_RECORDS:
                    source_id, row_hash = RUPERT_RECORDS[evidence['docId']]
                    require(any(r.get('source') == source_id and str(r.get('hash')) == row_hash for r in matches),
                            'Rupert curio original field/hash mismatch: ' + label)
                    require(original['title'] in panel['author'], 'Curio record attribution mismatch: ' + label)
                    cited_rupert.add(evidence['docId'])
        if cluster['titleKind'] == 'source':
            require(cluster['title'] in source_titles, 'Source title differs from cited originals: ' + cid)
        for related in cluster.get('related', []):
            related_count += 1
            document(related['docId'])
            require(isinstance(related.get('reason'), str) and related['reason'].strip(),
                    'Missing related-document reason: ' + cid)
    require(cited_rupert == set(RUPERT_RECORDS), 'Missing the two distinct Rupert curio records')
    # Verify that this read-only audit left the input and all source bytes intact.
    require(digest(data_file) == data_hash, 'Cluster input changed during verification')
    for rel, before in source_hashes.items():
        require(digest(site / rel) == before, 'Original changed during verification: ' + rel)
    return {'status': 'PASS', 'clusters': len(clusters), 'panels': panels, 'citations': citations,
            'relatedDocuments': related_count, 'sourceDocumentFiles': len(documents),
            'clusterSha256': data_hash, 'sourceSha256': source_hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=ROOT)
    parser.add_argument('--data-file', type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.site, args.data_file)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)}, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
