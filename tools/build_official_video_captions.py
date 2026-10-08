"""Read official CaptionList/Korean records and explicit runtime or scoped MainMission owner chains.

No downloads. Metadata supplies schema/paths/conditions; all Korean body comes
from the official Korean TextMap. Unknown fields, path identity collisions,
missing Korean hashes and unowned playback sites remain measured exclusions.
"""
import argparse
from collections import Counter, defaultdict, deque
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import tarfile
from urllib.parse import quote

sys.dont_write_bytecode = True
SITE = Path(__file__).resolve().parents[1]
METADATA_COMMIT = '8b178dd48698e5e7b12f0cc319ddab149f2ffc5c'
METADATA_REPO = 'DimbreathBot/TurnBasedGameData'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unsigned(raw, pos):
    value = 0
    for shift in range(0, 70, 7):
        if pos >= len(raw):
            raise ValueError('Truncated varint')
        byte = raw[pos]
        pos += 1
        value |= (byte & 127) << shift
        if byte < 128:
            if value > 0xffffffffffffffff:
                raise ValueError('Overflow uint64')
            return value, pos
    raise ValueError('Overflow varint')


def decode_caption(raw):
    """Only demonstrated root/row fields. Return complete byte-span evidence."""
    flags, pos = unsigned(raw, 0)
    if flags != 1:
        raise ValueError('Unsupported CaptionList root presence')
    encoded, pos = unsigned(raw, pos)
    count = (encoded >> 1) ^ -(encoded & 1)
    if not 0 <= count <= 100000 or count > (len(raw) - pos) // 11:
        raise ValueError('Invalid CaptionList count')
    rows = []
    for index in range(count):
        begin = pos
        flags, pos = unsigned(raw, pos)
        if flags != 13:
            raise ValueError('Unsupported caption row presence')
        legacy, pos = unsigned(raw, pos)
        primary, pos = unsigned(raw, pos)
        if legacy > 0xffffffff or not primary:
            raise ValueError('Invalid caption hash')
        if pos + 8 > len(raw):
            raise ValueError('Truncated caption time')
        start, end = struct.unpack_from('<ff', raw, pos)
        pos += 8
        if not all(math.isfinite(x) and x >= 0 for x in (start, end)) or start > end:
            raise ValueError('Invalid caption interval')
        rows.append({'hash': primary, 'legacy': legacy, 'startTime': start,
                     'endTime': end, 'offset': begin, 'end': pos, 'index': index})
    if pos != len(raw):
        raise ValueError('Unconsumed caption bytes')
    return rows


def fixture_identity(data):
    """All fixture fields/types must match; times use IEEE binary32 identity."""
    if not isinstance(data, dict) or set(data) != {'CaptionList'} or not isinstance(data['CaptionList'], list):
        raise ValueError('Unsupported caption fixture root')
    result = []
    for row in data['CaptionList']:
        if not isinstance(row, dict) or set(row) != {'CaptionTextID', 'StartTime', 'EndTime'}:
            raise ValueError('Unsupported caption fixture fields')
        if not isinstance(row['CaptionTextID'], dict) or set(row['CaptionTextID']) != {'Hash'}:
            raise ValueError('Unsupported fixture hash fields')
        primary = row['CaptionTextID']['Hash']
        if type(primary) is not int or not 0 < primary <= 0xffffffffffffffff:
            raise ValueError('Invalid fixture hash type')
        if any(type(row[k]) not in (int, float) for k in ('StartTime', 'EndTime')):
            raise ValueError('Invalid fixture time type')
        result.append((primary, struct.pack('<f', row['StartTime']), struct.pack('<f', row['EndTime'])))
    return tuple(result)


def caption_identity(rows):
    return tuple((r['hash'], struct.pack('<f', r['startTime']), struct.pack('<f', r['endTime'])) for r in rows)


def corpus_digest(site):
    """Existing 4.5 dialogue bytes are a preservation guard, not new body."""
    files = sorted((site / 'data/dialogues').glob('*.json'))
    if (site / 'data/dialogue-index.json').exists():
        files.append(site / 'data/dialogue-index.json')
    manifest = [(p.relative_to(site).as_posix(), sha(p.read_bytes())) for p in files]
    return {'files': len(manifest), 'sha256': sha(json.dumps(manifest, separators=(',', ':')).encode())}


def metadata_url(source):
    return f'https://github.com/{METADATA_REPO}/blob/{METADATA_COMMIT}/{quote(source, safe="/")}'


def select_video_performance(records, performance_type):
    if performance_type not in ('PlayVideo', 'Video'):
        return []
    selected = [r for r in records if r['source'] == 'ExcelOutput/PerformanceVideo.json']
    if not selected:
        selected = [r for r in records if r['source'] == 'ExcelOutput/PerformanceVideoLD.json']
    if len(selected) != 1 or len({r['target'] for r in records}) != 1:
        return []
    return selected


def ancestors(data, pointer, source):
    result = []
    node = data
    parts = pointer.split('/')[1:]
    for depth, part in enumerate(parts):
        prefix = '/' + '/'.join(parts[:depth])
        if isinstance(node, dict) and isinstance(node.get('Predicate'), dict) and part in ('SuccessTaskList', 'FailedTaskList', 'FailTaskList'):
            result.append({'source': source, 'predicatePointer': prefix + '/Predicate',
                           'branchPointer': prefix + '/' + part, 'branch': part,
                           'predicate': node['Predicate']})
        if isinstance(node, dict) and part == 'OnEvent' and node.get('$type'):
            event = {k: v for k, v in node.items() if k in ('$type', 'CustomString', 'EventName', 'Name', 'Key')}
            result.append({'source': source, 'eventPointer': prefix,
                           'branchPointer': prefix + '/OnEvent', 'event': event})
        node = node[int(part)] if isinstance(node, list) else node[part]
    return result


def build(args):
    before = corpus_digest(args.site)
    sys.path.insert(0, str(args.skill / 'scripts'))
    from binary import decode_textmap, read_catalog
    spec = importlib.util.spec_from_file_location('caption_owner_metadata', args.site / 'tools/build_mission_dialogue_supplements.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    envelope = json.loads((args.official_root / 'catalog.json').read_text('utf8'))
    manifest = (args.official_root / 'M_DesignV.bytes').read_bytes()
    if not manifest.startswith(b'SRMI') or len(manifest) != 66:
        raise ValueError('Unsupported official manifest')
    digest = b''.join(manifest[i:i + 4][::-1] for i in range(28, 44, 4)).hex()
    design_path = args.official_root / ('DesignV_' + digest + '.bytes')
    design_raw = design_path.read_bytes()
    catalog = read_catalog(design_raw)
    if catalog != envelope['catalog']:
        # JSON tuples roundtrip to lists; compare normalized structures.
        if json.loads(json.dumps(catalog)) != envelope['catalog']:
            raise ValueError('Cached catalog differs from original DesignV')
    roots = [args.official_root] + args.pack_dir
    pack_manifest = []
    missing_packs = []
    packs = []
    for item in catalog:
        if item['language']:
            continue
        path = next((root / item['file'] for root in roots if (root / item['file']).is_file()), None)
        if path is None:
            missing_packs.append({'file': item['file'], 'entries': len(item['entries']), 'size': item['size']})
            continue
        raw = path.read_bytes()
        if len(raw) != item['size'] or hashlib.md5(raw).hexdigest() != Path(item['file']).stem:
            raise ValueError('Official pack catalog digest/size mismatch: ' + item['file'])
        evidence = {'file': item['file'], 'sha256': sha(raw), 'size': len(raw), 'entries': len(item['entries'])}
        pack_manifest.append(evidence)
        packs.append((item, raw, evidence))
    fixtures = {}
    fixture_by_identity = defaultdict(list)
    unsupported = []
    video_config = None
    video_sha = None
    with tarfile.open(args.archive) as archive:
        for member in archive:
            path = member.name.split('/', 1)[-1]
            if not member.isfile():
                continue
            if path == 'ExcelOutput/VideoConfig.json':
                raw = archive.extractfile(member).read()
                video_config = json.loads(raw)
                video_sha = sha(raw)
            elif path.startswith('Config/CutSceneCaption/') and path.endswith('.json'):
                raw = archive.extractfile(member).read()
                try:
                    identity = fixture_identity(json.loads(raw))
                except (ValueError, TypeError, KeyError, OverflowError) as error:
                    unsupported.append({'path': path, 'reason': str(error)})
                    continue
                fixtures[path] = {'sha256': sha(raw), 'rows': len(identity)}
                fixture_by_identity[identity].append(path)
    if video_config is None:
        raise ValueError('VideoConfig metadata unavailable')
    matches = defaultdict(list)
    scanned = strict_records = 0
    for item, raw, evidence in packs:
        for key, size, offset in item['entries']:
            scanned += 1
            entry = raw[offset:offset + size]
            if len(entry) < 2 or entry[0] != 1:
                continue
            try:
                rows = decode_caption(entry)
            except (ValueError, struct.error):
                continue
            strict_records += 1
            paths = fixture_by_identity.get(caption_identity(rows), [])
            for path in paths:
                matches[path].append({'packFile': item['file'], 'packSha256': evidence['sha256'],
                                      'entryKey': str(key), 'entryOffset': offset, 'entryLength': size,
                                      'entrySha256': sha(entry), 'consumedBytes': size,
                                      'fixturePath': path, 'fixtureSha256': fixtures[path]['sha256'],
                                      'fixtureIdentityPaths': paths, 'rows': rows})
    unique = {path: records[0] for path, records in matches.items()
              if len(records) == 1 and len(records[0]['fixtureIdentityPaths']) == 1}
    kr = next(item for item in catalog if item['language'] == 'kr')
    kr_path = args.official_root / 'kr' / kr['file']
    kr_raw = kr_path.read_bytes()
    if len(kr_raw) != kr['size'] or hashlib.md5(kr_raw).hexdigest() != Path(kr['file']).stem:
        raise ValueError('Official Korean pack catalog digest/size mismatch')
    key, size, offset = next(r for r in kr['entries'] if r[0] == args.textmap_key)
    text_rows = decode_textmap(kr_raw[offset:offset + size])
    textmap = {r['hash']: r for r in text_rows}
    unresolved_korean = [{'captionPath': path, 'captionRowIndex': row['index'],
                          'hash': str(row['hash']), 'startTime': row['startTime'], 'endTime': row['endTime'],
                          'entryKey': caption['entryKey']}
                         for path, caption in unique.items() for row in caption['rows']
                         if row['hash'] not in textmap or not textmap[row['hash']]['raw']]
    text_source = {'packFile': 'kr/' + kr['file'], 'packSha256': sha(kr_raw),
                   'entryKey': str(key), 'entryOffset': offset, 'entryLength': size,
                   'entrySha256': sha(kr_raw[offset:offset + size]), 'consumedBytes': size}
    metadata, hashes, performances = helper.load_metadata(args.archive)
    reverse = defaultdict(list)
    lookup_diagnostics = []
    for source, data in metadata.items():
        if not source.startswith(('Config/', 'Story/')):
            continue
        for target, pointer in helper.path_refs(data):
            reverse[target].append({'kind': 'EXPLICIT_JSON_PATH', 'source': source,
                                    'sourceSha256': hashes[source], 'pointer': pointer, 'target': target})
        for task, pointer in helper.objects(data):
            if task.get('$type') != 'RPG.GameCore.TriggerPerformance':
                continue
            pid = task.get('PerformanceID')
            kind = task.get('PerformanceType')
            records = performances.get(pid, [])
            if kind in ('PlayVideo', 'Video'):
                selected = select_video_performance(records, kind)
                valid = bool(selected)
                lookup_diagnostics.append({'source': source, 'pointer': pointer, 'performanceId': pid,
                                           'performanceType': kind, 'accepted': valid, 'records': records,
                                           'duplicateIdTables': {k: v for k, v in Counter(r['source'] for r in records).items() if v > 1},
                                           'foreignTableRecords': [r for r in records if r['source'] not in ('ExcelOutput/PerformanceVideo.json', 'ExcelOutput/PerformanceVideoLD.json')]})
                if not valid:
                    continue
                lookup = 'PLAYVIDEO_EXACT_ID_VIDEO_TABLE_CROSS_TABLE_UNIQUE'
            else:
                selected, lookup = helper.performance_matches(performances, pid, kind)
                if len({r['target'] for r in selected}) != 1:
                    continue
            record = selected[0]
            reverse[record['target']].append({'kind': 'EXPLICIT_PERFORMANCE_LOOKUP', 'source': source,
                                            'sourceSha256': hashes[source], 'pointer': pointer + '/PerformanceID',
                                            'performanceId': pid, 'performanceType': kind, 'lookupScope': lookup,
                                            'tableSource': record['source'], 'tableSha256': hashes[record['source']],
                                            'idPointer': record['idPointer'], 'pathPointer': record['pathPointer'],
                                            'target': record['target']})
    runtime_owners, owner_conflicts = helper.runtime_group_ownership_index(metadata)
    seeds = defaultdict(list)
    for owner, records in runtime_owners.items():
        for source, pointer in records:
            seeds[source].append({'kind': 'EXPLICIT_RUNTIME_OWNERMAINMISSIONID', 'source': source,
                                  'sourceSha256': hashes[source], 'pointer': pointer, 'missionId': owner})

    # The owner is scoped to the actual MissionJsonPath row, not its folder.
    main_seeds = defaultdict(list)
    catalog = json.loads((args.site / 'data/catalog.json').read_text('utf8'))
    registered = {r['id'] for r in catalog if r['id'].startswith('quest-')}
    for ident in list(registered):
        document = json.loads((args.site / 'data/documents' / (ident + '.json')).read_text('utf8'))
        registered.update(a for a in document.get('aliases', []) if a in document.get('missionParts', []))
    for path, obj in metadata.items():
        if not path.startswith('Config/Level/Mission/') or not Path(path).name.startswith('MissionInfo_') or not isinstance(obj, dict):
            continue
        for i, row in enumerate(obj.get('SubMissionList', [])):
            if not isinstance(row, dict):
                continue
            target, owner = row.get('MissionJsonPath'), row.get('MainMissionID', obj.get('MainMissionID'))
            if type(owner) is not int or owner <= 0 or not isinstance(target, str) or target not in metadata:
                continue
            path_pointer = f'/SubMissionList/{i}/MissionJsonPath'
            owner_pointer = f'/SubMissionList/{i}/MainMissionID' if 'MainMissionID' in row else '/MainMissionID'
            main_seeds[path].append({'kind': 'EXPLICIT_MAIN_MISSION_ID', 'source': path,
                'sourceSha256': hashes[path], 'pointer': owner_pointer, 'missionId': owner,
                'missionJsonPathPointer': path_pointer, 'missionJsonPath': target})
    conflicting_sources = {r['source'] for r in owner_conflicts}
    unregistered_owners = []

    def owners(source):
        found = []
        queue = deque([(source, [], {source})])
        while queue:
            path, chain, seen = queue.popleft()
            if path in conflicting_sources:
                continue
            if path in seeds:
                found.extend({'missionId': seed['missionId'], 'ownershipSeed': seed,
                              'chain': list(reversed(chain))} for seed in seeds[path])
                continue
            if path in main_seeds and chain:
                first = chain[-1]
                for seed in main_seeds[path]:
                    if first['kind'] != 'EXPLICIT_JSON_PATH' or first['pointer'] != seed['missionJsonPathPointer'] or first['target'] != seed['missionJsonPath']:
                        continue
                    proof = {'missionId': seed['missionId'], 'ownershipSeed': seed, 'chain': list(reversed(chain))}
                    if 'quest-' + str(seed['missionId']) not in registered:
                        if proof not in unregistered_owners:
                            unregistered_owners.append(proof)
                    else:
                        found.append(proof)
                continue
            if len(chain) >= 12:
                continue
            for edge in reverse.get(path, []):
                if edge['source'] in seen:
                    continue
                queue.append((edge['source'], chain + [edge], seen | {edge['source']}))
        return sorted(found, key=lambda r: r['ownershipSeed']['kind'] != 'EXPLICIT_RUNTIME_OWNERMAINMISSIONID')

    videos = defaultdict(list)
    for index, row in enumerate(video_config):
        if type(row.get('VideoID')) is int:
            videos[row['VideoID']].append((index, row))
    missions = defaultdict(list)
    exclusions = []
    site_count = 0
    for source, data in metadata.items():
        if not source.startswith(('Config/', 'Story/')):
            continue
        for task, pointer in helper.objects(data):
            if task.get('$type') != 'RPG.GameCore.PlayVideo':
                continue
            video_id = task.get('VideoID')
            candidates = videos.get(video_id, [])
            override = task.get('OverrideCaptionPath')
            caption_path = override or (candidates[0][1].get('CaptionPath') if len(candidates) == 1 else None)
            if caption_path not in fixtures:
                continue
            site_count += 1
            base = {'source': source, 'pointer': pointer, 'captionPath': caption_path, 'videoId': video_id}
            if len(candidates) != 1:
                exclusions.append(dict(base, reason='VIDEOID_MISSING_OR_AMBIGUOUS'))
                continue
            if missing_packs:
                exclusions.append(dict(base, reason='GLOBAL_CAPTION_IDENTITY_UNVERIFIED_MISSING_PACKS'))
                continue
            if caption_path not in unique:
                exclusions.append(dict(base, reason='CAPTION_WHOLE_RECORD_NOT_UNIQUE_OR_UNMATCHED'))
                continue
            ownership = owners(source)
            if not ownership:
                exclusions.append(dict(base, reason='NO_EXPLICIT_NONCONFLICTING_REGISTERED_OWNER'))
                continue
            caption = unique[caption_path]
            absent = [str(r['hash']) for r in caption['rows'] if r['hash'] not in textmap or not textmap[r['hash']]['raw']]
            if absent:
                exclusions.append(dict(base, reason='KOREAN_CAPTION_HASH_UNAVAILABLE', hashes=absent))
                continue
            video_index, video_row = candidates[0]
            reference = {'kind': 'EXPLICIT_OVERRIDE_CAPTION_PATH' if override else 'EXACT_VIDEOID_CAPTIONPATH_FK',
                         'source': source, 'sourceSha256': hashes[source], 'pointer': pointer + ('/OverrideCaptionPath' if override else '/VideoID'),
                         'videoId': video_id, 'tableSource': 'ExcelOutput/VideoConfig.json', 'tableSha256': video_sha,
                         'idPointer': f'/{video_index}/VideoID', 'videoPathPointer': f'/{video_index}/VideoPath',
                         'target': caption_path}
            if override:
                reference['videoIdPointer'] = pointer + '/VideoID'
                reference['defaultCaptionPath'] = video_row.get('CaptionPath')
            else:
                reference['captionPathPointer'] = f'/{video_index}/CaptionPath'
            rows = []
            for row in caption['rows']:
                original = textmap[row['hash']]
                caption_source = {k: v for k, v in caption.items() if k != 'rows'}
                caption_source.update({'captionPath': caption_path, 'rowIndex': row['index'], 'rowOffset': row['offset'],
                                       'rowEnd': row['end'], 'absoluteOffset': caption['entryOffset'] + row['offset'],
                                       'legacy': row['legacy'], 'identityStatus': 'EXACT_ALL_FIELDS_BINARY32_UNIQUE_WHOLE_RECORD'})
                rows.append({'label': '영상 자막', 'hash': str(row['hash']), 'text': original['raw'], 'raw': original['raw'],
                             'startTime': row['startTime'], 'endTime': row['endTime'], 'officialCaptionSource': caption_source,
                             'officialTextMapSource': dict(text_source, rowOffset=original['offset'], rowEnd=original['end'],
                                                         absoluteOffset=offset + original['offset'], legacy=original['legacy'], hasParams=original['has_params'])})
            for chain in ownership:
                conditions = ancestors(data, pointer, source)
                for edge in chain['chain']:
                    conditions.extend(ancestors(metadata[edge['source']], edge['pointer'], edge['source']))
                anchor = 'video-caption-' + sha(json.dumps([chain['missionId'], source, pointer, caption_path], separators=(',', ':')).encode())[:20]
                scene = {'anchor': anchor, 'title': '영상 자막', 'source': source, 'sourceSha256': hashes[source],
                         'sourceUrl': metadata_url(source), 'ownership': chain, 'captionPath': caption_path,
                         'videoId': video_id, 'conditions': conditions, 'captionReference': reference, 'rows': rows,
                         'recordType': 'CUTSCENE_CAPTION', 'speakerStatus': 'UNSPECIFIED_BY_CAPTIONLIST'}
                mission = 'quest-' + str(chain['missionId'])
                if not any(s['anchor'] == anchor for s in missions[mission]):
                    missions[mission].append(scene)
    after = corpus_digest(args.site)
    if before != after:
        raise ValueError('Preserved 4.5 dialogue corpus changed during extraction')
    counts = {'missions': len(missions), 'scenes': sum(len(v) for v in missions.values()),
              'rows': sum(len(s['rows']) for scenes in missions.values() for s in scenes),
              'playbackSites': site_count, 'supportedCaptionFixtures': len(fixtures), 'unsupportedCaptionFixtures': len(unsupported),
              'wholeRecordMatchedPaths': len(matches), 'uniqueWholeRecordPaths': len(unique),
              'ambiguousWholeRecordPaths': sum(len(v) != 1 or len(v[0]['fixtureIdentityPaths']) != 1 for v in matches.values()),
              'catalogEntriesScanned': scanned, 'strictSchemaRecords': strict_records, 'missingNonLanguagePacks': len(missing_packs),
              'excludedPlaybackSites': len(exclusions), 'exclusionReasons': dict(Counter(x['reason'] for x in exclusions)),
              'playVideoTriggers': len(lookup_diagnostics), 'rejectedPlayVideoTriggers': sum(not r['accepted'] for r in lookup_diagnostics),
              'unresolvedKoreanCaptionRows': len(unresolved_korean),
              'unresolvedKoreanCaptionHashes': len({r['hash'] for r in unresolved_korean}),
              'runtimeOwnerConflicts': len(owner_conflicts)}
    result = {'schema': 'starrail-official-video-captions.v1', 'evidence': {
        'clientVersion': envelope['version'], 'officialBaseUrl': envelope['baseUrl'],
        'manifestSha256': sha(manifest), 'catalogSha256': sha(design_raw), 'packs': pack_manifest,
        'metadataRepository': METADATA_REPO, 'metadataCommit': METADATA_COMMIT, 'metadataArchiveSha256': sha(args.archive.read_bytes()),
        'preserved45Corpus': before, 'preserved45CorpusUnchanged': before == after,
        'method': 'Strict CaptionList schema/EOF; complete fixture field and IEEE binary32 identity unique across every non-language catalog entry; official Korean TextMap hash; explicit nonconflicting RuntimeGroup owner or row-scoped MissionInfo MainMissionID/MissionJsonPath and exact path/typed Performance/Video foreign keys; conditional caption playback retained.'},
        'missions': dict(missions), 'counts': counts, 'unsupportedCaptionFixtures': unsupported,
        'unresolvedKoreanCaptionRows': unresolved_korean,
        'missingOfficialPacks': missing_packs, 'excludedPlaybackSites': exclusions,
        'playVideoLookupDiagnostics': lookup_diagnostics, 'runtimeOwnerConflicts': owner_conflicts,
        'unregisteredExplicitMainMissionOwners': unregistered_owners,
        'limitations': ['영상 자막의 화자 이름은 CaptionList에 수록된 필드 범위에서 확인되지 않는다.',
                        '자막의 재생 조건과 호출 경로를 함께 수록한다. 구조의 나열 순서는 전체 임무의 실행 순서와 구분한다.']}
    if args.measure_output:
        args.measure_output.parent.mkdir(parents=True, exist_ok=True)
        args.measure_output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', 'utf8')
    if args.write:
        if missing_packs:
            raise ValueError('All non-language catalog packs are required for public output')
        for path in (args.site / 'data/official-video-captions.json', args.site / 'public/official-video-captions.json'):
            path.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), 'utf8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--official-root', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--skill', type=Path, required=True)
    parser.add_argument('--pack-dir', type=Path, action='append', default=[])
    parser.add_argument('--site', type=Path, default=SITE)
    parser.add_argument('--textmap-key', type=int, default=15229857389724683600)
    parser.add_argument('--measure-output', type=Path)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    output = build(args)
    print(json.dumps(output['counts'], ensure_ascii=False, indent=2))
