"""Independently verify official video captions against raw packs and metadata.

The builder is deliberately not imported. Existing catalog/TextMap and JSON
traversal primitives are reused; caption byte fields, ownership, playback
foreign keys, conditions and complete adoption are checked from original input.
"""
import argparse
from collections import Counter, defaultdict, deque
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
import tarfile
from urllib.parse import quote

sys.dont_write_bytecode = True
from build_mission_dialogue_supplements import objects, path_refs
from verify_official_universe_texts import at, safe

SITE = Path(__file__).resolve().parents[1]
COMMIT = '8b178dd48698e5e7b12f0cc319ddab149f2ffc5c'
REPO = 'DimbreathBot/TurnBasedGameData'
TEXTMAP_KEY = 15229857389724683600
EXPECTED = {'missions': 92, 'scenes': 133, 'rows': 727}
RUNTIME_BASELINE_SHA = 'a072f5a610357f3f78dfac8f4ee0378cce5c6df77ed0fb5294384f5ddbfe9208'
PRIMARY = {'A': ('A',), 'C': ('C',), 'D': ('D', 'DS'),
           'DS': ('DS',), 'E': ('E',), 'CG': ('CG',)}
VARIANT = {'C': ('CLD',), 'D': ('DLD', 'DSLD'), 'DS': ('DSLD',)}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def corpus(site):
    files = sorted((site / 'data/dialogues').glob('*.json'))
    files += [site / 'data/dialogue-index.json']
    manifest = [(p.relative_to(site).as_posix(), sha(p.read_bytes())) for p in files]
    return {'files': len(manifest), 'sha256': sha(json.dumps(manifest, separators=(',', ':')).encode())}


def caption_rows(raw, varint, signed):
    """Read the demonstrated fields directly, preserving row byte boundaries."""
    flags, pos = varint(raw, 0)
    check(flags == 1, 'Unsupported caption root fields')
    count, pos = varint(raw, pos)
    count = signed(count)
    check(0 <= count <= 100000 and count <= (len(raw) - pos) // 11, 'Invalid caption count')
    rows = []
    for index in range(count):
        begin = pos
        flags, pos = varint(raw, pos)
        check(flags == 13, 'Unsupported caption row fields')
        legacy, pos = varint(raw, pos)
        primary, pos = varint(raw, pos)
        check(0 <= legacy <= 0xffffffff and 0 < primary <= 0xffffffffffffffff, 'Caption hash width')
        check(pos + 8 <= len(raw), 'Caption time span truncated')
        start, end = struct.unpack_from('<ff', raw, pos)
        pos += 8
        check(all(math.isfinite(x) and x >= 0 for x in (start, end)) and start <= end,
              'Invalid caption interval')
        rows.append({'hash': primary, 'legacy': legacy, 'startTime': start,
                     'endTime': end, 'offset': begin, 'end': pos, 'index': index})
    check(pos == len(raw), 'Caption trailing bytes')
    return rows


def fixture_identity(data):
    check(isinstance(data, dict) and set(data) == {'CaptionList'} and
          isinstance(data['CaptionList'], list), 'Unsupported fixture root')
    result = []
    for row in data['CaptionList']:
        check(isinstance(row, dict) and set(row) == {'CaptionTextID', 'StartTime', 'EndTime'},
              'Unsupported fixture row fields')
        key = row['CaptionTextID']
        check(isinstance(key, dict) and set(key) == {'Hash'} and
              type(key['Hash']) is int and 0 < key['Hash'] <= 0xffffffffffffffff,
              'Unsupported fixture text hash')
        check(all(type(row[k]) in (float, int) for k in ('StartTime', 'EndTime')), 'Fixture time type')
        result.append((key['Hash'], struct.pack('<f', row['StartTime']), struct.pack('<f', row['EndTime'])))
    return tuple(result)


def row_identity(rows):
    return tuple((r['hash'], struct.pack('<f', r['startTime']), struct.pack('<f', r['endTime'])) for r in rows)


def select_performance(records, kind):
    """Typed ID lookup; PlayVideo requires a unique video row and target."""
    if kind in ('Video', 'PlayVideo'):
        preferred = [r for r in records if r['source'] == 'ExcelOutput/PerformanceVideo.json']
        alternate = [r for r in records if r['source'] == 'ExcelOutput/PerformanceVideoLD.json']
        chosen = preferred or alternate
        return (chosen, 'PLAYVIDEO_EXACT_ID_VIDEO_TABLE_CROSS_TABLE_UNIQUE') if (
            len(chosen) == 1 and len({r['target'] for r in records}) == 1) else ([], '')
    names = {'Performance' + x for x in PRIMARY.get(kind, ())}
    chosen = [r for r in records if Path(r['source']).stem in names]
    scope = 'TYPED_PRIMARY_TABLE'
    if not chosen:
        names = {'Performance' + x for x in VARIANT.get(kind, ())}
        chosen = [r for r in records if Path(r['source']).stem in names]
        scope = 'TYPED_VARIANT_TABLE'
    return (chosen, scope) if len({r['target'] for r in chosen}) == 1 else ([], '')


def conditions(data, pointer, source):
    """Verify actual ancestors, including failure branches and event callbacks."""
    result, current, traversed = [], data, []
    for token in pointer.split('/')[1:]:
        prefix = '/' + '/'.join(traversed)
        if isinstance(current, dict):
            if token in ('SuccessTaskList', 'FailedTaskList', 'FailTaskList') and isinstance(current.get('Predicate'), dict):
                result.append({'source': source, 'predicatePointer': prefix + '/Predicate',
                               'branchPointer': prefix + '/' + token, 'branch': token,
                               'predicate': current['Predicate']})
            if token == 'OnEvent' and current.get('$type'):
                event = {k: v for k, v in current.items()
                         if k in ('$type', 'CustomString', 'EventName', 'Name', 'Key')}
                result.append({'source': source, 'eventPointer': prefix,
                               'branchPointer': prefix + '/OnEvent', 'event': event})
        current = current[int(token)] if isinstance(current, list) else current[token]
        traversed.append(token)
    return result


def uint_bytes(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def artifact_check(data, site):
    """Portable proof consistency; raw-source verification remains separate."""
    safe(data)
    check(data['schema'] == 'starrail-official-video-captions.v1', 'Caption schema')
    evidence = data['evidence']
    check(evidence['clientVersion'] == 'OSPRODWin4.6.0' and evidence['metadataRepository'] == REPO and
          evidence['metadataCommit'] == COMMIT, 'Official artifact source identity')
    check(evidence['preserved45Corpus'] == corpus(site) and evidence['preserved45CorpusUnchanged'] is True,
          'Existing corpus preservation')
    supplements = json.loads((site / 'data/mission-dialogue-supplements.json').read_text('utf8'))
    known = supplements['evidence']['structureFiles']
    check(supplements['evidence']['commit'] == COMMIT and
          supplements['evidence']['archiveSha256'] == evidence['metadataArchiveSha256'], 'Metadata archive evidence')
    universe = json.loads((site / 'data/official-universe-texts.json').read_text('utf8'))['evidence']
    check(evidence['manifestSha256'] == universe['manifestSha256'] and
          evidence['catalogSha256'] == universe['catalogSha256'], 'Existing official catalog evidence')
    packs = {p['file']: p for p in evidence['packs']}
    check(len(packs) == len(evidence['packs']) == 20, 'Complete unique pack manifest')
    def digest(value):
        check(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), 'Invalid SHA-256 proof')
    for pack in packs.values():
        check(re.fullmatch(r'[0-9a-f]{32}\.bytes', pack['file']) and type(pack['size']) is int and
              pack['size'] > 0 and type(pack['entries']) is int and pack['entries'] > 0, 'Pack manifest fields')
        digest(pack['sha256'])
    catalog = {r['id']: r for r in json.loads((site / 'data/catalog.json').read_text('utf8'))}
    mission_targets = {ident: ident for ident in catalog if ident.startswith('quest-')}
    for ident in list(mission_targets):
        path = site / 'data/documents' / (ident + '.json')
        if not path.is_file():
            continue
        document = json.loads(path.read_text('utf8'))
        for alias in document.get('aliases', []):
            if alias not in document.get('missionParts', []):
                continue
            check(alias not in mission_targets or mission_targets[alias] == ident,
                  'Conflicting explicit missionParts container')
            mission_targets[alias] = ident
    metadata_hashes, captions, text_rows, anchors, coordinates = {}, {}, {}, set(), set()
    total_scenes = total_rows = 0
    def source_proof(source, value):
        check(isinstance(source, str) and source.startswith(('Config/', 'Story/', 'ExcelOutput/')) and
              source.endswith('.json'), 'Invalid metadata source path')
        digest(value)
        if source in known:
            check(value == known[source], 'Existing metadata source SHA differs')
        check(source not in metadata_hashes or metadata_hashes[source] == value, 'Conflicting metadata source SHA')
        metadata_hashes[source] = value
    for mission, scenes in data['missions'].items():
        target = mission_targets.get(mission)
        check(re.fullmatch(r'quest-[1-9][0-9]*', mission) and target in catalog and
              (site / 'data/documents' / (target + '.json')).is_file(), 'Caption mission absent from catalog/explicit missionParts')
        check(bool(scenes), 'Empty caption mission')
        for scene in scenes:
            total_scenes += 1
            check(scene['anchor'] not in anchors and re.fullmatch(r'video-caption-[0-9a-f]{20}', scene['anchor']),
                  'Duplicate/invalid caption anchor')
            anchors.add(scene['anchor'])
            check(scene['recordType'] == 'CUTSCENE_CAPTION' and scene['speakerStatus'] == 'UNSPECIFIED_BY_CAPTIONLIST',
                  'Caption attribution fields')
            check(not any(k.lower().startswith('speaker') for k in scene if k != 'speakerStatus'), 'Invented scene speaker')
            ownership = scene['ownership']
            owner, seed = ownership['missionId'], ownership['ownershipSeed']
            check(type(owner) is int and mission == 'quest-' + str(owner) and seed['missionId'] == owner,
                  'Explicit owner proof')
            if seed['kind'] == 'EXPLICIT_RUNTIME_OWNERMAINMISSIONID':
                check(seed['pointer'] == '/OwnerMainMissionID' and seed['source'].startswith(
                    ('Config/LevelOutput/RuntimeGroup/', 'Config/LevelOutput/SharedRuntimeGroup/')),
                    'Explicit runtime owner proof')
            else:
                check(seed['kind'] == 'EXPLICIT_MAIN_MISSION_ID' and seed['source'].startswith('Config/Level/Mission/') and
                    Path(seed['source']).name.startswith('MissionInfo_'), 'Explicit MissionInfo owner proof')
                check(re.fullmatch(r'/SubMissionList/[0-9]+/MissionJsonPath', seed['missionJsonPathPointer']) and
                    seed['pointer'] in ('/MainMissionID', seed['missionJsonPathPointer'].rsplit('/', 1)[0] + '/MainMissionID'),
                    'MainMission seed row scope')
                first = ownership['chain'][0] if ownership['chain'] else {}
                check(first.get('kind') == 'EXPLICIT_JSON_PATH' and first.get('source') == seed['source'] and
                    first.get('pointer') == seed['missionJsonPathPointer'] and first.get('target') == seed['missionJsonPath'],
                    'MainMission typed path scope')
            source_proof(seed['source'], seed['sourceSha256'])
            current = seed['source']
            scope_pointers = defaultdict(list)
            for edge in ownership['chain']:
                check(edge['source'] == current and edge['pointer'].startswith('/'), 'Owner chain discontinuity')
                source_proof(edge['source'], edge['sourceSha256'])
                scope_pointers[edge['source']].append(edge['pointer'])
                check(edge['target'].startswith(('Config/', 'Story/')) and edge['target'].endswith('.json'), 'Owner chain target')
                if edge['kind'] != 'EXPLICIT_JSON_PATH':
                    check(edge['kind'] == 'EXPLICIT_PERFORMANCE_LOOKUP' and edge['pointer'].endswith('/PerformanceID') and
                          type(edge['performanceId']) is int and edge['performanceId'] > 0, 'Performance owner link')
                    source_proof(edge['tableSource'], edge['tableSha256'])
                    check(re.fullmatch(r'/[0-9]+/PerformanceID', edge['idPointer']) and
                          edge['pathPointer'] == edge['idPointer'].rsplit('/', 1)[0] + '/PerformancePath', 'Performance table pointers')
                    table = Path(edge['tableSource']).stem.removeprefix('Performance')
                    if edge['performanceType'] in ('Video', 'PlayVideo'):
                        check(table in ('Video', 'VideoLD') and
                              edge['lookupScope'] == 'PLAYVIDEO_EXACT_ID_VIDEO_TABLE_CROSS_TABLE_UNIQUE', 'Typed PlayVideo proof')
                    else:
                        allowed = PRIMARY.get(edge['performanceType'], ()) if edge['lookupScope'] == 'TYPED_PRIMARY_TABLE' else (
                            VARIANT.get(edge['performanceType'], ()) if edge['lookupScope'] == 'TYPED_VARIANT_TABLE' else ())
                        check(table in allowed, 'Typed performance proof')
                current = edge['target']
            check(current == scene['source'], 'Owner chain lacks playback source')
            source_proof(scene['source'], scene['sourceSha256'])
            check(scene['sourceUrl'] == f'https://github.com/{REPO}/blob/{COMMIT}/{quote(scene["source"], safe="/")}', 'Metadata source URL')
            reference = scene['captionReference']
            check(reference['source'] == scene['source'] and reference['sourceSha256'] == scene['sourceSha256'] and
                  type(scene['videoId']) is int and scene['videoId'] > 0 and reference['videoId'] == scene['videoId'] and
                  reference['target'] == scene['captionPath'], 'Caption scene/reference consistency')
            check(scene['captionPath'].startswith('Config/CutSceneCaption/') and scene['captionPath'].endswith('.json'), 'Caption metadata path')
            check(reference['tableSource'] == 'ExcelOutput/VideoConfig.json', 'Caption foreign-key table')
            source_proof(reference['tableSource'], reference['tableSha256'])
            check(re.fullmatch(r'/[0-9]+/VideoID', reference['idPointer']) and
                  reference['videoPathPointer'] == reference['idPointer'].rsplit('/', 1)[0] + '/VideoPath', 'Video table pointers')
            task_pointer, field = reference['pointer'].rsplit('/', 1)
            check(task_pointer.startswith('/'), 'Playback source pointer')
            scope_pointers[scene['source']].append(task_pointer)
            if reference['kind'] == 'EXACT_VIDEOID_CAPTIONPATH_FK':
                check(field == 'VideoID' and reference['captionPathPointer'] ==
                      reference['idPointer'].rsplit('/', 1)[0] + '/CaptionPath' and
                      'defaultCaptionPath' not in reference and 'videoIdPointer' not in reference, 'Default caption reference')
            else:
                check(reference['kind'] == 'EXPLICIT_OVERRIDE_CAPTION_PATH' and field == 'OverrideCaptionPath' and
                      reference['videoIdPointer'] == task_pointer + '/VideoID' and 'defaultCaptionPath' in reference and
                      'captionPathPointer' not in reference, 'Override caption reference')
                check(reference['defaultCaptionPath'] is None or isinstance(reference['defaultCaptionPath'], str), 'Default path type')
            key = (owner, scene['source'], task_pointer, scene['captionPath'])
            check(key not in coordinates, 'Duplicate playback coordinate')
            coordinates.add(key)
            check(scene['anchor'] == 'video-caption-' + sha(json.dumps(list(key), separators=(',', ':')).encode())[:20], 'Caption anchor binding')
            condition_keys = set()
            for condition in scene['conditions']:
                source = condition['source']
                branch_pointer = condition['branchPointer']
                check(source in scope_pointers and any(p.startswith(branch_pointer + '/') for p in scope_pointers[source]),
                      'Condition outside playback owner path')
                coordinate = (source, branch_pointer)
                check(coordinate not in condition_keys, 'Duplicate playback condition')
                condition_keys.add(coordinate)
                if 'predicate' in condition:
                    check(set(condition) == {'source', 'predicatePointer', 'branchPointer', 'branch', 'predicate'} and
                          condition['branch'] in ('SuccessTaskList', 'FailedTaskList', 'FailTaskList') and
                          condition['predicatePointer'].endswith('/Predicate') and branch_pointer ==
                          condition['predicatePointer'].rsplit('/', 1)[0] + '/' + condition['branch'] and
                          isinstance(condition['predicate'], dict) and isinstance(condition['predicate'].get('$type'), str),
                          'Predicate condition fields/branch')
                else:
                    check(set(condition) == {'source', 'eventPointer', 'branchPointer', 'event'} and
                          branch_pointer == condition['eventPointer'] + '/OnEvent' and isinstance(condition['event'], dict) and
                          isinstance(condition['event'].get('$type'), str) and set(condition['event']).issubset(
                          {'$type', 'CustomString', 'EventName', 'Name', 'Key'}), 'Event condition fields')
            rows = scene['rows']
            check(bool(rows), 'Empty caption scene')
            previous_end = 1 + len(uint_bytes(len(rows) * 2))
            times, reconstructed, common_caption = set(), bytearray(b'\1' + uint_bytes(len(rows) * 2)), None
            for index, row in enumerate(rows):
                total_rows += 1
                check(row['label'] == '영상 자막' and isinstance(row['hash'], str) and re.fullmatch(r'[1-9][0-9]*', row['hash']) and
                      0 < int(row['hash']) <= 0xffffffffffffffff and isinstance(row['raw'], str) and row['raw'] == row['text'] and
                      bool(row['raw']), 'Caption Korean row fields')
                check(not any(k.lower().startswith('speaker') for k in row), 'Invented caption row speaker')
                start, end = row['startTime'], row['endTime']
                check(all(type(t) in (int, float) and math.isfinite(t) and t >= 0 and
                          struct.unpack('<f', struct.pack('<f', t))[0] == t for t in (start, end)) and start <= end,
                      'Invalid float32 caption times')
                interval = (start, end)
                check(interval not in times and (not times or start >= rows[index - 1]['startTime']), 'Duplicate/unsorted caption timestamps')
                times.add(interval)
                cap, text = row['officialCaptionSource'], row['officialTextMapSource']
                pack = packs.get(cap['packFile'])
                check(pack is not None and cap['packSha256'] == pack['sha256'] and
                      type(cap['entryOffset']) is int and type(cap['entryLength']) is int and cap['entryOffset'] >= 0 and
                      0 < cap['entryLength'] <= pack['size'] - cap['entryOffset'] and cap['consumedBytes'] == cap['entryLength'], 'Caption pack entry bounds')
                check(re.fullmatch(r'[1-9][0-9]*', cap['entryKey']) and 0 < int(cap['entryKey']) <= 0xffffffffffffffff,
                      'Caption entry key')
                digest(cap['entrySha256']); digest(cap['fixtureSha256'])
                check(cap['captionPath'] == cap['fixturePath'] == scene['captionPath'] and
                      cap['fixtureIdentityPaths'] == [scene['captionPath']] and cap['rowIndex'] == index and
                      cap['identityStatus'] == 'EXACT_ALL_FIELDS_BINARY32_UNIQUE_WHOLE_RECORD', 'Whole-record caption identity')
                stable = {k: v for k, v in cap.items() if k not in
                          ('rowIndex', 'rowOffset', 'rowEnd', 'absoluteOffset', 'legacy')}
                if common_caption is None:
                    common_caption = stable
                check(stable == common_caption, 'Mixed caption records in one scene')
                check(type(cap['legacy']) is int and 0 <= cap['legacy'] <= 0xffffffff, 'Caption legacy hash')
                encoded = b'\r' + uint_bytes(cap['legacy']) + uint_bytes(int(row['hash'])) + struct.pack('<ff', start, end)
                check(cap['rowOffset'] == previous_end and cap['rowEnd'] == previous_end + len(encoded) and
                      cap['absoluteOffset'] == cap['entryOffset'] + cap['rowOffset'], 'Caption exact reconstructed row span')
                previous_end = cap['rowEnd']; reconstructed.extend(encoded)
                kr, entry = universe['koreanPack'], universe['entry']
                expected = {'packFile': 'kr/' + kr['file'], 'packSha256': kr['sha256'], 'entryKey': entry['key'],
                            'entryOffset': entry['offset'], 'entryLength': entry['length'], 'entrySha256': entry['sha256'],
                            'consumedBytes': entry['length']}
                check(all(text[k] == v for k, v in expected.items()) and type(text['rowOffset']) is int and
                      type(text['rowEnd']) is int and 0 <= text['rowOffset'] < text['rowEnd'] <= entry['length'] and
                      text['absoluteOffset'] == text['entryOffset'] + text['rowOffset'] and type(text['legacy']) is int and
                      0 <= text['legacy'] <= 0xffffffff and type(text['hasParams']) is int and text['hasParams'] >= 0,
                      'Korean TextMap proof/bounds')
                identity = (row['raw'], text)
                check(row['hash'] not in text_rows or text_rows[row['hash']] == identity, 'Same Korean hash has conflicting rows')
                text_rows[row['hash']] = identity
            check(previous_end == common_caption['entryLength'] and sha(reconstructed) == common_caption['entrySha256'],
                  'Caption reconstructed complete entry SHA/EOF')
            caption_identity = (common_caption, [(r['hash'], r['startTime'], r['endTime']) for r in rows])
            check(scene['captionPath'] not in captions or captions[scene['captionPath']] == caption_identity,
                  'Same caption path has conflicting whole-record identity')
            captions[scene['captionPath']] = caption_identity
    actual = {'missions': len(data['missions']), 'scenes': total_scenes, 'rows': total_rows}
    check(actual == EXPECTED and all(data['counts'][k] == v for k, v in actual.items()), 'Caption cohort/counts')
    verify_runtime_preservation(data)
    check(data['counts']['catalogEntriesScanned'] == sum(p['entries'] for p in packs.values()) and
          data['counts']['missingNonLanguagePacks'] == 0 and data['missingOfficialPacks'] == [], 'Caption pack coverage')
    for name, values in [('unsupportedCaptionFixtures', data['unsupportedCaptionFixtures']),
                         ('unresolvedKoreanCaptionRows', data['unresolvedKoreanCaptionRows']),
                         ('excludedPlaybackSites', data['excludedPlaybackSites']),
                         ('runtimeOwnerConflicts', data['runtimeOwnerConflicts'])]:
        check(data['counts'][name] == len(values), 'Caption diagnostic counts: ' + name)
    check(data['counts']['unresolvedKoreanCaptionHashes'] == len({r['hash'] for r in data['unresolvedKoreanCaptionRows']}) and
          data['counts']['exclusionReasons'] == dict(Counter(r['reason'] for r in data['excludedPlaybackSites'])) and
          data['counts']['playVideoTriggers'] == len(data['playVideoLookupDiagnostics']) and
          data['counts']['rejectedPlayVideoTriggers'] == sum(not d['accepted'] for d in data['playVideoLookupDiagnostics']),
          'Caption exclusion/lookup counts')
    for diagnostic in data['playVideoLookupDiagnostics']:
        check(diagnostic['performanceType'] in ('PlayVideo', 'Video') and diagnostic['accepted'] is
              bool(select_performance(diagnostic['records'], diagnostic['performanceType'])[0]), 'Ambiguous PlayVideo accepted')
    # This measured branch is the initial scene that exposed lost conditional
    # captions. Preserve its exact serialized conditions in the portable gate.
    target = next(s for s in data['missions']['quest-1043710'] if s['captionPath'].endswith('CS_Chap04_Act781_2_Caption.json'))
    check(len(target['rows']) == 59 and target['captionReference']['kind'] == 'EXPLICIT_OVERRIDE_CAPTION_PATH' and
          target['captionReference']['defaultCaptionPath'].endswith('CS_Chap04_Act781_1_Caption.json') and
          any(c.get('branch') == 'FailedTaskList' and c.get('predicate') ==
              {'$type': 'RPG.GameCore.ByCurrentAudioLanguage', 'AudioLanguage': 'CN'} for c in target['conditions']) and
          any(c.get('event') == {'$type': 'RPG.GameCore.WaitGroupEvent', 'EventName': {'Value': 'EnterArea_G{GroupID}'}}
              for c in target['conditions']), '1043710 original audio/event/Override conditions')
    return data['counts']


class Originals:
    def __init__(self, args):
        self.args = args
        self.preserved = corpus(args.site)
        sys.path.insert(0, str(args.skill / 'scripts'))
        from binary import read_catalog, decode_textmap, varint, signed
        self.varint, self.signed = varint, signed
        self.manifest = (args.official_root / 'M_DesignV.bytes').read_bytes()
        check(len(self.manifest) == 66 and self.manifest[:4] == b'SRMI', 'Official manifest format')
        digest = b''.join(self.manifest[i:i + 4][::-1] for i in range(28, 44, 4)).hex()
        self.design = (args.official_root / ('DesignV_' + digest + '.bytes')).read_bytes()
        envelope = json.loads((args.official_root / 'catalog.json').read_text('utf8'))
        self.catalog = read_catalog(self.design)
        check(json.loads(json.dumps(self.catalog)) == envelope['catalog'], 'Cached catalog differs from raw')
        self.envelope = envelope
        self.packs, self.entries, self.pack_evidence = {}, {}, []
        for item in self.catalog:
            if item['language']:
                continue
            path = next((p / item['file'] for p in [args.official_root] + args.pack_dir
                         if (p / item['file']).is_file()), None)
            check(path is not None, 'Missing non-language pack: ' + item['file'])
            raw = path.read_bytes()
            check(len(raw) == item['size'] and hashlib.md5(raw).hexdigest() == Path(item['file']).stem,
                  'Official pack size/MD5: ' + item['file'])
            self.packs[item['file']] = raw
            self.pack_evidence.append({'file': item['file'], 'sha256': sha(raw),
                                       'size': len(raw), 'entries': len(item['entries'])})
            for key, size, offset in item['entries']:
                self.entries[(item['file'], str(key))] = (offset, size)
        kr = next(item for item in self.catalog if item['language'] == 'kr')
        korean = (args.official_root / 'kr' / kr['file']).read_bytes()
        check(len(korean) == kr['size'] and hashlib.md5(korean).hexdigest() == Path(kr['file']).stem,
              'Korean pack size/MD5')
        key, size, offset = next(r for r in kr['entries'] if r[0] == TEXTMAP_KEY)
        text_bytes = korean[offset:offset + size]
        text_rows = decode_textmap(text_bytes)
        self.textmap = {str(r['hash']): r for r in text_rows}
        self.text_source = {'packFile': 'kr/' + kr['file'], 'packSha256': sha(korean),
                            'entryKey': str(key), 'entryOffset': offset, 'entryLength': size,
                            'entrySha256': sha(text_bytes), 'consumedBytes': size}
        self.metadata, self.hashes, self.performances = {}, {}, defaultdict(list)
        self.fixtures, self.fixture_paths, self.unsupported = {}, defaultdict(list), []
        self.archive_sha = sha(args.archive.read_bytes())
        with tarfile.open(args.archive, 'r:gz') as archive:
            for member in archive:
                name = member.name.split('/', 1)[-1]
                if not member.isfile() or not name.endswith('.json'):
                    continue
                table = bool(re.fullmatch(r'ExcelOutput/Performance(?:A|C|D|E|DS|CG|CLD|DLD|DSLD|Video|VideoLD)\.json', name))
                caption = name.startswith('Config/CutSceneCaption/')
                if not (name.startswith(('Config/Level/', 'Story/', 'Config/LevelOutput/RuntimeGroup/',
                                         'Config/LevelOutput/SharedRuntimeGroup/')) or table or caption or
                        name == 'ExcelOutput/VideoConfig.json'):
                    continue
                raw = archive.extractfile(member).read()
                data = json.loads(raw)
                if caption:
                    try:
                        identity = fixture_identity(data)
                    except (ValueError, TypeError, KeyError, OverflowError, struct.error):
                        self.unsupported.append(name)
                        continue
                    check(name not in self.fixtures, 'Duplicate archive caption path')
                    self.fixtures[name] = {'sha256': sha(raw), 'identity': identity}
                    self.fixture_paths[identity].append(name)
                    continue
                check(name not in self.metadata, 'Duplicate archive metadata path')
                self.metadata[name], self.hashes[name] = data, sha(raw)
                if table:
                    for i, row in enumerate(data):
                        if type(row.get('PerformanceID')) is int and row.get('PerformancePath'):
                            self.performances[row['PerformanceID']].append({
                                'source': name, 'idPointer': f'/{i}/PerformanceID',
                                'pathPointer': f'/{i}/PerformancePath', 'target': row['PerformancePath']})
        self.matches, self.scanned, self.strict = defaultdict(list), 0, 0
        for (file, key), (offset, size) in self.entries.items():
            self.scanned += 1
            raw = self.packs[file][offset:offset + size]
            if len(raw) < 2 or raw[0] != 1:
                continue
            try:
                rows = caption_rows(raw, varint, signed)
            except (ValueError, struct.error):
                continue
            self.strict += 1
            identity = row_identity(rows)
            for path in self.fixture_paths.get(identity, []):
                self.matches[path].append({'packFile': file, 'packSha256': sha(self.packs[file]),
                                          'entryKey': key, 'entryOffset': offset, 'entryLength': size,
                                          'entrySha256': sha(raw), 'consumedBytes': size,
                                          'fixturePath': path, 'fixtureSha256': self.fixtures[path]['sha256'],
                                          'fixtureIdentityPaths': self.fixture_paths[identity], 'rows': rows})
        self.unique = {path: records[0] for path, records in self.matches.items()
                       if len(records) == 1 and len(records[0]['fixtureIdentityPaths']) == 1}
        self.reverse, self.seeds, self.conflicts = defaultdict(list), defaultdict(list), []
        subowners, subproofs = defaultdict(set), defaultdict(list)
        for source, data in self.metadata.items():
            if source.startswith('Config/Level/Mission/') and Path(source).name.startswith('MissionInfo_') and isinstance(data, dict):
                for i, row in enumerate(data.get('SubMissionList', [])):
                    if type(row.get('ID')) is int and type(row.get('MainMissionID')) is int:
                        subowners[row['ID']].add(row['MainMissionID'])
                        subproofs[row['ID']].append({'source': source, 'idPointer': f'/SubMissionList/{i}/ID',
                                                    'ownerPointer': f'/SubMissionList/{i}/MainMissionID',
                                                    'missionId': row['MainMissionID']})
        self.lookup_diagnostics = []
        for source, data in self.metadata.items():
            if not source.startswith(('Config/', 'Story/')):
                continue
            for target, pointer in path_refs(data):
                self.reverse[target].append({'kind': 'EXPLICIT_JSON_PATH', 'source': source,
                                             'sourceSha256': self.hashes[source], 'pointer': pointer, 'target': target})
            for task, pointer in objects(data):
                if task.get('$type') != 'RPG.GameCore.TriggerPerformance':
                    continue
                pid, kind = task.get('PerformanceID'), task.get('PerformanceType')
                records = self.performances.get(pid, [])
                chosen, scope = select_performance(records, kind)
                if kind in ('PlayVideo', 'Video'):
                    self.lookup_diagnostics.append({'source': source, 'pointer': pointer, 'performanceId': pid,
                        'performanceType': kind, 'accepted': bool(chosen), 'records': records,
                        'duplicateIdTables': {k: v for k, v in Counter(r['source'] for r in records).items() if v > 1},
                        'foreignTableRecords': [r for r in records if r['source'] not in
                                               ('ExcelOutput/PerformanceVideo.json', 'ExcelOutput/PerformanceVideoLD.json')]})
                if not chosen:
                    continue
                record = chosen[0]
                self.reverse[record['target']].append({'kind': 'EXPLICIT_PERFORMANCE_LOOKUP',
                    'source': source, 'sourceSha256': self.hashes[source], 'pointer': pointer + '/PerformanceID',
                    'performanceId': pid, 'performanceType': kind, 'lookupScope': scope,
                    'tableSource': record['source'], 'tableSha256': self.hashes[record['source']],
                    'idPointer': record['idPointer'], 'pathPointer': record['pathPointer'], 'target': record['target']})
            if not source.startswith(('Config/LevelOutput/RuntimeGroup/', 'Config/LevelOutput/SharedRuntimeGroup/')):
                continue
            if not isinstance(data, dict) or data.get('$type') != 'RPG.GameCore.RtLevelGroupInfo':
                continue
            owner, target = data.get('OwnerMainMissionID'), data.get('LevelGraph')
            if type(owner) is not int or owner <= 0 or not isinstance(target, str) or not target:
                continue
            foreign = []
            for task, pointer in objects(self.metadata.get(target, {})):
                sid = task.get('SubmissionID')
                if task.get('$type', '').endswith('.ClientFinishMission') and type(sid) is int and subowners[sid] and owner not in subowners[sid]:
                    foreign.append({'pointer': pointer + '/SubmissionID', 'submissionId': sid,
                                    'mainMissionIds': sorted(subowners[sid]), 'ownerProofs': subproofs[sid]})
            if foreign:
                self.conflicts.append({'source': source, 'ownerPointer': '/OwnerMainMissionID', 'missionId': owner,
                    'graphPointer': '/LevelGraph', 'target': target, 'conflictingFinishReferences': foreign})
            else:
                self.seeds[source].append({'kind': 'EXPLICIT_RUNTIME_OWNERMAINMISSIONID', 'source': source,
                                          'sourceSha256': self.hashes[source], 'pointer': '/OwnerMainMissionID',
                                          'missionId': owner})
        self.main_seeds = defaultdict(list)
        self.registered = {r['id'] for r in json.loads((args.site / 'data/catalog.json').read_text('utf8')) if r['id'].startswith('quest-')}
        for ident in list(self.registered):
            doc = json.loads((args.site / 'data/documents' / (ident + '.json')).read_text('utf8'))
            self.registered.update(a for a in doc.get('aliases', []) if a in doc.get('missionParts', []))
        for source, obj in self.metadata.items():
            if not source.startswith('Config/Level/Mission/') or not Path(source).name.startswith('MissionInfo_') or not isinstance(obj, dict):
                continue
            for i, row in enumerate(obj.get('SubMissionList', [])):
                if not isinstance(row, dict):
                    continue
                owner = row.get('MainMissionID', obj.get('MainMissionID'))
                target = row.get('MissionJsonPath')
                if type(owner) is not int or owner <= 0 or not isinstance(target, str) or target not in self.metadata:
                    continue
                self.main_seeds[source].append({'kind': 'EXPLICIT_MAIN_MISSION_ID', 'source': source,
                    'sourceSha256': self.hashes[source], 'pointer': f'/SubMissionList/{i}/MainMissionID' if 'MainMissionID' in row else '/MainMissionID',
                    'missionId': owner, 'missionJsonPathPointer': f'/SubMissionList/{i}/MissionJsonPath', 'missionJsonPath': target})
        self.unregistered_owners = []
        self.conflicting_sources = {r['source'] for r in self.conflicts}
        self.owner_cache = {}
        self.videos = defaultdict(list)
        for i, video in enumerate(self.metadata['ExcelOutput/VideoConfig.json']):
            if type(video.get('VideoID')) is int:
                self.videos[video['VideoID']].append((i, video))
        self.expected_scenes, self.excluded, self.playback_sites = {}, [], 0
        for source, data in self.metadata.items():
            if not source.startswith(('Config/', 'Story/')):
                continue
            for task, pointer in objects(data):
                if task.get('$type') != 'RPG.GameCore.PlayVideo':
                    continue
                candidates = self.videos.get(task.get('VideoID'), [])
                caption = task.get('OverrideCaptionPath') or (candidates[0][1].get('CaptionPath') if len(candidates) == 1 else None)
                if caption not in self.fixtures:
                    continue
                self.playback_sites += 1
                base = {'source': source, 'pointer': pointer, 'captionPath': caption, 'videoId': task.get('VideoID')}
                if len(candidates) != 1:
                    reason = 'VIDEOID_MISSING_OR_AMBIGUOUS'
                elif caption not in self.unique:
                    reason = 'CAPTION_WHOLE_RECORD_NOT_UNIQUE_OR_UNMATCHED'
                elif not self.owners(source):
                    reason = 'NO_EXPLICIT_NONCONFLICTING_REGISTERED_OWNER'
                elif any(str(r['hash']) not in self.textmap or not self.textmap[str(r['hash'])]['raw']
                         for r in self.unique[caption]['rows']):
                    reason = 'KOREAN_CAPTION_HASH_UNAVAILABLE'
                else:
                    reason = None
                if reason:
                    exclusion = dict(base, reason=reason)
                    if reason == 'KOREAN_CAPTION_HASH_UNAVAILABLE':
                        exclusion['hashes'] = [str(r['hash']) for r in self.unique[caption]['rows']
                            if str(r['hash']) not in self.textmap or not self.textmap[str(r['hash'])]['raw']]
                    self.excluded.append(exclusion)
                    continue
                for ownership in self.owners(source):
                    key = (ownership['missionId'], source, pointer, caption)
                    self.expected_scenes.setdefault(key, []).append(ownership)

    def owners(self, source):
        if source not in self.owner_cache:
            found, queue = [], deque([(source, [], {source})])
            while queue:
                target, chain, seen = queue.popleft()
                if target in self.conflicting_sources:
                    continue
                if target in self.seeds:
                    found.extend({'missionId': seed['missionId'], 'ownershipSeed': seed,
                                  'chain': list(reversed(chain))} for seed in self.seeds[target])
                    continue
                if target in self.main_seeds and chain:
                    first = chain[-1]
                    for seed in self.main_seeds[target]:
                        if first['kind'] != 'EXPLICIT_JSON_PATH' or first['pointer'] != seed['missionJsonPathPointer'] or first['target'] != seed['missionJsonPath']:
                            continue
                        proof = {'missionId': seed['missionId'], 'ownershipSeed': seed, 'chain': list(reversed(chain))}
                        if 'quest-' + str(seed['missionId']) not in self.registered:
                            if proof not in self.unregistered_owners:
                                self.unregistered_owners.append(proof)
                        else:
                            found.append(proof)
                    continue
                if len(chain) >= 12:
                    continue
                for edge in self.reverse.get(target, []):
                    if edge['source'] not in seen:
                        queue.append((edge['source'], chain + [edge], seen | {edge['source']}))
            self.owner_cache[source] = sorted(found, key=lambda r: r['ownershipSeed']['kind'] != 'EXPLICIT_RUNTIME_OWNERMAINMISSIONID')
        return self.owner_cache[source]


def verify_runtime_preservation(data):
    scenes = [s for ss in data['missions'].values() for s in ss if
        s['ownership']['ownershipSeed']['kind'] == 'EXPLICIT_RUNTIME_OWNERMAINMISSIONID']
    raw = json.dumps(sorted(scenes, key=lambda s: s['anchor']), sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    check(len(scenes) == 81 and sum(len(s['rows']) for s in scenes) == 424 and sha(raw) == RUNTIME_BASELINE_SHA,
          'Existing 81 Runtime scenes/raw/anchors/proofs changed')


def verify_scene(mission, scene, original):
    ownership = scene['ownership']
    owner = ownership['missionId']
    check(type(owner) is int and mission == 'quest-' + str(owner), 'Mission key/owner mismatch')
    reference = scene['captionReference']
    task_pointer = reference['pointer'].rsplit('/', 1)[0]
    key = (owner, scene['source'], task_pointer, scene['captionPath'])
    check(key in original.expected_scenes and ownership in original.expected_scenes[key],
          'Owner chain is not an explicit nonconflicting raw-metadata path')
    check(scene['sourceSha256'] == original.hashes[scene['source']], 'Scene source SHA')
    expected_url = f'https://github.com/{REPO}/blob/{COMMIT}/{quote(scene["source"], safe="/")}'
    check(scene['sourceUrl'] == expected_url, 'Scene source URL')
    check(scene['anchor'] == 'video-caption-' + sha(json.dumps(list(key), separators=(',', ':')).encode())[:20], 'Scene anchor')
    check(scene['recordType'] == 'CUTSCENE_CAPTION' and scene['speakerStatus'] == 'UNSPECIFIED_BY_CAPTIONLIST', 'Caption attribution')
    check(not any(k.lower().startswith('speaker') for k in scene if k != 'speakerStatus'), 'Invented scene speaker')
    task = at(original.metadata[scene['source']], task_pointer)
    check(task.get('$type') == 'RPG.GameCore.PlayVideo' and type(task['VideoID']) is int and
          task['VideoID'] == scene['videoId'], 'PlayVideo source task')
    candidates = original.videos[task['VideoID']]
    check(len(candidates) == 1, 'VideoID ambiguous')
    index, video = candidates[0]
    override = task.get('OverrideCaptionPath')
    target = override or video.get('CaptionPath')
    check(target == scene['captionPath'], 'Caption foreign-key target')
    expected_ref = {'kind': 'EXPLICIT_OVERRIDE_CAPTION_PATH' if override else 'EXACT_VIDEOID_CAPTIONPATH_FK',
        'source': scene['source'], 'sourceSha256': original.hashes[scene['source']],
        'pointer': task_pointer + ('/OverrideCaptionPath' if override else '/VideoID'), 'videoId': task['VideoID'],
        'tableSource': 'ExcelOutput/VideoConfig.json', 'tableSha256': original.hashes['ExcelOutput/VideoConfig.json'],
        'idPointer': f'/{index}/VideoID', 'videoPathPointer': f'/{index}/VideoPath', 'target': target}
    if override:
        expected_ref.update(videoIdPointer=task_pointer + '/VideoID', defaultCaptionPath=video.get('CaptionPath'))
    else:
        expected_ref['captionPathPointer'] = f'/{index}/CaptionPath'
    check(reference == expected_ref, 'Default/Override caption reference differs from raw task/table')
    expected_conditions = conditions(original.metadata[scene['source']], task_pointer, scene['source'])
    for edge in ownership['chain']:
        expected_conditions += conditions(original.metadata[edge['source']], edge['pointer'], edge['source'])
    check(scene['conditions'] == expected_conditions, 'Playback condition/branch/event omitted or changed')
    caption = original.unique[target]
    check(len(scene['rows']) == len(caption['rows']), 'Caption scene has missing/extra rows')
    for row, source in zip(scene['rows'], caption['rows']):
        check(not any(k.lower().startswith('speaker') for k in row), 'Invented per-row speaker')
        check(row['label'] == '영상 자막' and type(row['hash']) is str and row['hash'] == str(source['hash']), 'Caption row hash/type')
        check(all(type(row[k]) in (int, float) and row[k] == source[k] for k in ('startTime', 'endTime')), 'Caption float32 time')
        korean = original.textmap[row['hash']]
        check(row['raw'] == row['text'] == korean['raw'] and bool(row['raw']), 'Korean TextMap original changed')
        expected_caption = {k: v for k, v in caption.items() if k != 'rows'}
        expected_caption.update(captionPath=target, rowIndex=source['index'], rowOffset=source['offset'],
            rowEnd=source['end'], absoluteOffset=caption['entryOffset'] + source['offset'], legacy=source['legacy'],
            identityStatus='EXACT_ALL_FIELDS_BINARY32_UNIQUE_WHOLE_RECORD')
        check(row['officialCaptionSource'] == expected_caption, 'Caption raw span/pack/fixture evidence changed')
        expected_text = dict(original.text_source, rowOffset=korean['offset'], rowEnd=korean['end'],
            absoluteOffset=original.text_source['entryOffset'] + korean['offset'], legacy=korean['legacy'], hasParams=korean['has_params'])
        check(row['officialTextMapSource'] == expected_text, 'TextMap raw span/hash/params evidence changed')
    return key


def verify_payload(data, original):
    safe(data)
    check(data['schema'] == 'starrail-official-video-captions.v1', 'Caption schema')
    evidence = data['evidence']
    check(evidence['clientVersion'] == original.envelope['version'] == 'OSPRODWin4.6.0', 'Official version')
    check(evidence['officialBaseUrl'] == original.envelope['baseUrl'], 'Official source URL')
    check(evidence['manifestSha256'] == sha(original.manifest) and evidence['catalogSha256'] == sha(original.design), 'Manifest/catalog SHA')
    check(evidence['packs'] == original.pack_evidence, 'Complete whole-pack SHA evidence')
    check(evidence['metadataRepository'] == REPO and evidence['metadataCommit'] == COMMIT and
          evidence['metadataArchiveSha256'] == original.archive_sha, 'Metadata source identity')
    check(evidence['preserved45Corpus'] == original.preserved and evidence['preserved45CorpusUnchanged'] is True, 'Existing corpus changed')
    actual, scenes, rows = set(), 0, 0
    for mission, entries in data['missions'].items():
        check(bool(entries), 'Empty mission capsule')
        for scene in entries:
            key = verify_scene(mission, scene, original)
            check(key not in actual, 'Duplicate adopted caption scene')
            actual.add(key)
            scenes += 1
            rows += len(scene['rows'])
    check(actual == set(original.expected_scenes), 'Complete raw-source adoption differs')
    check(data['unregisteredExplicitMainMissionOwners'] == original.unregistered_owners, 'Unregistered explicit owners differ')
    counts = {'missions': len(data['missions']), 'scenes': scenes, 'rows': rows}
    check(counts == EXPECTED, 'Verified 4.6 caption cohort changed')
    verify_runtime_preservation(data)
    unresolved = [{'captionPath': path, 'captionRowIndex': row['index'], 'hash': str(row['hash']),
                   'startTime': row['startTime'], 'endTime': row['endTime'], 'entryKey': caption['entryKey']}
                  for path, caption in original.unique.items() for row in caption['rows']
                  if str(row['hash']) not in original.textmap or not original.textmap[str(row['hash'])]['raw']]
    counts.update(playbackSites=original.playback_sites, supportedCaptionFixtures=len(original.fixtures),
        unsupportedCaptionFixtures=len(original.unsupported), wholeRecordMatchedPaths=len(original.matches),
        uniqueWholeRecordPaths=len(original.unique),
        ambiguousWholeRecordPaths=sum(len(v) != 1 or len(v[0]['fixtureIdentityPaths']) != 1 for v in original.matches.values()),
        catalogEntriesScanned=original.scanned, strictSchemaRecords=original.strict, missingNonLanguagePacks=0,
        excludedPlaybackSites=len(original.excluded), exclusionReasons=dict(Counter(x['reason'] for x in original.excluded)),
        playVideoTriggers=len(original.lookup_diagnostics), rejectedPlayVideoTriggers=sum(not x['accepted'] for x in original.lookup_diagnostics),
        unresolvedKoreanCaptionRows=len(unresolved), unresolvedKoreanCaptionHashes=len({r['hash'] for r in unresolved}),
        runtimeOwnerConflicts=len(original.conflicts))
    check(data['counts'] == counts, 'Measured caption/exclusion counts')
    check(data['missingOfficialPacks'] == [], 'Missing pack disclosure')
    check({r['path'] for r in data['unsupportedCaptionFixtures']} == set(original.unsupported), 'Unsupported fixture disclosure')
    check(data['unresolvedKoreanCaptionRows'] == unresolved, 'Unavailable Korean hashes disclosure')
    check(data['excludedPlaybackSites'] == original.excluded, 'Unowned/ambiguous playback exclusion disclosure')
    check(data['playVideoLookupDiagnostics'] == original.lookup_diagnostics, 'PlayVideo typed lookup/ambiguity disclosure')
    check(data['runtimeOwnerConflicts'] == original.conflicts, 'Runtime owner conflict disclosure')
    return counts


def self_test(data, original):
    checks = []
    def rejected(label, operation):
        try:
            operation()
        except (ValueError, KeyError, IndexError, TypeError, struct.error, OverflowError):
            checks.append(label)
            return
        raise ValueError('Accepted contamination: ' + label)
    mission, entries = next(iter(data['missions'].items()))
    scene = entries[0]
    def changed(label, mutate, selected=scene, owner=mission):
        edited = deepcopy(selected)
        mutate(edited)
        rejected(label, lambda: verify_scene(owner, edited, original))
    changed('WRONG_RUNTIME_OWNER', lambda s: s['ownership'].update(missionId=s['ownership']['missionId'] + 1))
    changed('DIRECTORY_ONLY_OWNER', lambda s: s['ownership'].update(ownershipSeed={'kind': 'MISSION_DIRECTORY'}))
    main_owner, main_scene = next((m, s) for m, ss in data['missions'].items() for s in ss
        if s['ownership']['ownershipSeed']['kind'] == 'EXPLICIT_MAIN_MISSION_ID')
    changed('MAINMISSION_WRONG_SEED_ID', lambda s: s['ownership']['ownershipSeed'].update(missionId=1), main_scene, main_owner)
    changed('MAINMISSION_FOREIGN_ROW_OWNER', lambda s: s['ownership']['ownershipSeed'].update(pointer='/SubMissionList/999/MainMissionID'), main_scene, main_owner)
    changed('MAINMISSION_REMOVED_PATH_EDGE', lambda s: s['ownership']['chain'].pop(0), main_scene, main_owner)
    changed('MAINMISSION_FOREIGN_MISSION_PATH', lambda s: s['ownership']['ownershipSeed'].update(missionJsonPath='Story/foreign.json'), main_scene, main_owner)
    changed('MAINMISSION_WRONG_VIDEO_TYPE', lambda s: next(e for e in s['ownership']['chain'] if e['kind'] == 'EXPLICIT_PERFORMANCE_LOOKUP').update(performanceType='D'), main_scene, main_owner)
    changed('CAPTION_HASH', lambda s: s['rows'][0].update(hash='1'))
    changed('KOREAN_RAW', lambda s: s['rows'][0].update(raw=s['rows'][0]['raw'] + 'x'))
    changed('FLOAT32_TIME', lambda s: s['rows'][0].update(startTime=s['rows'][0]['startTime'] + 0.000001))
    changed('CAPTION_ROW_SPAN', lambda s: s['rows'][0]['officialCaptionSource'].update(rowOffset=0))
    changed('CAPTION_ENTRY_SPAN', lambda s: s['rows'][0]['officialCaptionSource'].update(entryOffset=0))
    changed('WHOLE_PACK_SHA', lambda s: s['rows'][0]['officialCaptionSource'].update(packSha256='0' * 64))
    changed('TEXTMAP_ROW_SPAN', lambda s: s['rows'][0]['officialTextMapSource'].update(rowEnd=0))
    changed('PER_ROW_SPEAKER_INVENTION', lambda s: s['rows'][0].update(speaker='invented'))
    changed('DEFAULT_AS_OVERRIDE', lambda s: s['captionReference'].update(kind='EXPLICIT_OVERRIDE_CAPTION_PATH'))
    conditional = next((m, s) for m, ss in data['missions'].items() for s in ss if s['conditions'])
    changed('OMITTED_PLAYBACK_CONDITION', lambda s: s.update(conditions=[]), conditional[1], conditional[0])
    failed = next((m, s) for m, ss in data['missions'].items() for s in ss
                  if any(c.get('branch') in ('FailedTaskList', 'FailTaskList') for c in s['conditions']))
    changed('FAILED_AUDIO_BRANCH_AS_SUCCESS', lambda s: next(c for c in s['conditions'] if c.get('branch') in
            ('FailedTaskList', 'FailTaskList')).update(branch='SuccessTaskList'), failed[1], failed[0])
    override = next((m, s) for m, ss in data['missions'].items() for s in ss
                    if s['captionReference']['kind'] == 'EXPLICIT_OVERRIDE_CAPTION_PATH')
    changed('OVERRIDE_DEFAULT_PATH_CONFLATION', lambda s: s['captionReference'].update(
        defaultCaptionPath=s['captionPath']), override[1], override[0])
    missing = deepcopy(data)
    removed = missing['missions'][mission].pop(0)
    if not missing['missions'][mission]:
        del missing['missions'][mission]
    missing['counts'].update(missions=len(missing['missions']), scenes=data['counts']['scenes'] - 1,
                             rows=data['counts']['rows'] - len(removed['rows']))
    rejected('OMITTED_SCENE_WITH_ADJUSTED_COUNTS', lambda: verify_payload(missing, original))
    record = {'source': 'ExcelOutput/PerformanceVideo.json', 'target': 'Story/example.json'}
    for label, records, kind in [
        ('DUPLICATE_VIDEO_ID', [record, record], 'PlayVideo'),
        ('FOREIGN_TABLE_ONLY', [dict(record, source='ExcelOutput/PerformanceC.json')], 'PlayVideo'),
        ('CROSS_TABLE_TARGET_CONFLICT', [record, dict(record, source='ExcelOutput/PerformanceC.json', target='Story/other.json')], 'PlayVideo'),
        ('VIDEO_LD_TARGET_CONFLICT', [record, dict(record, source='ExcelOutput/PerformanceVideoLD.json', target='Story/other.json')], 'PlayVideo'),
        ('WRONG_PERFORMANCE_TYPE', [record], 'D')]:
        rejected(label, lambda rs=records, k=kind: check(bool(select_performance(rs, k)[0]), 'Typed video lookup rejected'))
    caption = original.unique[scene['captionPath']]
    start, length = caption['entryOffset'], caption['entryLength']
    raw = original.packs[caption['packFile']][start:start + length]
    for label, invalid in [('UNKNOWN_ROOT', bytes([3]) + raw[1:]),
                           ('TRUNCATED_CAPTION', raw[:-1]), ('CAPTION_TRAILING_BYTES', raw + b'\0')]:
        rejected(label, lambda b=invalid: caption_rows(b, original.varint, original.signed))
    return checks


def artifact_self_test(data, site):
    rejected = []
    mission = next(iter(data['missions']))
    def contamination(label, mutation):
        edited = deepcopy(data)
        mutation(edited)
        try:
            artifact_check(edited, site)
        except (ValueError, KeyError, IndexError, TypeError, struct.error, OverflowError, StopIteration):
            rejected.append(label)
            return
        raise ValueError('Portable QA accepted contamination: ' + label)
    def first(d):
        return d['missions'][mission][0]
    contamination('ARTIFACT_WRONG_OWNER', lambda d: first(d)['ownership']['ownershipSeed'].update(missionId=1))
    contamination('ARTIFACT_WRONG_HASH', lambda d: first(d)['rows'][0].update(hash='1'))
    contamination('ARTIFACT_WRONG_SPAN', lambda d: first(d)['rows'][0]['officialCaptionSource'].update(rowEnd=0))
    contamination('ARTIFACT_TIME_TYPE', lambda d: first(d)['rows'][0].update(startTime='1'))
    contamination('ARTIFACT_PACK_SHA', lambda d: first(d)['rows'][0]['officialCaptionSource'].update(packSha256='0' * 64))
    contamination('ARTIFACT_DIRECTORY_OWNER', lambda d: first(d)['ownership']['ownershipSeed'].update(kind='MISSION_DIRECTORY'))
    main_owner, main_index = next((m, i) for m, ss in data['missions'].items() for i, s in enumerate(ss)
        if s['ownership']['ownershipSeed']['kind'] == 'EXPLICIT_MAIN_MISSION_ID')
    def main_scene(d):
        return d['missions'][main_owner][main_index]
    contamination('ARTIFACT_MAINMISSION_FOREIGN_ROW', lambda d: main_scene(d)['ownership']['ownershipSeed'].update(pointer='/SubMissionList/999/MainMissionID'))
    contamination('ARTIFACT_MAINMISSION_REMOVED_PATH', lambda d: main_scene(d)['ownership']['chain'].pop(0))
    contamination('ARTIFACT_MAINMISSION_WRONG_SEED', lambda d: main_scene(d)['ownership']['ownershipSeed'].update(missionId=1))
    contamination('ARTIFACT_MAINMISSION_FOREIGN_PATH', lambda d: main_scene(d)['ownership']['ownershipSeed'].update(missionJsonPath='Story/foreign.json'))
    contamination('ARTIFACT_MAINMISSION_WRONG_VIDEO_TYPE', lambda d: next(e for e in main_scene(d)['ownership']['chain'] if e['kind'] == 'EXPLICIT_PERFORMANCE_LOOKUP').update(performanceType='D'))
    contamination('ARTIFACT_SPEAKER', lambda d: first(d)['rows'][0].update(speaker='invented'))
    contamination('ARTIFACT_DUPLICATE_ANCHOR', lambda d: d['missions'][mission].append(deepcopy(first(d))))
    def duplicate_time(d):
        selected = next(s for ss in d['missions'].values() for s in ss if len(s['rows']) > 1)
        selected['rows'][1].update(startTime=selected['rows'][0]['startTime'], endTime=selected['rows'][0]['endTime'])
    contamination('ARTIFACT_DUPLICATE_TIMESTAMPS', duplicate_time)
    def lost_audio(d):
        selected = next(s for s in d['missions']['quest-1043710'] if s['captionPath'].endswith('CS_Chap04_Act781_2_Caption.json'))
        selected['conditions'] = []
    contamination('ARTIFACT_LOST_AUDIO_EVENT_CONDITIONS', lost_audio)
    return rejected


def main(args):
    path = args.input or args.site / 'data/official-video-captions.json'
    raw = path.read_bytes()
    if args.input is None:
        check(raw == (args.site / 'public/official-video-captions.json').read_bytes(), 'Public/data caption artifact differs')
    data = json.loads(raw)
    if args.artifact_only:
        check(not (args.official_root or args.archive or args.skill or args.pack_dir),
              'Artifact-only QA does not accept external raw inputs; use deep mode for them')
        counts = artifact_check(data, args.site)
        mutations = artifact_self_test(data, args.site) if args.self_test else []
        preserved, source_packs = data['evidence']['preserved45Corpus'], 0
        limitation = 'Portable artifact/proof consistency only; original packs and metadata were not reread.'
    else:
        check(args.official_root and args.archive and args.skill,
              'Deep QA requires --official-root, --archive and --skill; portable gate must explicitly use --artifact-only')
        original = Originals(args)
        counts = verify_payload(data, original)
        mutations = self_test(data, original) if args.self_test else []
        check(corpus(args.site) == original.preserved, 'Existing corpus changed during QA')
        preserved, source_packs = original.preserved, len(original.packs)
        limitation = 'Byte, metadata ownership, condition and whole-cohort verification; browser rendering is separate.'
    result = {'status': 'PASS', 'deepOriginalBytes': not args.artifact_only, 'artifactOnly': args.artifact_only,
              'artifactSha256': sha(raw), 'counts': counts, 'sourcePacks': source_packs, 'preserved45Corpus': preserved,
              'mutationRejections': len(mutations), 'mutations': mutations,
              'limitations': limitation}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', 'utf8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=SITE)
    parser.add_argument('--official-root', type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--skill', type=Path)
    parser.add_argument('--pack-dir', type=Path, action='append', default=[])
    parser.add_argument('--input', type=Path, help='Explicit measured artifact; default also checks public copy')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--artifact-only', action='store_true', help='Portable committed-artifact consistency; does not claim raw-source verification')
    main(parser.parse_args())
