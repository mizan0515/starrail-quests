"""Validate the delta library, with optional independent original-byte checks."""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import re
import tarfile
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

from verify_official_universe_texts import readable, corpus, safe
from build_mission_dialogue_supplements import refs, string_case_conditions

SITE = Path(__file__).resolve().parents[1]
CHANGE_KEYS = ('READABLE_TEXT_CHANGED', 'SPEAKER_HASH_CHANGED', 'READABLE_SPEAKER_CHANGED', 'TEXT_HASH_CHANGED', 'VOICE_ID_CHANGED')
EXPECTED = {'officialTalkTableRows': 244380, 'officialTextMapRows': 474191, 'preservedTalkRows': 240078,
            'unchangedPreservedIds': 240038, 'deltaRows': 4342, 'idsAbsentPreserved': 4302,
            'newReadable': 3882, 'changedPreservedIds': 40, 'readableDeltaRows': 3922,
            'unresolvedRecords': 420, 'deltaTextHashAbsent': 420, 'explicitAssignedDeltaRows': 7,
            'unassignedDeltaRows': 4335, 'readableUnassignedDeltaRows': 3915,
            'deltaRowsWithMetadataReference': 104, 'metadataFilesScanned': 103849,
            'READABLE_TEXT_CHANGED': 35, 'SPEAKER_HASH_CHANGED': 5, 'READABLE_SPEAKER_CHANGED': 5,
            'TEXT_HASH_CHANGED': 0, 'VOICE_ID_CHANGED': 0}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def at(obj, pointer):
    for raw_key in pointer.split('/')[1:]:
        key = raw_key.replace('~1', '/').replace('~0', '~')
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    return obj


def normalized(value):
    if isinstance(value, list):
        return [normalized(item) for item in value]
    if isinstance(value, dict):
        return {key: str(item) if key in ('Hash', 'hash') and type(item) is int
                else normalized(item) for key, item in value.items()}
    return value


def precise(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('Hash', 'hash', 'speaker_hash'):
                assert isinstance(item, str) and re.fullmatch(r'0|[1-9][0-9]*', item)
                assert int(item) < 2**64
            precise(item)
    elif isinstance(value, list):
        for item in value:
            precise(item)
    elif type(value) is int:
        assert abs(value) <= 2**53 - 1, ('UNSAFE_JSON_INTEGER', value)


def baseline():
    rows, files = {}, {}
    pages = {page['id'] for page in read(SITE / 'data/dialogue-index.json')['pages']}
    for path in sorted((SITE / 'data/dialogues').glob('*.json')):
        data = read(path)
        assert data['id'] == path.stem and path.stem in pages
        relative = path.relative_to(SITE).as_posix()
        files[relative] = sha(path.read_bytes())
        for index, row in enumerate(data['section']['rows']):
            assert row['talk_id'] not in rows
            rows[row['talk_id']] = (row, relative, index,
                                   '대사/' + data['id'] + '.html#talk-' + str(row['talk_id']))
    return rows, files


def reasons(row, old):
    if old is None:
        return ['ABSENT_PRESERVED_CORPUS']
    changes = []
    if str(old['hash']) != row['hash']:
        changes.append('TEXT_HASH_CHANGED')
    if row['text'] is not None and old['text'] != row['text']:
        changes.append('READABLE_TEXT_CHANGED')
    if str(old['speaker_hash']) != row['speaker_hash']:
        changes.append('SPEAKER_HASH_CHANGED')
    if row['speaker'] is not None and old['speaker'] != row['speaker']:
        changes.append('READABLE_SPEAKER_CHANGED')
    if old.get('voice', 0) != row['voice']:
        changes.append('VOICE_ID_CHANGED')
    if not row['raw']:
        changes.append('OFFICIAL_KOREAN_TEXT_UNAVAILABLE_FOR_BASELINE_ID')
    return changes


def source_digest(source):
    records = {key: source[key] for key in ('tableRecord', 'textRecord', 'speakerRecord')}
    return sha(json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'))


def row_check(row, evidence, old, baseline_files):
    precise(row)
    source = row['officialSource']
    table, text, speaker = source['tableRecord'], source['textRecord'], source['speakerRecord']
    assert row['label'] == '대사' and type(row['talk_id']) is int and row['talk_id'] == table.get('TalkSentenceID', 0)
    assert source['clientVersion'] == evidence['clientVersion'] == 'OSPRODWin4.6.0'
    assert 0 <= source['tableRow'] < evidence['talkTable']['rows']
    assert 0 <= source['tableOffset'] < source['tableEnd'] <= evidence['talkTable']['length']
    assert source['tableOffset'] == table['_offset'] and source['tableEnd'] == table['_end']
    assert table.get('TalkSentenceText', {}).get('Hash', '0') == row['hash']
    assert table.get('TextmapTalkSentenceName', {}).get('Hash', '0') == row['speaker_hash']
    assert row['voice'] == table.get('VoiceID', 0)
    assert source['decodedRecordSha256'] == source_digest(source)
    assert re.fullmatch(r'[0-9a-f]{64}', source['tableRecordSha256'])
    if text is None:
        assert row['raw'] is None and row['text'] is None and row['offset'] is None and row['end'] is None
        assert source['textRecordSha256'] is None and row['sourceStatus'] == 'KOREAN_TEXT_HASH_ABSENT'
    else:
        assert text['hash'] == row['hash'] and row['raw'] == text['raw']
        assert row['text'] == readable(row['raw']) and row['text']
        assert row['offset'] == text['offset'] and row['end'] == text['end']
        assert 0 <= row['offset'] < row['end'] <= evidence['entry']['length']
        assert re.fullmatch(r'[0-9a-f]{64}', source['textRecordSha256'])
        assert row['sourceStatus'] == 'READABLE_TEXT_AND_SPEAKER'
    if row['speaker_hash'] == '0':
        assert speaker is None and row['speaker_raw'] == '' and row['speaker'] == '화자 미지정'
        assert source['speakerRecordSha256'] is None
    else:
        assert speaker['hash'] == row['speaker_hash'] and speaker['raw'] == row['speaker_raw']
        assert row['speaker'] == readable(speaker['raw'])
        assert 0 <= speaker['offset'] < speaker['end'] <= evidence['entry']['length']
        assert re.fullmatch(r'[0-9a-f]{64}', source['speakerRecordSha256'])
    previous = old.get(row['talk_id'])
    assert row['changeKind'] == ('changed' if previous else 'new')
    assert row['changes'] == reasons(row, previous[0] if previous else None) and row['changes']
    if previous:
        original, file, index, url = previous
        assert row['previous'] == {**{key: original[key] for key in ('talk_id', 'speaker', 'text', 'hash', 'speaker_hash', 'voice', 'offset', 'end')}, 'url': url}
        assert row['previousSource'] == {'sourceFile': file, 'sourceFileSha256': baseline_files[file], 'rowIndex': index,
                                         'rawComparisonStatus': 'UNVERIFIED_PRESERVED_RAW_STRING_UNAVAILABLE'}
    else:
        assert 'previous' not in row and 'previousSource' not in row


def links_check(row, supplements):
    links = row['missionLinks']
    assert row['assignmentStatus'] == ('EXPLICIT_CURRENT_MISSION_OWNER' if links else 'MISSION_OWNER_UNVERIFIED')
    assert len({json.dumps(ref, sort_keys=True) for ref in row['references']}) == len(row['references'])
    expected = []
    for ref in row['references']:
        assert ref['referenceKind'] in ('TalkSentenceID', 'TalkSentenceIDList', 'TalkSentence event reference')
        assert ref['pointer'].startswith('/') and re.fullmatch(r'[0-9a-f]{64}', ref['sourceSha256'])
        assert ref['source'].startswith(('Config/', 'Story/', 'ExcelOutput/')) and ref['source'].endswith('.json')
        if ref['source'] in supplements['evidence']['structureFiles']:
            assert ref['sourceSha256'] == supplements['evidence']['structureFiles'][ref['source']]
        if ref['referenceKind'] == 'TalkSentence event reference' or not ref['typedContainer']:
            continue
        for mid, coverage in supplements['coverage'].items():
            chain = coverage.get('sourceOwnership', {}).get(ref['source'])
            if not chain or chain[0].get('kind') != 'EXPLICIT_MAIN_MISSION_ID':
                continue
            scope = coverage.get('sourceTalkScopes', {}).get(ref['source'])
            if scope and (row['talk_id'] not in scope['talkIds']
                          or not any(ref['pointer'].startswith(p + '/') for p in scope['pointers'])):
                continue
            link = {'missionId': mid, 'ownership': chain, 'scope': scope,
                    'source': ref['source'], 'sourceSha256': ref['sourceSha256'], 'referencePointer': ref['pointer'],
                    'referenceKind': ref['referenceKind'], 'typedContainer': ref['typedContainer'], 'conditions': ref['conditions']}
            if link not in expected:
                expected.append(link)
    assert links == expected
    for link in links:
        document = read(SITE / 'data/documents' / (link['missionId'] + '.json'))
        seed = link['ownership'][0]
        assert 'quest-' + str(seed['missionId']) in document.get('missionParts', [link['missionId']])
        assert seed['canonicalMissionId'] == int(link['missionId'].removeprefix('quest-'))
        assert sha((SITE / seed['membershipSource']).read_bytes()) == seed['membershipSha256']
        for edge in link['ownership']:
            assert edge['kind'] in ('EXPLICIT_MAIN_MISSION_ID', 'EXPLICIT_JSON_PATH', 'EXACT_UNIQUE_EVENT_CHANNEL', 'EXPLICIT_PERFORMANCE_LOOKUP')
            assert edge['sourceSha256'] == supplements['evidence']['structureFiles'][edge['source']]
            if edge['kind'] == 'EXACT_UNIQUE_EVENT_CHANNEL':
                assert edge['producerCount'] == edge['consumerCount'] == 1
            if edge['kind'] == 'EXPLICIT_PERFORMANCE_LOOKUP':
                assert edge['lookupScope'] == 'TYPED_PRIMARY_TABLE'
                assert edge['tableSha256'] == supplements['evidence']['structureFiles'][edge['tableSource']]


def counts_for(data, old, supplements):
    rows = data['rows'] + data['unresolvedRecords']
    changed = sum(row['changeKind'] == 'changed' for row in rows)
    counts = {'officialTalkTableRows': data['evidence']['talkTable']['rows'],
              'officialTextMapRows': data['evidence']['entry']['rows'], 'preservedTalkRows': len(old),
              'unchangedPreservedIds': len(old) - changed, 'deltaRows': len(rows),
              'idsAbsentPreserved': sum(row['changeKind'] == 'new' for row in rows),
              'newReadable': sum(row['changeKind'] == 'new' for row in data['rows']),
              'changedPreservedIds': changed, 'readableDeltaRows': len(data['rows']),
              'unresolvedRecords': len(data['unresolvedRecords']),
              'deltaTextHashAbsent': sum(row['officialSource']['textRecord'] is None for row in rows),
              'explicitAssignedDeltaRows': sum(bool(row['missionLinks']) for row in rows),
              'unassignedDeltaRows': sum(not row['missionLinks'] for row in rows),
              'readableUnassignedDeltaRows': sum(not row['missionLinks'] for row in data['rows']),
              'deltaRowsWithMetadataReference': sum(bool(row['references']) for row in rows),
              'metadataFilesScanned': supplements['counts']['metadataFilesScanned']}
    counts.update({kind: sum(kind in row['changes'] for row in rows) for kind in CHANGE_KEYS})
    return counts


def validate(data, old, files, supplements):
    precise(data)
    safe(data)
    assert data['schema'] == 'starrail-official-talk-library.v1'
    evidence = data['evidence']
    assert evidence['preservedCorpus'] == corpus()
    assert evidence['preservedDialogueIndexSha256'] == sha((SITE / 'data/dialogue-index.json').read_bytes())
    assert evidence['baselineRawComparisonStatus'] == 'UNVERIFIED_PRESERVED_RAW_STRING_UNAVAILABLE'
    assert evidence['versionSemantics'] == 'OBSERVED_OFFICIAL_SOURCE_VERSION'
    assert evidence['missionAssignmentScope'] == 'EXPLICIT_CURRENT_MISSION_OWNER_AND_EXACT_TYPED_REFERENCE'
    assert evidence['metadataCommit'] == supplements['evidence']['commit']
    assert evidence['archiveSha256'] == supplements['evidence']['archiveSha256']
    assert evidence['metadataRepository'] == supplements['evidence']['repository']
    assert evidence['catalogSha256'] == 'ae92b3dd2417efbb9cd08e463891051ed515df2f97d40137223cec394a7e6132'
    assert evidence['talkTable']['sha256'] == 'ae6cc8e41213ccecc430a346909daf38ff4013d6b1441ddba384032d77b3ffd4'
    assert evidence['koreanPack']['sha256'] == '99dadf3786823c934ff12e970df594a77d413f8b090d2645f58cc8ad903fda20'
    assert evidence['talkTable']['fullEofVerified'] is True and evidence['entry']['fullEofVerified'] is True
    rows = data['rows'] + data['unresolvedRecords']
    assert len({row['talk_id'] for row in rows}) == len(rows)
    assert len({row['officialSource']['tableRow'] for row in rows}) == len(rows)
    assert all(row['sourceStatus'] == 'READABLE_TEXT_AND_SPEAKER' for row in data['rows'])
    assert all(row['sourceStatus'] == 'KOREAN_TEXT_HASH_ABSENT' for row in data['unresolvedRecords'])
    for row in rows:
        row_check(row, evidence, old, files)
        links_check(row, supplements)
    assert data['counts'] == counts_for(data, old, supplements) == EXPECTED


def metadata_context(obj, pointer, kind):
    ancestors, current, path = [('', obj)], obj, ''
    for part in pointer.split('/')[1:]:
        key = part.replace('~1', '/').replace('~0', '~')
        current = current[int(key)] if isinstance(current, list) else current[key]
        path += '/' + part
        ancestors.append((path, current))
    typed = next(({'type': value['$type'], 'pointer': p} for p, value in reversed(ancestors)
                  if isinstance(value, dict) and isinstance(value.get('$type'), str)), None)
    conditions = []
    for p, value in ancestors:
        if not isinstance(value, dict) or not isinstance(value.get('Predicate'), dict):
            continue
        if not isinstance(value['Predicate'].get('$type'), str):
            continue
        for branch in ('SuccessTaskList', 'FailedTaskList'):
            branch_pointer = p + '/' + branch
            if pointer.startswith(branch_pointer + '/'):
                conditions.append({'kind': 'TYPED_PREDICATE_BRANCH', 'containerType': value.get('$type'),
                                   'predicatePointer': p + '/Predicate', 'branchPointer': branch_pointer,
                                   'branch': branch, 'predicate': value['Predicate']})
    conditions.extend(string_case_conditions(obj, [{'pointer': pointer, 'kind': kind}]))
    return {'typedContainer': typed, 'conditions': conditions}


def deep_verify(data, old, root, archive, skill):
    from build_official_mission_talks import decode_talk_input
    talks, texts, evidence, projection = decode_talk_input(root, skill)
    for key in ('clientVersion', 'officialHost', 'manifestSha256', 'catalogSha256', 'catalogFile', 'talkTable', 'koreanPack', 'entry'):
        assert data['evidence'][key] == evidence[key]
    expected_ids = set()
    for record in talks:
        tid = record.get('TalkSentenceID', 0)
        text_hash = str(record.get('TalkSentenceText', {}).get('Hash', 0))
        speaker_hash = str(record.get('TextmapTalkSentenceName', {}).get('Hash', 0))
        text, speaker = texts.get(text_hash), texts.get(speaker_hash)
        prior = old.get(tid)
        if prior is None:
            expected_ids.add(tid)
            continue
        row = prior[0]
        name = projection(speaker['raw']) if speaker else '화자 미지정' if speaker_hash == '0' else None
        if (row['hash'] != text_hash or row['speaker_hash'] != speaker_hash
                or row.get('voice', 0) != record.get('VoiceID', 0)
                or not text or not text['raw'] or row['text'] != projection(text['raw'])
                or name is not None and row['speaker'] != name):
            expected_ids.add(tid)
    rows = data['rows'] + data['unresolvedRecords']
    assert {row['talk_id'] for row in rows} == expected_ids
    assert set(old) <= {record.get('TalkSentenceID', 0) for record in talks}
    talk_pack = (root / evidence['talkTable']['file']).read_bytes()
    talk_entry = talk_pack[evidence['talkTable']['offset']:][:evidence['talkTable']['length']]
    kr_pack = (root / 'kr' / evidence['koreanPack']['file']).read_bytes()
    kr_entry = kr_pack[evidence['entry']['offset']:][:evidence['entry']['length']]
    for row in rows:
        source = row['officialSource']
        assert source['tableRecord'] == normalized(talks[source['tableRow']])
        assert source['textRecord'] == normalized(texts.get(row['hash']))
        assert source['speakerRecord'] == normalized(texts.get(row['speaker_hash']))
        assert source['tableRecordSha256'] == sha(talk_entry[source['tableOffset']:source['tableEnd']])
        for prefix in ('text', 'speaker'):
            record = source[prefix + 'Record']
            assert source[prefix + 'RecordSha256'] == (sha(kr_entry[record['offset']:record['end']]) if record else None)
    assert sha(archive.read_bytes()) == data['evidence']['archiveSha256']
    wanted = {ref['source'] for row in rows for ref in row['references']}
    for row in rows:
        for link in row['missionLinks']:
            for edge in link['ownership']:
                wanted.add(edge['source'])
                if 'target' in edge:
                    wanted.add(edge['target'])
                if 'tableSource' in edge:
                    wanted.add(edge['tableSource'])
    sources, references = {}, defaultdict(list)
    total = 0
    with tarfile.open(archive, 'r:gz') as tf:
        for member in tf:
            path = member.name.split('/', 1)[-1]
            if not member.isfile() or not path.endswith('.json'):
                continue
            matched = (path.startswith(('Config/Level/', 'Story/', 'Config/LevelOutput/RuntimeGroup/', 'Config/LevelOutput/SharedRuntimeGroup/'))
                       or bool(re.fullmatch(r'ExcelOutput/Performance(?:A|C|D|E|DS|CG|CLD|DLD|DSLD|Video|VideoLD)\.json', path))
                       or path == 'ExcelOutput/MessageSectionConfig.json')
            if not matched and path not in wanted:
                continue
            raw = tf.extractfile(member).read()
            obj = json.loads(raw)
            if path in wanted:
                assert path not in sources
                sources[path] = (obj, sha(raw))
            if matched:
                total += 1
                for tid, pointer, kind in refs(obj):
                    if tid in expected_ids:
                        references[tid].append(normalized({'source': path, 'sourceSha256': sha(raw), 'pointer': pointer,
                                                         'referenceKind': kind, **metadata_context(obj, pointer, kind)}))
    assert total == data['counts']['metadataFilesScanned'] and set(sources) == wanted
    for row in rows:
        assert row['references'] == references.get(row['talk_id'], [])
        for link in row['missionLinks']:
            for edge in link['ownership']:
                obj, digest = sources[edge['source']]
                assert digest == edge['sourceSha256']
                value = at(obj, edge['pointer'])
                if edge['kind'] == 'EXPLICIT_MAIN_MISSION_ID':
                    assert value == edge['missionId']
                elif edge['kind'] == 'EXPLICIT_JSON_PATH':
                    assert value == edge['target']
                elif edge['kind'] == 'EXACT_UNIQUE_EVENT_CHANNEL':
                    assert value == at(sources[edge['target']][0], edge['producerPointer']) == edge['event']
                elif edge['kind'] == 'EXPLICIT_PERFORMANCE_LOOKUP':
                    table, table_sha = sources[edge['tableSource']]
                    assert table_sha == edge['tableSha256']
                    assert value == at(table, edge['idPointer']) == edge['performanceId']
                    assert at(table, edge['pathPointer']) == edge['target']
    return {'originalTableRows': len(talks), 'originalTextMapRows': len(texts), 'metadataFiles': total,
            'exactSourceFiles': len(sources), 'deltaRecordsCompared': len(rows)}


def mutations(data, old, files, supplements):
    original = data['rows'][0]
    tests = []
    for key, value in (('raw', 'altered'), ('hash', '1'), ('offset', original['offset'] + 1),
                       ('speaker', 'altered'), ('changeKind', 'new' if original['changeKind'] == 'changed' else 'changed')):
        changed = deepcopy(original)
        changed[key] = value
        tests.append((key, changed))
    changed = deepcopy(original)
    changed['officialSource']['tableRecord']['TalkSentenceText']['Hash'] = int(changed['hash'])
    tests.append(('nested64BitHash', changed))
    changed = deepcopy(original)
    changed['officialSource']['textRecord']['offset'] += 1
    changed['offset'] += 1
    tests.append(('matchingOffsetPair', changed))
    changed = deepcopy(original)
    changed['officialSource']['textRecord']['raw'] = changed['raw'] = changed['text'] = 'altered'
    tests.append(('matchingRawPair', changed))
    changed = deepcopy(next(row for row in data['rows'] if row['changeKind'] == 'changed'))
    changed['previous']['text'] = 'altered'
    tests.append(('previousOriginal', changed))
    rejected = 0
    for name, row in tests:
        try:
            row_check(row, data['evidence'], old, files)
        except (AssertionError, KeyError, TypeError, ValueError):
            rejected += 1
        else:
            raise AssertionError('Accepted mutation: ' + name)
    altered_counts = dict(data['counts'])
    altered_counts['readableDeltaRows'] += 1
    assert altered_counts != counts_for(data, old, supplements)
    rejected += 1
    assigned = deepcopy(next(row for row in data['rows'] if row['missionLinks']))
    assigned['missionLinks'][0]['missionId'] = 'quest-1054411'
    try:
        links_check(assigned, supplements)
    except (AssertionError, KeyError, TypeError, ValueError):
        rejected += 1
    else:
        raise AssertionError('Accepted mutation: missionOwner')
    return rejected


def verify(root=None, archive=None, skill=None):
    data = read(SITE / 'data/official-talk-library.json')
    public = read(SITE / 'public/official-talk-library.json')
    assert public == {key: value for key, value in data.items() if key != 'unresolvedRecords'}
    assert 'unresolvedRecords' not in public and len(public['rows']) == 3922
    old, files = baseline()
    supplements = read(SITE / 'data/mission-dialogue-supplements.json')
    validate(data, old, files, supplements)
    rejected = mutations(data, old, files, supplements)
    deep = None
    if root or archive or skill:
        assert root and archive and skill
        deep = deep_verify(data, old, root, archive, skill)
    result = {'status': 'PASS', 'readableRows': len(data['rows']), 'unresolvedRecords': len(data['unresolvedRecords']),
              'changedRows': data['counts']['changedPreservedIds'], 'assignedRows': data['counts']['explicitAssignedDeltaRows'],
              'preservedTalkRows': len(old), 'mutationRejections': rejected, 'deepOriginalBytes': deep}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--official-root', type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--skill', type=Path)
    parser.add_argument('--artifact-only', action='store_true', help='Validate repository artifacts without external source inputs.')
    parser.add_argument('--self-test', action='store_true', help='Run mutation checks (also performed by default).')
    args = parser.parse_args()
    assert not args.artifact_only or not (args.official_root or args.archive or args.skill)
    verify(args.official_root, args.archive, args.skill)
