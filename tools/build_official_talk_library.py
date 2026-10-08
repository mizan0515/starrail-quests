"""Rebuild the bounded official Talk delta from approved source inputs."""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

from build_official_mission_talks import decode_talk_input
from build_official_universe_texts import corpus_digest
from build_mission_dialogue_supplements import refs, string_case_conditions

SITE = Path(__file__).resolve().parents[1]
SCHEMA = 'starrail-official-talk-library.v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def normalize_hashes(value):
    """Hash identifiers are decimal strings, including nested source records."""
    if isinstance(value, list):
        return [normalize_hashes(item) for item in value]
    if isinstance(value, dict):
        return {key: str(item) if key in ('Hash', 'hash') and type(item) is int
                else normalize_hashes(item) for key, item in value.items()}
    return value


def decoded_digest(source):
    records = {key: source[key] for key in ('tableRecord', 'textRecord', 'speakerRecord')}
    return sha(json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'))


def metadata_path(path):
    return path.endswith('.json') and (
        path.startswith(('Config/Level/', 'Story/', 'Config/LevelOutput/RuntimeGroup/',
                         'Config/LevelOutput/SharedRuntimeGroup/'))
        or bool(re.fullmatch(r'ExcelOutput/Performance(?:A|C|D|E|DS|CG|CLD|DLD|DSLD|Video|VideoLD)\.json', path))
        or path == 'ExcelOutput/MessageSectionConfig.json')


def ancestry(obj, pointer):
    value, path = obj, ''
    result = [(path, value)]
    for raw_part in pointer.strip('/').split('/'):
        part = raw_part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
        path += '/' + raw_part
        result.append((path, value))
    return result


def reference_context(obj, pointer, kind):
    parents = ancestry(obj, pointer)
    typed = next(({'type': value['$type'], 'pointer': path}
                  for path, value in reversed(parents)
                  if isinstance(value, dict) and isinstance(value.get('$type'), str)), None)
    conditions = []
    for path, value in parents:
        if not isinstance(value, dict) or not isinstance(value.get('Predicate'), dict):
            continue
        if not isinstance(value['Predicate'].get('$type'), str):
            continue
        for branch in ('SuccessTaskList', 'FailedTaskList'):
            branch_pointer = path + '/' + branch
            if pointer.startswith(branch_pointer + '/'):
                conditions.append({'kind': 'TYPED_PREDICATE_BRANCH', 'containerType': value.get('$type'),
                                   'predicatePointer': path + '/Predicate', 'branchPointer': branch_pointer,
                                   'branch': branch, 'predicate': value['Predicate']})
    conditions.extend(string_case_conditions(obj, [{'pointer': pointer, 'kind': kind}]))
    return {'typedContainer': typed, 'conditions': conditions}


def baseline_input():
    old, files = {}, {}
    page_ids = {page['id'] for page in read(SITE / 'data/dialogue-index.json')['pages']}
    for path in sorted((SITE / 'data/dialogues').glob('*.json')):
        raw = path.read_bytes()
        relative = path.relative_to(SITE).as_posix()
        files[relative] = sha(raw)
        document = json.loads(raw)
        assert document['id'] == path.stem and path.stem in page_ids
        for index, row in enumerate(document['section']['rows']):
            assert row['talk_id'] not in old
            old[row['talk_id']] = (relative, index, row,
                                   '대사/' + document['id'] + '.html#talk-' + str(row['talk_id']))
    return old, files


def changes_for(record, text, speaker, previous, projection):
    text_hash = str(record.get('TalkSentenceText', {}).get('Hash', 0))
    speaker_hash = str(record.get('TextmapTalkSentenceName', {}).get('Hash', 0))
    if previous is None:
        return ['ABSENT_PRESERVED_CORPUS']
    changes = []
    if str(previous.get('hash', '0')) != text_hash:
        changes.append('TEXT_HASH_CHANGED')
    if text and text['raw'] and previous['text'] != projection(text['raw']):
        changes.append('READABLE_TEXT_CHANGED')
    if str(previous.get('speaker_hash', '0')) != speaker_hash:
        changes.append('SPEAKER_HASH_CHANGED')
    if speaker_hash == '0' or speaker is not None:
        name = projection(speaker['raw']) if speaker else '화자 미지정'
        if previous['speaker'] != name:
            changes.append('READABLE_SPEAKER_CHANGED')
    if int(previous.get('voice', 0)) != int(record.get('VoiceID', 0)):
        changes.append('VOICE_ID_CHANGED')
    if not text or not text['raw']:
        changes.append('OFFICIAL_KOREAN_TEXT_UNAVAILABLE_FOR_BASELINE_ID')
    return changes


def assign_references(rows, archive, supplements):
    assert sha(archive.read_bytes()) == supplements['evidence']['archiveSha256']
    targets = {row['talk_id'] for row in rows}
    references, source_hashes = defaultdict(list), {}
    scanned = 0
    with tarfile.open(archive, 'r:gz') as tf:
        for member in tf:
            path = member.name.split('/', 1)[-1]
            if not member.isfile() or not metadata_path(path):
                continue
            raw = tf.extractfile(member).read()
            assert path not in source_hashes
            source_hashes[path] = sha(raw)
            obj = json.loads(raw)
            scanned += 1
            for tid, pointer, kind in refs(obj):
                if tid in targets:
                    references[tid].append({'source': path, 'sourceSha256': source_hashes[path],
                                            'pointer': pointer, 'referenceKind': kind,
                                            **reference_context(obj, pointer, kind)})
    assert scanned == supplements['counts']['metadataFilesScanned']
    for path, expected in supplements['evidence']['structureFiles'].items():
        assert source_hashes[path] == expected
    owners = defaultdict(list)
    for mid, coverage in supplements['coverage'].items():
        document = read(SITE / 'data/documents' / (mid + '.json'))
        for path, chain in coverage.get('sourceOwnership', {}).items():
            seed = chain[0] if chain else {}
            if seed.get('kind') != 'EXPLICIT_MAIN_MISSION_ID':
                continue
            assert 'quest-' + str(seed['missionId']) in document.get('missionParts', [mid])
            assert all(source_hashes[edge['source']] == edge['sourceSha256'] for edge in chain)
            for edge in chain:
                if 'tableSource' in edge:
                    assert source_hashes[edge['tableSource']] == edge['tableSha256']
            owners[path].append({'missionId': mid, 'ownership': chain,
                                 'scope': coverage.get('sourceTalkScopes', {}).get(path)})
    for row in rows:
        row['references'] = references.get(row['talk_id'], [])
        links = []
        for ref in row['references']:
            if ref['referenceKind'] == 'TalkSentence event reference' or not ref['typedContainer']:
                continue
            for owner in owners.get(ref['source'], []):
                scope = owner['scope']
                if scope and (row['talk_id'] not in scope['talkIds']
                              or not any(ref['pointer'].startswith(p + '/') for p in scope['pointers'])):
                    continue
                link = {**owner, 'source': ref['source'], 'sourceSha256': ref['sourceSha256'],
                        'referencePointer': ref['pointer'], 'referenceKind': ref['referenceKind'],
                        'typedContainer': ref['typedContainer'], 'conditions': ref['conditions']}
                if link not in links:
                    links.append(link)
        row['missionLinks'] = links
        row['assignmentStatus'] = 'EXPLICIT_CURRENT_MISSION_OWNER' if links else 'MISSION_OWNER_UNVERIFIED'
    return scanned


def public_projection(result):
    """Unreadable records remain in the structured research dataset."""
    return {key: value for key, value in result.items() if key != 'unresolvedRecords'}


def build(root, archive, skill):
    preserved = corpus_digest()
    old, baseline_files = baseline_input()
    table, texts, evidence, projection = decode_talk_input(root, skill)
    assert not set(old) - {record.get('TalkSentenceID', 0) for record in table}
    talk_pack = (root / evidence['talkTable']['file']).read_bytes()
    talk_entry = talk_pack[evidence['talkTable']['offset']:][:evidence['talkTable']['length']]
    kr_pack = (root / 'kr' / evidence['koreanPack']['file']).read_bytes()
    kr_entry = kr_pack[evidence['entry']['offset']:][:evidence['entry']['length']]
    all_rows, stats = [], Counter()
    for index, record in enumerate(table):
        tid = record.get('TalkSentenceID', 0)
        text_hash = str(record.get('TalkSentenceText', {}).get('Hash', 0))
        speaker_hash = str(record.get('TextmapTalkSentenceName', {}).get('Hash', 0))
        text, speaker = texts.get(text_hash), texts.get(speaker_hash)
        prior = old.get(tid)
        changes = changes_for(record, text, speaker, prior[2] if prior else None, projection)
        if not changes:
            stats['unchangedPreservedIds'] += 1
            continue
        source = {'clientVersion': evidence['clientVersion'], 'tableRow': index,
                  'tableOffset': record['_offset'], 'tableEnd': record['_end'],
                  'tableRecord': normalize_hashes(record), 'textRecord': normalize_hashes(text),
                  'speakerRecord': normalize_hashes(speaker),
                  'tableRecordSha256': sha(talk_entry[record['_offset']:record['_end']]),
                  'textRecordSha256': sha(kr_entry[text['offset']:text['end']]) if text else None,
                  'speakerRecordSha256': sha(kr_entry[speaker['offset']:speaker['end']]) if speaker else None}
        source['decodedRecordSha256'] = decoded_digest(source)
        available = bool(text and text['raw']) and (speaker_hash == '0' or speaker is not None)
        row = {'talk_id': tid, 'label': '대사', 'speaker': projection(speaker['raw']) if speaker else '화자 미지정' if speaker_hash == '0' else None,
               'text': projection(text['raw']) if text and text['raw'] else None,
               'raw': text['raw'] if text else None, 'speaker_raw': speaker['raw'] if speaker else '' if speaker_hash == '0' else None,
               'hash': text_hash, 'speaker_hash': speaker_hash, 'voice': record.get('VoiceID', 0),
               'offset': text['offset'] if text else None, 'end': text['end'] if text else None,
               'officialSource': source, 'changeKind': 'changed' if prior else 'new', 'changes': changes,
               'sourceStatus': 'READABLE_TEXT_AND_SPEAKER' if available else 'KOREAN_TEXT_HASH_ABSENT' if text is None else 'KOREAN_TEXT_OR_SPEAKER_UNAVAILABLE'}
        if prior:
            file, old_index, previous, url = prior
            row['previous'] = {key: previous[key] for key in ('talk_id', 'speaker', 'text', 'hash', 'speaker_hash', 'voice', 'offset', 'end')}
            row['previous']['url'] = url
            row['previousSource'] = {'sourceFile': file, 'sourceFileSha256': baseline_files[file], 'rowIndex': old_index,
                                     'rawComparisonStatus': 'UNVERIFIED_PRESERVED_RAW_STRING_UNAVAILABLE'}
        all_rows.append(row)
    supplements = read(SITE / 'data/mission-dialogue-supplements.json')
    scanned = assign_references(all_rows, archive, supplements)
    readable_rows = [row for row in all_rows if row['sourceStatus'] == 'READABLE_TEXT_AND_SPEAKER']
    unresolved = [row for row in all_rows if row['sourceStatus'] != 'READABLE_TEXT_AND_SPEAKER']
    counts = {'officialTalkTableRows': len(table), 'officialTextMapRows': len(texts),
              'preservedTalkRows': len(old), 'unchangedPreservedIds': stats['unchangedPreservedIds'],
              'deltaRows': len(all_rows), 'idsAbsentPreserved': sum(row['changeKind'] == 'new' for row in all_rows),
              'newReadable': sum(row['changeKind'] == 'new' for row in readable_rows),
              'changedPreservedIds': sum(row['changeKind'] == 'changed' for row in all_rows),
              'readableDeltaRows': len(readable_rows), 'unresolvedRecords': len(unresolved),
              'deltaTextHashAbsent': sum(row['officialSource']['textRecord'] is None for row in all_rows),
              'explicitAssignedDeltaRows': sum(bool(row['missionLinks']) for row in all_rows),
              'unassignedDeltaRows': sum(not row['missionLinks'] for row in all_rows),
              'readableUnassignedDeltaRows': sum(not row['missionLinks'] for row in readable_rows),
              'deltaRowsWithMetadataReference': sum(bool(row['references']) for row in all_rows),
              'metadataFilesScanned': scanned}
    for kind in ('READABLE_TEXT_CHANGED', 'SPEAKER_HASH_CHANGED', 'READABLE_SPEAKER_CHANGED', 'TEXT_HASH_CHANGED', 'VOICE_ID_CHANGED'):
        counts[kind] = sum(kind in row['changes'] for row in all_rows)
    result = normalize_hashes({'schema': SCHEMA,
              'evidence': {**evidence, 'preservedCorpus': preserved,
                           'preservedDialogueIndexSha256': sha((SITE / 'data/dialogue-index.json').read_bytes()),
                           'baselineRawComparisonStatus': 'UNVERIFIED_PRESERVED_RAW_STRING_UNAVAILABLE',
                           'metadataRepository': supplements['evidence']['repository'],
                           'metadataCommit': supplements['evidence']['commit'],
                           'archiveSha256': supplements['evidence']['archiveSha256'],
                           'missionAssignmentScope': 'EXPLICIT_CURRENT_MISSION_OWNER_AND_EXACT_TYPED_REFERENCE',
                           'versionSemantics': 'OBSERVED_OFFICIAL_SOURCE_VERSION'},
              'rows': readable_rows, 'unresolvedRecords': unresolved, 'counts': counts})
    assert corpus_digest() == preserved
    for path, content in ((SITE / 'data/official-talk-library.json', result),
                          (SITE / 'public/official-talk-library.json', public_projection(result))):
        path.write_text(json.dumps(content, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({'status': 'BUILT', **counts}, ensure_ascii=False), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--official-root', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--skill', type=Path, required=True)
    args = parser.parse_args()
    build(args.official_root, args.archive, args.skill)
