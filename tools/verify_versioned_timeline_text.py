"""Verify the closed one-record edition comparison without executing producers.

source_check(repo, data) returns the validated records. Its default scope is the
exact repository originals and frozen source proofs. Actual byte/owner replays
are explicit options, with the cached caller edition boundary always retained.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import base64
from collections import Counter
from copy import deepcopy
import hashlib
import gzip
from publication_contract_reader import HTMLParser
import json
from pathlib import Path
import re
import tarfile
from urllib.parse import unquote

SITE = Path(__file__).resolve().parents[1]
CANONICAL = '91e1731e1a354b70400f4e1e43ff6485d81352e28e76fe6de9d07bd10eea8557'
CAPSULE = 'a2e0af520af9587e934081c887d700036b84df4d40f02149577f6cdd4d0c99dd'
CALLER_REPLAY = 'db81af44188bf73ef502e70d35b151684f772e90eb9cfec956b7127fc8eb6714'
TID = 202196417


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())


def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def exact_identifiers(value):
    if isinstance(value, dict):
        return {k: exact_identifiers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [exact_identifiers(v) for v in value]
    return str(value) if type(value) is int and abs(value) > 2**53 - 1 else value


def at(value, pointer):
    require(pointer.startswith('/'), 'JSON pointer must be absolute within its document')
    for part in pointer.split('/')[1:]:
        key = part.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def relative(value):
    require(isinstance(value, str) and value and not re.search(r'^[a-z]+:|^/|\\', value, re.I)
            and all(part not in ('.', '..', '') for part in value.split('/')), 'Private or unsafe source path')
    return value


def public_safe(value, key=''):
    if isinstance(value, dict):
        require(not any(k in value for k in ('privateReplay', 'packPath', 'objectFolder', 'rawAudit', 'nativePackPath')), 'Private replay field in public payload')
        for k, item in value.items():
            public_safe(item, k)
    elif isinstance(value, list):
        for item in value:
            public_safe(item, key)
    elif isinstance(value, str):
        require(not re.search(r'(?:[A-Z]:[/\\]|file://|\\\\)', value, re.I), 'Private absolute path in public payload')
        if key in ('pathID', 'm_PathID', 'hash', 'speaker_hash', 'Hash', 'entry_hash'):
            require(re.fullmatch(r'-?[0-9]+', value) is not None, 'Identifier string is not precise')
    elif type(value) is int:
        require(abs(value) <= 2**53 - 1, 'Public integer loses browser precision')


def source_row(repo, edition):
    path = repo / relative(edition['sourceFile'])
    raw = path.read_bytes()
    require(sha(raw) == edition['sourceFileSha256'], 'Edition source file SHA differs')
    require(at(json.loads(raw), edition['pointer']) == edition['row'], 'Edition source pointer/body differs')
    require(edition['row']['talk_id'] == TID, 'Edition TalkSentenceID differs')
    return json.loads(raw)


def source_check(repo, data):
    """Return the one validated VERSION_COMPARISON_REFERENCE record.

    Inverse consumers use record.url + previous.anchor for the preserved source;
    this reference identifies a comparison, never the old body's runtime use.
    """
    repo = Path(repo)
    public_safe(data)
    require(data['schema'] == 'starrail-versioned-timeline-text.v1', 'Comparison schema differs')
    require(data['counts'] == {'records': 1, 'staticOriginals': 2} and len(data['records']) == 1, 'Closed comparison count differs')
    record, = data['records']
    require(record['id'] == 'versioned-talk-202196417' and record['talkId'] == TID
            and record['role'] == 'VERSION_COMPARISON_REFERENCE', 'Comparison identifier/role differs')
    require(record['url'] == '대화/판본-202196417.html', 'Comparison return URL differs')
    old, current, proof = record['previous'], record['current'], record['proof']
    require(old['anchor'] == 'talk-202196417-previous' and current['anchor'] == 'talk-202196417-current', 'Edition anchors differ')
    require(old['raw'] is None and old['speakerRaw'] is None and old['rawStatus']['raw'] is None
            and old['rawStatus']['status'] == 'UNVERIFIED_PRESERVED_RAW_STRING_UNAVAILABLE'
            and old['observedReleaseVersion'] == 'UNVERIFIED', 'Preserved raw/version boundary weakened')
    require(old['editionLabel'] == '보존 한국어 원문 · 관찰 판본 미확인'
            and current['editionLabel'] == '공식 한국어 원문 · 4.6.0', 'Edition labels differ')
    source_row(repo, old)
    official = source_row(repo, current)
    require(official['evidence'] == current['officialEvidence'], 'Current official source evidence differs')
    require(current['row']['previous']['text'] == old['row']['text']
            and current['row']['previousSource']['sourceFileSha256'] == old['sourceFileSha256'], 'Previous/current exact row bridge differs')
    require(old['row']['text'] != current['row']['text'] and current['row']['changeKind'] == 'changed'
            and current['row']['changes'] == ['READABLE_TEXT_CHANGED'], 'Readable edition difference absent')
    for key in ('hash', 'speaker_hash', 'voice'):
        require(old['row'][key] == current['row'][key], 'Shared edition identifier differs: ' + key)
    native, scene = proof['nativeCaller'], proof['scene']
    require(record['source'] == scene['source'] == scene['container']['key'], 'Virtual scene source identity differs')
    require(scene['nativeIDUseRole'] == 'SPOKEN' and scene['object']['class'] == 'PlaySimpleTalkClip'
            and scene['track']['class'] == 'PlaySimpleTalkTrack' and scene['root']['class'] == 'TimelineAsset'
            and scene['idField'] == {'field': 'PlaySimpleTalkClip.Config.TalkSentenceID', 'span': [60, 64], 'value': TID}, 'Typed native Talk domain differs')
    require(proof['verification']['nativeFullEOFObjects'] == {'root': 1, 'tracks': 3, 'typedTalkClip': 1}
            and native['consumedBytes'] == native['catalogMatch']['length'] == 1669
            and native['status'] == 'WHOLE_NATIVE_EOF_AND_INDEPENDENT_PLAYTIMELINE_TERMINAL_PASS', 'Whole native EOF boundary differs')
    require(native['editionStatus'] == data['evidence']['callerEditionStatus']
            == 'CACHED_SNAPSHOT_CURRENT_INSTALLED_EDITION_UNVERIFIED'
            and data['evidence']['runtimePlaybackStatus'] == data['evidence']['previousRawStatus'] == 'UNVERIFIED', 'Edition/runtime uncertainty weakened')
    require(native['source'] == proof['publicCaller']['source']
            and native['pointer'] == proof['publicCaller']['pointer']
            and 'assets/asbres/' + proof['publicCaller']['snapshotTask']['TimelineName'].lower() == record['source']
            and proof['publicCaller']['snapshotTask']['$type'] == 'RPG.GameCore.PlayTimeline', 'Typed caller scene bridge differs')
    require(proof['owner']['mission'] == 'quest-2021901', 'Owner mission differs')
    membership = proof['owner']['ownerChain'][0]
    raw = (repo / relative(membership['membershipSource'])).read_bytes()
    require(sha(raw) == membership['membershipSha256'] and at(json.loads(raw), membership['membershipPointer']) == proof['owner']['mission'], 'Exact mission membership source differs')
    require(data['evidence']['capsuleSha256'] == CAPSULE and data['evidence']['nativeCallerReplaySha256'] == CALLER_REPLAY, 'Frozen proof identity differs')
    require(canonical(data) == CANONICAL, 'Closed public comparison payload changed')
    return data['records']


def capsule_check(record, path):
    raw = Path(path).read_bytes()
    require(sha(raw) == CAPSULE, 'Frozen private capsule SHA differs')
    capsule = json.loads(raw)
    for key in ('scene', 'owner', 'nativeCaller', 'publicCaller', 'verification'):
        require(record['proof'][key] == exact_identifiers(capsule[key]), 'Capsule proof projection differs: ' + key)
    for key in ('previous', 'current'):
        projected = dict(record[key])
        projected.pop('anchor')
        projected.pop('editionLabel')
        require(projected == capsule[key], 'Capsule edition projection differs: ' + key)
    return capsule


def native_codec(record):
    import verify_fresh_native_timeline as native
    require(sha(Path(native.__file__).read_bytes()) == record['proof']['verification']['verifierSha256'],
            'Independent native verifier source differs from frozen capsule')
    return native


def audit_cab(record, capsule, game):
    # This module is an independent stdlib verifier; no producer is imported.
    native = native_codec(record)
    p, scene = capsule['privateReplay'], record['proof']['scene']
    receipt = p['sourceReceipt']
    block = Path(game) / 'StreamingAssets/Asb/Windows' / receipt['blockFile']
    require(native.file_sha(block) == receipt['blockSha256'], 'Actual current installed block SHA differs')
    raw = Path(receipt['inventory']).read_bytes()
    require(sha(raw) == receipt['inventorySha256'], 'Actual object inventory SHA differs')
    inv = json.loads(raw)
    cab = next(x for x in inv['cabs'] if x['name'] == receipt['cabName'])
    folder = Path(receipt['objectFolder'])
    body, obj = native.raw_object(folder, cab['name'], cab, scene['root'])
    root = native.decode_root(body, obj)
    require(root['eof'] == p['rootEOF'] and root['fields'] == native.normalize_fields(p['rootFields']), 'Actual root whole EOF/fields differ')
    body, obj = native.raw_object(folder, cab['name'], cab, scene['object'])
    asset = native.decode_asset(body, obj, scene['object']['class'])
    require(asset['eof'] == p['assetEOF'] and asset['fields'] == native.normalize_fields(p['assetFields'])
            and scene['idField'] in asset['fields'], 'Actual clip whole EOF/Talk field differs')
    tracks = {}
    for pathid in scene['parentRoute'][:-1]:
        proof = p['trackProofs'].get(pathid)
        if proof is None:
            obj = next(x for x in cab['objects'] if str(x['pathID']) == pathid)
            mono = next(x for x in cab['objects'] if x['pathID'] == obj['scriptPointer']['m_PathID'])
            require(mono['script']['m_ClassName'] == 'GroupTrack', 'Actual parent native class differs')
            proof = {'object': dict(obj, **{'class': 'GroupTrack'})}
        body, obj = native.raw_object(folder, cab['name'], cab, proof['object'])
        tracks[pathid] = native.decode_track(body, obj, proof['object']['class'])
    for child, parent in zip(scene['parentRoute'], scene['parentRoute'][1:]):
        require(tracks[child]['parent'] == {'fileID': 0, 'pathID': parent}, 'Actual track parent PPtr differs')
        siblings = root['tracks'] if parent == scene['parentRoute'][-1] else tracks[parent]['children']
        require({'fileID': 0, 'pathID': child} in siblings, 'Actual reciprocal child PPtr absent')
    clip = tracks[scene['track']['pathID']]['clips'][scene['trackClipIndex']]
    require(clip['m_Asset'] == {'fileID': 0, 'pathID': scene['object']['pathID']}
            and clip['m_Start'] == scene['start'] and clip['m_Duration'] == scene['duration'], 'Actual typed track clip/timing differs')
    return {'actualCurrentBlocks': 1, 'wholeEOFRoots': 1, 'wholeEOFTracks': 3, 'wholeEOFTalkClips': 1}


def audit_caller(record, capsule, replay_path):
    native = native_codec(record)
    raw = Path(replay_path).read_bytes()
    require(sha(raw) == CALLER_REPLAY, 'Whole caller frozen replay SHA differs')
    p = record['proof']['nativeCaller']
    receipt, = [x for x in json.loads(raw)['results'] if x['source'] == p['source']]
    require(receipt['status'] == 'WHOLE_NATIVE_FIELDS_EOF_PASS' and receipt['bytes'] == 1669
            and receipt['sha256'] == p['entrySha256'] and receipt['trailingByteRejected'] is True,
            'Closed native caller whole EOF proof differs')
    pack = Path(capsule['privateReplay']['nativePackPath']).read_bytes()
    require(sha(pack) == p['sourcePack']['sha256'] and len(pack) == p['sourcePack']['bytes'], 'Actual cached caller pack SHA/size differs')
    match = p['catalogMatch']
    body = pack[match['offset']:match['offset'] + match['length']]
    require(len(body) == 1669 and sha(body) == p['entrySha256'], 'Actual caller entry SHA/size differs')
    spans = {x['pointer']: x for x in receipt['fieldSpans']}
    require(len(spans) == len(receipt['fieldSpans']) and spans[''] == {'pointer': '', 'start': 0, 'end': 1669}, 'Closed whole caller EOF span differs')
    for span in spans.values():
        require(0 <= span['start'] <= span['end'] <= 1669, 'Closed caller field span escapes entry')
        if span['pointer']:
            at(receipt['fields'], span['pointer'])
    require(spans[p['pointer']] == p['fieldSpan'], 'Exact caller TimelineName span differs')
    parent_pointer = p['pointer'].rsplit('/', 1)[0]
    parent = spans[parent_pointer]
    rd = native.Primitive(body, parent['start'], parent['end'])
    require(rd.uint() == 1976, 'Actual typed PlayTimeline discriminator differs')
    mask = rd.uint()
    require(mask in (6, 14), 'Actual PlayTimeline mask differs')
    start = rd.at
    require('assets/asbres/' + rd.string().lower() == record['source'] and (start, rd.at) == (p['fieldSpan']['start'], p['fieldSpan']['end']), 'Actual Timeline literal/source/span differs')
    require(rd.uint() == p['type']['observedSerializedEnum'], 'Actual Timeline type differs')
    if mask & 8:
        require(rd.count() == 0, 'Unsupported native Timeline parameters')
    rd.eof()
    return {'actualCachedCallerEntries': 1, 'actualWholePlayTimelineTerminals': 1,
            'wholeSourceBoundary': 'Frozen whole-EOF receipt rebound to actual entry SHA/size; terminal independently decoded',
            'callerEditionStatus': p['editionStatus']}


def audit_official(repo, record, directory):
    native = native_codec(record)
    edition = record['current']
    row, old = edition['row'], record['previous']
    p = row['officialSource']
    join = {'preservedSource': {'file': old['sourceFile'], 'sha256': old['sourceFileSha256'], 'pointer': old['pointer']},
            'raw': row['raw'], 'speakerRaw': row['speaker_raw'], 'tableOffset': p['tableOffset'], 'tableEnd': p['tableEnd'],
            'textOffset': p['textRecord']['offset'], 'textEnd': p['textRecord']['end'],
            'speakerOffset': p['speakerRecord']['offset'], 'speakerEnd': p['speakerRecord']['end']}
    result = native.official_replay(Path(repo), {'evidence': {'officialKorean': edition['officialEvidence']}, 'joins': {str(TID): join}}, Path(directory))
    evidence = edition['officialEvidence']
    table = evidence['talkTable']
    def actual_pack(name, expected):
        matches = [path for path in Path(directory).rglob(name) if native.file_sha(path) == expected]
        require(matches, 'Actual pinned official record pack absent')
        return matches[0].read_bytes()
    raw = actual_pack(table['file'], table['sha256'])
    body = raw[table['offset']:table['offset'] + table['length']]
    require(sha(body[p['tableOffset']:p['tableEnd']]) == p['tableRecordSha256'], 'Actual official table record span SHA differs')
    textmap = evidence['entry']
    raw = actual_pack(evidence['koreanPack']['file'], evidence['koreanPack']['sha256'])
    body = raw[textmap['offset']:textmap['offset'] + textmap['length']]
    for name in ('text', 'speaker'):
        span = p[name + 'Record']
        require(sha(body[span['offset']:span['end']]) == p[name + 'RecordSha256'], 'Actual official ' + name + ' record span SHA differs')
    result['actualRecordSpanHashes'] = 3
    return result


def audit_archive(record, path):
    proof = record['proof']
    require(sha(Path(path).read_bytes()) == proof['publicCaller']['archiveSha256'], 'Actual owner archive SHA differs')
    needed = {proof['publicCaller']['source']}
    for edge in proof['owner']['ownerChain']:
        needed.update(edge[k] for k in ('source', 'tableSource') if k in edge)
    docs, hashes = {}, {}
    with tarfile.open(path, 'r|gz') as archive:
        for member in archive:
            name = member.name.split('/', 1)[-1]
            if name in needed:
                require(member.isfile() and name not in docs, 'Archive member is nonunique/nonfile')
                raw = archive.extractfile(member).read()
                docs[name], hashes[name] = json.loads(raw), sha(raw)
    require(set(docs) == needed, 'Actual archive owner chain source absent')
    previous = None
    for edge in proof['owner']['ownerChain']:
        require(hashes[edge['source']] == edge['sourceSha256'] and (previous is None or edge['source'] == previous), 'Archive owner source SHA/chain differs')
        value = at(docs[edge['source']], edge['pointer'])
        if edge['kind'] == 'EXPLICIT_MAIN_MISSION_ID':
            require(value == edge['missionId'] == 2021901, 'Actual owner mission ID differs')
        elif edge['kind'] == 'EXPLICIT_JSON_PATH':
            require(value == edge['target'], 'Actual owner path differs')
            previous = edge['target']
        elif edge['kind'] == 'EXPLICIT_PERFORMANCE_LOOKUP':
            table = docs[edge['tableSource']]
            require(hashes[edge['tableSource']] == edge['tableSha256'] and value == edge['performanceId'] == at(table, edge['idPointer'])
                    and at(table, edge['pathPointer']) == edge['target'], 'Actual typed performance lookup differs')
            parent = at(docs[edge['source']], edge['pointer'].rsplit('/', 1)[0])
            require(parent['$type'] == 'RPG.GameCore.TriggerPerformance' and parent['PerformanceType'] == edge['performanceType'], 'Actual performance domain differs')
            previous = edge['target']
        else:
            raise AssertionError('Unsupported owner edge')
    caller = proof['publicCaller']
    require(previous == caller['source'] and hashes[previous] == caller['sourceSha256']
            and at(docs[previous], caller['pointer'].rsplit('/', 1)[0]) == caller['snapshotTask'], 'Actual archive typed caller differs')
    return {'actualArchiveOwnerSources': len(docs), 'ownerEdges': 3, 'exactPlayTimelineCalls': 1}


class ReaderHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.stack, self.bodies, self.editions, self.links, self.text = Counter(), [], {}, [], [], []
        self.roles = []
        self.proof_text = []

    def handle_starttag(self, tag, items):
        attrs = dict(items)
        if attrs.get('id'):
            self.ids[attrs['id']] += 1
        if attrs.get('data-version-edition'):
            self.editions.append(attrs['data-version-edition'])
        if attrs.get('data-version-original'):
            self.roles.append((attrs['data-version-original'], attrs.get('data-version-role'), attrs.get('data-speaker')))
        if tag == 'a':
            self.links.append((unquote(attrs.get('href', '')), 'data-reading-link' in attrs))
        anchor = attrs.get('id') if tag == 'p' and 'original-body' in attrs.get('class', '').split() else None
        if anchor:
            self.bodies[anchor] = []
        if tag not in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'):
            self.stack.append((tag, anchor, tag == 'details' and attrs.get('id') == 'verified-sources'))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, value):
        self.text.append(value)
        for _, anchor, source_proof in self.stack:
            if anchor:
                self.bodies[anchor].append(value)
            if source_proof:
                self.proof_text.append(value)


def rendered_check(record, static, expanded):
    body = ReaderHTML()
    body.feed(static)
    body.close()
    require(body.editions == ['previous', 'current'], 'Two ordered static edition readers absent')
    require(body.roles == [(record[key]['anchor'], record['role'], record[key]['row']['speaker']) for key in ('previous', 'current')], 'Static comparison role/speaker differs')
    require(set(body.bodies) == {record[x]['anchor'] for x in ('previous', 'current')}, 'Exactly two static originals required')
    for key in ('previous', 'current'):
        edition = record[key]
        require(body.ids[edition['anchor']] == 1 and ''.join(body.bodies[edition['anchor']]) == edition['row']['text'], 'Static original body/anchor differs: ' + key)
        require(any(url.endswith('/' + edition['url']) and reading for url, reading in body.links), 'Static edition original return link absent: ' + key)
        require(edition['editionLabel'] in ''.join(body.text), 'Static edition label absent: ' + key)
    require('보존 원문의 관찰 판본과 정규화 전 문자열은 미확인' in ''.join(body.text), 'Static previous raw/version boundary absent')
    proof = ReaderHTML()
    proof.feed(expanded)
    proof.close()
    require(proof.ids['verified-sources'] == 1, 'Comparison source disclosure absent')
    text = ''.join(proof.proof_text)
    p = record['proof']
    for value in (record['source'], p['scene']['idField']['field'], p['scene']['object']['sha256'], p['scene']['receipt']['cabSha256'],
                  p['scene']['object']['pathID'], p['scene']['track']['pathID'], p['scene']['track']['sha256'],
                  p['scene']['root']['pathID'], p['scene']['root']['sha256'],
                  p['nativeCaller']['entrySha256'], p['nativeCaller']['pointer'], '1669', 'SPOKEN',
                  record['previous']['sourceFileSha256'], record['previous']['pointer'], record['current']['sourceFileSha256'],
                  record['current']['row']['officialSource']['textRecordSha256']):
        require(value in text, 'Rendered exact source proof absent: ' + value)
    require(all(value in text for value in ('60–64', '920–976', '1104090–1104128', '25531103–25531290', 'OSPRODWin4.6.0')),
            'Rendered exact native/official record spans or version absent')
    require('캐시된 호출 자료와 현재 설치본의 판본 일치는 미확인' in text
            and '어느 판본의 문장이 실제로 재생되는지는 미확인' in text, 'Rendered edition/playback boundary absent')
    return {'staticOriginals': 2, 'editionLabels': 2, 'sourceDisclosures': 1, 'originalReturnLinks': 2}


def dist_check(repo, record, directory, report_path=None):
    static = (Path(directory) / record['url']).read_text(encoding='utf8')
    expanded = static
    if re.search(r'__spr\(|__sp\(|__starrailPublicationWrite\(', static):
        report = load(report_path or Path(repo) / '.codex-work/publication-build-report.json')
        for shard in report.get('proofShards', {}).values():
            url = unquote(shard['url'])
            require(url.startswith('/starrail-quests/'), 'Publication proof shard base differs')
            path = Path(directory) / relative(url[len('/starrail-quests/'):])
            require(sha(path.read_bytes()) == shard['assetSha256'], 'Actual publication proof shard SHA differs')
        expanded = expand_proof_slots(static, report)
    return rendered_check(record, static, expanded)


def expand_proof_slots(text, report):
    """Independently decode only metadata slots; reading bodies stay static.

    The bounded stdlib decoder uses the existing publication data contract and
    never imports or executes its producer, JavaScript, or UI reconstruction.
    """
    decoded = {}
    def slot(match):
        index = int(match[1])
        pool = report.get('proofPool', [])
        require(0 <= index < len(pool), 'Publication proof slot out of bounds')
        proof = pool[index]
        key = str(proof['shard'])
        if key not in decoded:
            shard = report['proofShards'][key]
            packed = base64.b64decode(shard['payload'], validate=True)
            body = gzip.decompress(packed)
            require(len(body) == shard['rawBytes'] and sha(body) == shard['rawSha256'], 'Publication decoded shard bytes/SHA differ')
            rows = json.loads(body.decode('utf8', errors='strict'))
            require(isinstance(rows, list) and len(rows) == shard['count'] == len(shard['sizes']), 'Publication shard slot count differs')
            for offset, row in enumerate(rows):
                require(isinstance(row, str), 'Publication proof slot must be text')
                original = pool[shard['start'] + offset]
                raw = row.encode('utf8')
                require(len(raw) == shard['sizes'][offset] == original['rawBytes'] and sha(raw) == original['sha256']
                        and str(original['shard']) == key, 'Publication proof slot source SHA/size differs')
            decoded[key] = rows
        offset = index - report['proofShards'][key]['start']
        require(0 <= offset < len(decoded[key]), 'Publication proof shard slot outside range')
        return decoded[key][offset]
    text = re.sub(r'<script>__spr\(([0-9]+)\);</script>', slot, text)
    def compressed(match):
        key, encoded, size = match.groups()
        proof = report['compressedProofs'][key]
        packed = base64.b64decode(encoded, validate=True)
        body = gzip.decompress(packed)
        require(len(body) == int(size) == proof['rawBytes'] and len(packed) == proof['gzipBytes'] and sha(body) == key, 'Compressed publication proof SHA/size differs')
        return body.decode('utf8', errors='strict')
    return re.sub(r'<script data-pc="([0-9a-f]{64})">__starrailPublicationWrite\("([A-Za-z0-9+/=]+)",([0-9]+)\);</script>', compressed, text)


def self_tests(repo, data):
    tests = []
    def reject(name, fn):
        try:
            fn()
        except (AssertionError, KeyError, IndexError, TypeError, ValueError):
            tests.append(name)
            return
        raise AssertionError('Negative unexpectedly accepted: ' + name)
    def mutate(name, edit):
        other = deepcopy(data)
        edit(other, other['records'][0])
        reject(name, lambda: source_check(repo, other))
    cases = [
        ('Talk id mutation', lambda d,r: r.__setitem__('talkId', TID + 1)),
        ('preserved body mutation', lambda d,r: r['previous']['row'].__setitem__('text', '변경')),
        ('current body substitution', lambda d,r: r['current']['row'].__setitem__('text', r['previous']['row']['text'])),
        ('raw mutation', lambda d,r: r['current']['row'].__setitem__('raw', r['current']['row']['text'])),
        ('old raw fabricated', lambda d,r: r['previous'].__setitem__('raw', r['previous']['row']['text'])),
        ('old version invented', lambda d,r: r['previous'].__setitem__('observedReleaseVersion', '4.5')),
        ('cached edition current claim', lambda d,r: r['proof']['nativeCaller'].__setitem__('editionStatus', 'CURRENT')),
        ('runtime playback claim', lambda d,r: d['evidence'].__setitem__('runtimePlaybackStatus', 'PASS')),
        ('VoiceID promoted', lambda d,r: r['proof']['scene']['idField'].__setitem__('field', 'VoiceID')),
        ('UIID promoted', lambda d,r: r['proof']['scene']['idField'].__setitem__('field', 'UIKey')),
        ('screen role substituted', lambda d,r: r['proof']['scene'].__setitem__('nativeIDUseRole', 'SCREEN_TEXT')),
        ('full EOF removed', lambda d,r: r['proof']['nativeCaller'].__setitem__('consumedBytes', 1600)),
        ('scene source mismatch', lambda d,r: r.__setitem__('source', 'unrelated.playable')),
        ('old pointer moved', lambda d,r: r['previous'].__setitem__('pointer', '/section/rows/95')),
        ('official span moved', lambda d,r: r['current']['row']['officialSource'].__setitem__('tableOffset', 0)),
        ('native field span moved', lambda d,r: r['proof']['scene']['idField'].__setitem__('span', [64,68])),
        ('owner path altered', lambda d,r: r['proof']['owner']['ownerChain'][1].__setitem__('target', 'wrong.json')),
        ('private path leaked', lambda d,r: r.__setitem__('source', 'D:/private/file.json')),
        ('duplicate record', lambda d,r: d['records'].append(deepcopy(r))),
        ('collapsed edition anchor', lambda d,r: r['current'].__setitem__('anchor', r['previous']['anchor'])),
        ('comparison role promoted', lambda d,r: r.__setitem__('role','SPOKEN')),
        ('closed proof pin altered', lambda d,r: r['proof']['scene']['receipt'].__setitem__('cabSha256','0'*64)),
    ]
    for name, edit in cases:
        mutate(name, edit)
    record = data['records'][0]
    from html import escape
    static = ''.join('<section data-version-edition="'+key+'">'+escape(record[key]['editionLabel'])+'<div data-version-original="'+record[key]['anchor']+'" data-version-role="'+record['role']+'" data-speaker="'+escape(record[key]['row']['speaker'],quote=True)+'"><p class="original-body" id="'+record[key]['anchor']+'">'+escape(record[key]['row']['text'])+'</p><a data-reading-link href="/starrail-quests/'+record[key]['url']+'">원문</a></div></section>' for key in ('previous','current'))
    static += '보존 원문의 관찰 판본과 정규화 전 문자열은 미확인'
    proof = '<details id="verified-sources">'+escape(json.dumps(record,ensure_ascii=False))+'1669 SPOKEN 60–64 920–976 1104090–1104128 25531103–25531290 캐시된 호출 자료와 현재 설치본의 판본 일치는 미확인 어느 판본의 문장이 실제로 재생되는지는 미확인</details>'
    rendered_check(record, static, static + proof)
    reject('static original removed', lambda: rendered_check(record, '', proof))
    reject('static original text changed', lambda: rendered_check(record, static.replace(record['previous']['row']['text'],'변경'), static+proof))
    reject('static anchor duplicated', lambda: rendered_check(record, static+'<p id="'+record['previous']['anchor']+'"></p>',static+proof))
    reject('static return link removed', lambda: rendered_check(record, static.replace(record['previous']['url'],'wrong.html'),static+proof))
    reject('source proof absent', lambda: rendered_check(record,static,static))
    reject('raw boundary removed', lambda: rendered_check(record, static.replace('보존 원문의 관찰 판본과 정규화 전 문자열은 미확인',''), static+proof))
    reject('static comparison role promoted', lambda: rendered_check(record, static.replace('VERSION_COMPARISON_REFERENCE','SPOKEN'), static+proof))
    reject('static edition label removed', lambda: rendered_check(record, static.replace(record['current']['editionLabel'],''), static+proof))
    raw = proof.encode('utf8')
    shard = {'start': 0, 'count': 1, 'sizes': [len(raw)], 'rawSha256': '', 'rawBytes': 0, 'payload': ''}
    packed = json.dumps([proof],ensure_ascii=False,separators=(',',':')).encode('utf8')
    shard.update(rawSha256=sha(packed),rawBytes=len(packed),payload=base64.b64encode(gzip.compress(packed,mtime=0)).decode('ascii'))
    report = {'proofPool': [{'shard': 0, 'rawBytes':len(raw), 'sha256':sha(raw)}], 'proofShards': {'0':shard}}
    require(expand_proof_slots('<script>__spr(0);</script>',report) == proof, 'Independent publication proof inverse differs')
    reject('publication slot out of range', lambda: expand_proof_slots('<script>__spr(1);</script>',report))
    changed = deepcopy(report)
    changed['proofPool'][0]['sha256'] = '0' * 64
    reject('publication decoded proof SHA drift', lambda: expand_proof_slots('<script>__spr(0);</script>',changed))
    changed = deepcopy(report)
    changed['proofShards']['0']['rawBytes'] += 1
    reject('publication decoded shard size drift', lambda: expand_proof_slots('<script>__spr(0);</script>',changed))
    return {'negativeCases': len(tests), 'rejected': tests}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=SITE)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--capsule', type=Path)
    parser.add_argument('--installed-data', type=Path)
    parser.add_argument('--caller-replay', type=Path)
    parser.add_argument('--official-audit', type=Path)
    parser.add_argument('--structure-archive', type=Path)
    parser.add_argument('--dist', type=Path)
    parser.add_argument('--publication-report', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    data = load(args.data or repo / 'data/versioned-timeline-text.json')
    record, = source_check(repo, data)
    checks = {'source': {'records': 1, 'exactRepositoryEditionRows': 2, 'nativeDomain': 'PlaySimpleTalkClip.Config.TalkSentenceID',
                         'scope': 'Exact repository originals and immutable public proof pin; actual external bytes replayed only when requested',
                         'previousRawStatus': 'UNVERIFIED', 'callerEditionStatus': data['evidence']['callerEditionStatus']}}
    capsule = None
    if args.capsule:
        capsule = capsule_check(record, args.capsule)
        checks['capsule'] = {'exactFrozenCapsules': 1, 'scope': 'Hash-bound evidence projection'}
    require(not (args.installed_data or args.caller_replay) or capsule is not None, 'Actual CAB/caller replay needs --capsule')
    if args.installed_data:
        checks['actualCAB'] = audit_cab(record, capsule, args.installed_data)
    if args.caller_replay:
        checks['actualCaller'] = audit_caller(record, capsule, args.caller_replay)
    if args.official_audit:
        checks['actualOfficial'] = audit_official(repo, record, args.official_audit)
    if args.structure_archive:
        checks['actualArchive'] = audit_archive(record, args.structure_archive)
    if args.self_test:
        checks['selfTests'] = self_tests(repo, data)
    if args.dist:
        checks['dist'] = dist_check(repo, record, args.dist, args.publication_report)
    result = {'status': 'PASS', 'verifierSha256': sha(Path(__file__).read_bytes()), 'payloadCanonicalSha256': canonical(data), 'checks': checks}
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
