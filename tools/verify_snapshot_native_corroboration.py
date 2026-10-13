"""Validate the closed cached-caller overlay while preserving its public base.

Default: exact portable repository projection and every original reference.
--audit: rebind frozen caller EOF receipts to actual cached entry/terminal bytes.
--installed-root: additionally rebind current native profile DLL/metadata hashes.
--dist: validate static reader boundaries and all rendered evidence markers.
No producer, native code, Lua, JavaScript, or game code is executed.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import base64
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote

SITE = Path(__file__).resolve().parents[1]
PUBLIC_SHA = '94bc9b8177a03aa4cc617b026de7e2474217a3b435fe2a55865ba35e66ac0ccc'
FRESH_SHA = 'b31990792d890bb38c3ecfb674f1cd7faa5f4200d9da9dc1aabc5e312d2094be'
OVERLAY_SHA = 'a303853309a3a3923742c55c706d1bab323de0f13576549a08e81a817d29abb7'
CANONICAL = '7ef973afeac846c20a5756730f9ac69724045579c0d9297e57873bbde9e60779'
AUDIT_SHA = '928c074cfb72a045fb5d3552f7bb24b9c9ced872186c607df1ad3cb1f039857d'
UNKNOWN = 'CACHED_SNAPSHOT_CURRENT_INSTALLED_EDITION_UNVERIFIED'
CORROBORATED = '캐시된 호출 자료의 전체 경계와 연출 호출 필드를 확인했습니다.'
STALE = '호출자 바이너리의 전체 해석은 미지원 상태'


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8'))


def load(path):
    return json.loads(Path(path).read_bytes())


def relative(value):
    require(isinstance(value, str) and value and not re.search(r'^[a-z]+:|^/|\\', value, re.I)
            and all(part not in ('.', '..', '') for part in value.split('/')), 'Unsafe/private source path')
    return value


def public_safe(value):
    if isinstance(value, dict):
        require(not any(key in value for key in ('privateReplay', 'packPath', 'objectFolder', 'nativePackPath')), 'Private replay field leaked')
        for item in value.values():
            public_safe(item)
    elif isinstance(value, list):
        for item in value:
            public_safe(item)
    elif isinstance(value, str):
        require(not re.search(r'[A-Z]:[/\\]|file://|\\\\', value, re.I), 'Private absolute path leaked')
    elif type(value) is int:
        require(abs(value) <= 2**53 - 1, 'Integer precision loss')


def at(value, pointer):
    require(pointer.startswith('/'), 'Unsafe JSON pointer')
    for part in pointer.split('/')[1:]:
        key = part.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def baseline(repo):
    raw = (Path(repo) / 'data/public-snapshot-timeline-dialogue.json').read_bytes()
    require(sha(raw) == PUBLIC_SHA, 'Preserved public snapshot projection changed')
    fresh = (Path(repo) / 'data/native-fresh-timeline-dialogue.json').read_bytes()
    require(sha(fresh) == FRESH_SHA, 'Known native fresh projection changed')
    return json.loads(raw), json.loads(fresh)


def root_identity(scene):
    proof = scene['proof']
    receipt = proof['receipt']
    return (receipt.get('sourceBlockFile', receipt.get('blockFile')), receipt['bundleOffset'], receipt['bundleBytes'],
            receipt['cabName'], proof['container']['key'], str(int(proof['root']['pathID']) & (2**64 - 1)))


def original_pair(public, scene, reference_index):
    ref = scene['proof']['references'][reference_index]
    source = public['sourceProofs'][ref['sourceIndex']]
    require(scene['source'] == scene['proof']['container']['key'] and scene['source'].startswith('assets/asbres/'), 'Preserved exact native container/root identity differs')
    name = ref['context']['typedAncestors'][-1]['contextFields']['TimelineName']
    require('assets/asbres/' + name.lower() == scene['source'], 'Exact serialized TimelineName/canonical resource key differs')
    return ref, source, name


def source_check(repo, data):
    """Return all 1,410 validated references; original public metadata is intact."""
    public_safe(data)
    require(data['schema'] == 'starrail-public-timeline-native-corroboration.v1', 'Overlay schema differs')
    require(data['baseProjectionSha256'] == PUBLIC_SHA and data['nativeFreshProjectionSha256'] == FRESH_SHA, 'Overlay version boundary differs')
    public, fresh = baseline(repo)
    evidence = data['evidence']
    require(evidence['typedConsumer'] == 'RPG.GameCore.PlayTimeline' and evidence['wholeEOFStatus'] == 'WHOLE_NATIVE_FIELDS_EOF_PASS'
            and evidence['trailingByteRejected'] is True, 'Typed cached whole EOF claim differs')
    require(evidence['callerEditionStatus'] == UNKNOWN and evidence['runtimePlaybackStatus'] == 'UNVERIFIED', 'Installed edition/runtime uncertainty weakened')
    scenes = {scene['id']: scene for scene in public['scenes']}
    require(len(scenes) == len(public['scenes']), 'Duplicate baseline scene')
    fresh_keys = set()
    for scene in fresh['scenes']:
        for ref in scene['proof']['references']:
            source = fresh['sourceProofs'][ref['sourceIndex']]
            fresh_keys.add((source['logicalJsonPath'], ref['pointer'], scene['source'][len('assets/asbres/'):].lower(),
                            root_identity(scene), source['mission'], canonical(source['ownerChain'])))
    seen, used_sources, matched_scenes, used_snapshot = set(), set(), set(), set()
    for ref in data['references']:
        pair = (ref['sceneId'], ref['referenceIndex'])
        require(pair not in seen and type(ref['referenceIndex']) is int and ref['referenceIndex'] >= 0, 'Duplicate/invalid exact reference pair')
        seen.add(pair)
        scene = scenes[ref['sceneId']]
        original, previous, name = original_pair(public, scene, ref['referenceIndex'])
        source = data['sourceProofs'][ref['nativeSourceIndex']]
        require(source['snapshotSourceIndex'] == original['sourceIndex'] and source['logicalJsonPath'] == previous['logicalJsonPath'], 'Exact public/native source index/path differs')
        require(original['nativeCallerWholeEOF'] is False and original['nativeInstalledCallerClaim'] is False
                and original['callerSourceKind'] == 'CALLER_SOURCE_PUBLIC_JSON_SNAPSHOT_NATIVE_EOF_BLOCKED', 'Original public-only boundary changed')
        require(source['entrySha256'] == previous['rawConsumerByteFrontier']['entrySha256']
                and source['consumedBytes'] == previous['rawConsumerByteFrontier']['nativeBytes'], 'Exact old STOP entry identity differs')
        parent_pointer = original['pointer'].rsplit('/', 1)[0]
        require(original['context']['typedContainer'] == {'type': 'RPG.GameCore.PlayTimeline', 'pointer': parent_pointer}, 'Original consumer domain/pointer differs')
        require(original['context']['typedAncestors'][-1]['contextFields']['TimelineName'] == name, 'Exact original TimelineName/root bridge differs')
        key = (previous['logicalJsonPath'], original['pointer'], name.lower(), root_identity(scene), previous['mission'], canonical(previous['ownerChain']))
        require(key not in fresh_keys, 'Already-native fresh reference promoted again')
        catalog = source['catalogMatch']
        pack = evidence['callerPacks'][source['callerPackIndex']]
        require(catalog['length'] == source['consumedBytes'] and catalog['packExpectedBytes'] == pack['bytes']
                and 0 <= catalog['offset'] < catalog['offset'] + catalog['length'] <= pack['bytes'], 'Caller entry escapes actual pack')
        field, terminal = ref['fieldSpan'], ref['terminalSpan']
        require(all(type(v) is int for v in field + terminal) and len(field) == len(terminal) == 2
                and 0 <= terminal[0] < field[0] < field[1] < terminal[1] <= source['consumedBytes'], 'Typed caller field/terminal span escapes entry')
        require(ref['mask'] in (6, 14) and ref['nativeType'] in (4, 8)
                and terminal[0] == field[0] - 3 and terminal[1] == field[1] + (2 if ref['mask'] == 14 else 1), 'Exact PlayTimeline terminal grammar differs')
        encoded = name.encode('utf8')
        width = max(1, (len(encoded).bit_length() + 6) // 7)
        require(field[1] - field[0] == len(encoded) + width, 'TimelineName exact UTF8 field length differs')
        profile = evidence['profiles'][str(source['sourceCodeStage'])]
        relative(profile['sourceCodeReceipt']['file'])
        relative(profile['currentProfile']['file'])
        used_sources.add(ref['nativeSourceIndex'])
        used_snapshot.add(source['snapshotSourceIndex'])
        matched_scenes.add(scene['id'])
    require(len(seen) == 1410 and len(matched_scenes) == 1400 and len(used_sources) == len(used_snapshot) == 239
            and used_sources == set(data['sourceProofs']), 'Closed corroboration coverage differs')
    require(all((scene_id, index) in seen for scene_id in matched_scenes for index in range(len(scenes[scene_id]['proof']['references']))), 'Partially matched scene claimed fully corroborated')
    require(canonical(data) == CANONICAL, 'Hard-closed minimal overlay changed')
    return data['references']


class Primitive:
    def __init__(self, raw, start, end):
        require(0 <= start <= end <= len(raw), 'Terminal bound escapes native entry')
        self.raw, self.at, self.end = raw, start, end

    def uint(self):
        value, shift = 0, 0
        while self.at < self.end and shift < 35:
            byte = self.raw[self.at]
            self.at += 1
            value |= (byte & 127) << shift
            if not byte & 128:
                require(value < 2**32 and not (shift and byte == 0), 'Invalid native UInt32 encoding')
                return value
            shift += 7
        raise AssertionError('Truncated/overflowing native UInt32')

    def string(self):
        count = self.uint()
        require(self.at + count <= self.end, 'Native UTF8 string escapes terminal')
        value = self.raw[self.at:self.at + count].decode('utf8', errors='strict')
        self.at += count
        return value

    def eof(self):
        require(self.at == self.end, 'Native terminal trailing bytes')


def terminal_check(body, ref, timeline_name):
    require(ref['mask'] in (6, 14) and ref['nativeType'] in (4, 8), 'Unsupported typed terminal grammar')
    reader = Primitive(body, *ref['terminalSpan'])
    require(reader.uint() == 1976 and reader.uint() == ref['mask'], 'Actual typed PlayTimeline discriminator/mask differs')
    start = reader.at
    require(reader.string() == timeline_name and [start, reader.at] == ref['fieldSpan'], 'Actual TimelineName UTF8/value/pointer span differs')
    require(reader.uint() == ref['nativeType'], 'Actual Timeline type observation differs')
    if ref['mask'] & 8:
        require(reader.uint() == 0, 'Unsupported active Timeline parameters')
    reader.eof()


def audit_check(repo, data, directory, native_inputs=None, installed_root=None):
    directory = Path(directory)
    raw = (directory / 'phase9-native-corroboration-audit.json').read_bytes()
    require(sha(raw) == AUDIT_SHA, 'Frozen preintegration audit SHA differs')
    audit = json.loads(raw)
    fields = Path(native_inputs) if native_inputs else directory.parent / 'star-fields'
    files = {}
    for name, proof in audit['inputPins'].items():
        relative(name)
        raw = (fields / name).read_bytes()
        require(len(raw) == proof['bytes'] and sha(raw) == proof['sha256'], 'Frozen schema/profile/whole-source input SHA differs: ' + name)
        files[name] = json.loads(raw)
    public, _ = baseline(repo)
    scenes = {scene['id']: scene for scene in public['scenes']}
    packs, bodies, fields_by_source, spans_by_source = {}, {}, {}, {}
    for key, source in data['sourceProofs'].items():
        stage = source['sourceCodeStage']
        profile = data['evidence']['profiles'][str(stage)]
        code = profile['sourceCodeReceipt']
        code_path = fields / relative(code['file'])
        require(code_path.stat().st_size == code['bytes'] and file_sha(code_path) == code['sha256'], 'Retained native reader code hash boundary differs')
        replay_name = 'new-field-replay.json' if stage == 0 else 'phase' + str(stage) + '-new-field-replay.json'
        require(audit['inputPins'][replay_name]['sha256'] == profile['wholeSourceReplaySha256'], 'Whole source replay profile identity differs')
        candidates = [r for r in files[replay_name]['results'] if r['source'] == source['logicalJsonPath'] and r['sha256'] == source['entrySha256']]
        require(candidates, 'Exact frozen native caller receipt absent')
        receipt = candidates[-1]
        require(receipt['status'] == 'WHOLE_NATIVE_FIELDS_EOF_PASS' and receipt['trailingByteRejected'] is True
                and receipt['bytes'] == source['consumedBytes'], 'Whole cached source EOF receipt differs')
        previous = public['sourceProofs'][source['snapshotSourceIndex']]
        require(receipt['descriptor']['ownerChain'] == previous['ownerChain'] and receipt['descriptor']['mission'] == previous['mission'], 'Actual caller owner proof differs')
        actual_pack = receipt['pack']
        declared_pack = data['evidence']['callerPacks'][source['callerPackIndex']]
        pack_key = (actual_pack['path'], declared_pack['sha256'])
        require(actual_pack['sha256'] == declared_pack['sha256'] and actual_pack['bytes'] == declared_pack['bytes'], 'Caller pack receipt differs')
        if pack_key not in packs:
            body = Path(actual_pack['path']).read_bytes()
            require(sha(body) == declared_pack['sha256'] and len(body) == declared_pack['bytes'], 'Actual cached caller pack bytes/SHA differ')
            packs[pack_key] = body
        match = source['catalogMatch']
        body = packs[pack_key][match['offset']:match['offset'] + match['length']]
        require(len(body) == source['consumedBytes'] and sha(body) == source['entrySha256'], 'Actual cached caller entry SHA/whole boundary differs')
        spans = {span['pointer']: span for span in receipt['fieldSpans']}
        require(len(spans) == len(receipt['fieldSpans']) and spans[''] == {'pointer': '', 'start': 0, 'end': len(body)}, 'Frozen whole EOF field partition differs')
        for span in spans.values():
            require(0 <= span['start'] <= span['end'] <= len(body), 'Frozen caller field escapes source')
            if span['pointer']:
                at(receipt['fields'], span['pointer'])
        bodies[key], fields_by_source[key], spans_by_source[key] = body, receipt['fields'], spans
        current = files[profile['currentProfile']['file']]
        require(current['status'] == 'PASS_CURRENT_INPUTS_AND_RECORDED_BYTES'
                and current['currentInputReceipts'] == data['evidence']['nativeInputReceipts'], 'Current native profile input boundary differs')
    for ref in data['references']:
        scene = scenes[ref['sceneId']]
        original, _, name = original_pair(public, scene, ref['referenceIndex'])
        key = ref['nativeSourceIndex']
        spans, fields_value = spans_by_source[key], fields_by_source[key]
        parent = original['pointer'].rsplit('/', 1)[0]
        require(spans[original['pointer']] == {'pointer': original['pointer'], 'start': ref['fieldSpan'][0], 'end': ref['fieldSpan'][1]}
                and spans[parent] == {'pointer': parent, 'start': ref['terminalSpan'][0], 'end': ref['terminalSpan'][1]}, 'Exact frozen terminal/field pointer differs')
        typed = at(fields_value, parent)
        require(typed['$type'] == 'RPG.GameCore.PlayTimeline' and typed['TimelineName'] == name
                and typed['Type']['observedSerializedEnum'] == ref['nativeType'], 'Whole native graph consumer/value differs')
        terminal_check(bodies[key], ref, name)
    native_inputs_checked = 0
    if installed_root:
        for name, path in [('GameAssembly.dll', 'GameAssembly.dll'), ('global-metadata.dat', 'StarRail_Data/il2cpp_data/Metadata/global-metadata.dat')]:
            current = Path(installed_root) / path
            proof = data['evidence']['nativeInputReceipts'][name]
            require(current.stat().st_size == proof['bytes'] and file_sha(current) == proof['sha256'], 'Actual current native DLL/metadata differs')
            native_inputs_checked += 1
    return {'actualCachedPacks': len(packs), 'wholeCallerEntriesRebound': len(bodies), 'wholeCallerEntryBytes': sum(len(body) for body in bodies.values()),
            'independentWholePlayTimelineTerminals': len(data['references']), 'actualCurrentNativeInputs': native_inputs_checked,
            'scope': 'Immutable whole EOF/schema receipts rebound to actual entry bytes; each terminal independently decoded',
            'callerEditionStatus': UNKNOWN, 'runtimePlaybackStatus': 'UNVERIFIED'}


class ReaderHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.markers, self.text, self.proof_text = [], {}, [], []

    def handle_starttag(self, tag, values):
        attrs = dict(values)
        marker = attrs.get('data-native-corroboration')
        if marker is not None:
            require(marker not in self.markers, 'Duplicate rendered corroboration marker')
            require(any(proof for _, _, proof in self.stack), 'Corroboration marker escapes source disclosure')
            self.markers[marker] = []
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
            self.stack.append((tag, marker, tag == 'details' and attrs.get('id') == 'verified-sources'))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, value):
        self.text.append(value)
        for _, marker, proof in self.stack:
            if marker is not None:
                self.markers[marker].append(value)
            if proof:
                self.proof_text.append(value)


def rendered_check(data, public, scene, references, text):
    parsed = ReaderHTML()
    parsed.feed(text)
    parsed.close()
    expected = {scene['id'] + ':' + str(ref['referenceIndex']): ref for ref in references}
    require(set(parsed.markers) == set(expected), 'Rendered exact corroboration pair set differs')
    proof_text = ''.join(parsed.proof_text)
    require(CORROBORATED in proof_text and STALE not in ''.join(parsed.text), 'Affected unsupported caller disclaimer remains stale')
    require('판본 일치는 미확인' in proof_text and '실제 재생 여부는 미확인' in proof_text, 'Rendered cached/current edition or playback boundary absent')
    for marker, ref in expected.items():
        source = data['sourceProofs'][ref['nativeSourceIndex']]
        original, _, _ = original_pair(public, scene, ref['referenceIndex'])
        value = ''.join(parsed.markers[marker])
        for token in (source['logicalJsonPath'], original['pointer'], source['entrySha256'], str(source['consumedBytes']),
                      str(ref['fieldSpan'][0]) + '–' + str(ref['fieldSpan'][1])):
            require(token in value and token in proof_text, 'Rendered exact cached source field proof absent: ' + marker + ' ' + token)
    return len(expected)


def expand_proof_slots(text, report, decoded=None):
    # The existing metadata data contract is decoded with stdlib only.
    decoded = {} if decoded is None else decoded
    def slot(match):
        index = int(match[1]);pool = report['proofPool']
        require(0 <= index < len(pool), 'Publication proof slot outside pool')
        item = pool[index];key = str(item['shard']);shard = report['proofShards'][key]
        if key not in decoded:
            raw = gzip.decompress(base64.b64decode(shard['payload'], validate=True))
            require(len(raw) == shard['rawBytes'] and sha(raw) == shard['rawSha256'], 'Publication source shard SHA/size differs')
            rows = json.loads(raw.decode('utf8', errors='strict'))
            require(isinstance(rows,list) and len(rows) == shard['count'] == len(shard['sizes']), 'Publication proof shard count differs')
            for offset, row in enumerate(rows):
                require(isinstance(row,str), 'Publication proof slot is not text')
                body = row.encode('utf8');proof = pool[shard['start'] + offset]
                require(len(body) == shard['sizes'][offset] == proof['rawBytes'] and sha(body) == proof['sha256']
                        and str(proof['shard']) == key, 'Publication proof slot SHA/size differs')
            decoded[key] = rows
        offset = index - shard['start']
        require(0 <= offset < len(decoded[key]), 'Publication proof slot escapes shard')
        return decoded[key][offset]
    text = re.sub(r'<script>__spr\(([0-9]+)\);</script>',slot,text)
    def compressed(match):
        key, encoded, size = match.groups();proof = report['compressedProofs'][key]
        packed = base64.b64decode(encoded,validate=True);raw = gzip.decompress(packed)
        require(len(raw) == int(size) == proof['rawBytes'] and len(packed) == proof['gzipBytes'] and sha(raw) == key,'Compressed publication proof differs')
        return raw.decode('utf8',errors='strict')
    return re.sub(r'<script data-pc="([0-9a-f]{64})">__starrailPublicationWrite\("([A-Za-z0-9+/=]+)",([0-9]+)\);</script>',compressed,text)


def dist_check(repo, data, directory, publication_report=None):
    public, _ = baseline(repo)
    scenes = {scene['id']:scene for scene in public['scenes']}
    by_scene = defaultdict(list)
    for ref in data['references']:
        by_scene[ref['sceneId']].append(ref)
    report, markers, decoded = None, 0, {}
    for scene_id, references in by_scene.items():
        path = Path(directory) / '대화' / ('연출-' + scene_id + '.html')
        text = path.read_text(encoding='utf8')
        if re.search(r'__spr\(|__starrailPublicationWrite\(', text):
            if report is None:
                report = load(publication_report or Path(repo) / '.codex-work/publication-build-report.json')
                for shard in report.get('proofShards',{}).values():
                    url = unquote(shard['url'])
                    require(url.startswith('/starrail-quests/'),'Publication proof shard base differs')
                    require(file_sha(Path(directory) / relative(url[len('/starrail-quests/'):])) == shard['assetSha256'],'Actual publication proof shard SHA differs')
            text = expand_proof_slots(text,report,decoded)
        markers += rendered_check(data,public,scenes[scene_id],references,text)
    require(markers == 1410 and len(by_scene) == 1400,'Rendered closed overlay count differs')
    return {'corroboratedReaders':len(by_scene),'exactRenderedReferenceMarkers':markers,'scope':'Static source originals remain the baseline reader verifier responsibility; this gate validates the overlay and scoped edition/EOF display'}


def self_tests(repo, data):
    tests=[]
    def reject(name,fn):
        try:
            fn()
        except (AssertionError,KeyError,IndexError,TypeError,ValueError):
            tests.append(name);return
        raise AssertionError('Negative unexpectedly accepted: '+name)
    def mutate(name,edit):
        changed=deepcopy(data);edit(changed,changed['references'][0],changed['sourceProofs'][changed['references'][0]['nativeSourceIndex']])
        reject(name,lambda:source_check(repo,changed))
    for name,edit in [
        ('source path mismatch',lambda d,r,s:s.__setitem__('logicalJsonPath','wrong.json')),
        ('source STOP entry SHA mismatch',lambda d,r,s:s.__setitem__('entrySha256','0'*64)),
        ('native entry bytes changed',lambda d,r,s:s.__setitem__('consumedBytes',1)),
        ('snapshot source owner switched',lambda d,r,s:s.__setitem__('snapshotSourceIndex',next(k for k in d['sourceProofs'].values()if k['snapshotSourceIndex']!=s['snapshotSourceIndex'])['snapshotSourceIndex'])),
        ('native consumer domain changed',lambda d,r,s:d['evidence'].__setitem__('typedConsumer','RPG.GameCore.PlayVOSequence')),
        ('whole EOF removed',lambda d,r,s:d['evidence'].__setitem__('wholeEOFStatus','PARTIAL')),
        ('runtime promotion',lambda d,r,s:d['evidence'].__setitem__('runtimePlaybackStatus','PASS')),
        ('installed edition promotion',lambda d,r,s:d['evidence'].__setitem__('callerEditionStatus','CURRENT')),
        ('field span escapes entry',lambda d,r,s:r.__setitem__('fieldSpan',[0,999999])),
        ('terminal span shifted',lambda d,r,s:r['terminalSpan'].__setitem__(0,r['terminalSpan'][0]+1)),
        ('unsupported native type',lambda d,r,s:r.__setitem__('nativeType',99)),
        ('opaque mask promoted',lambda d,r,s:r.__setitem__('mask',63)),
        ('wrong reference index',lambda d,r,s:r.__setitem__('referenceIndex',99999)),
        ('reference dropped',lambda d,r,s:d['references'].pop()),
        ('reference duplicated',lambda d,r,s:d['references'].append(deepcopy(r))),
        ('root/base projection changed',lambda d,r,s:d.__setitem__('baseProjectionSha256','0'*64)),
        ('private path leaked',lambda d,r,s:s.__setitem__('logicalJsonPath','D:/private/file')),
        ('retained reader source pin changed',lambda d,r,s:d['evidence']['profiles']['0']['sourceCodeReceipt'].__setitem__('sha256','0'*64)),
    ]:mutate(name,edit)
    public,_=baseline(repo);ref=data['references'][0];scene=next(s for s in public['scenes']if s['id']==ref['sceneId']);references=[r for r in data['references']if r['sceneId']==scene['id']]
    from html import escape
    text='<details id="verified-sources">'+CORROBORATED+' 판본 일치는 미확인 실제 재생 여부는 미확인'
    for r in references:
        source=data['sourceProofs'][r['nativeSourceIndex']];original,_,_=original_pair(public,scene,r['referenceIndex'])
        text+='<div data-native-corroboration="'+scene['id']+':'+str(r['referenceIndex'])+'">'+escape(' '.join([source['logicalJsonPath'],original['pointer'],source['entrySha256'],str(source['consumedBytes']),str(r['fieldSpan'][0])+'–'+str(r['fieldSpan'][1])]))+'</div>'
    text+='</details>';rendered_check(data,public,scene,references,text)
    reject('rendered marker missing',lambda:rendered_check(data,public,scene,references,text.replace('data-native-corroboration','data-wrong')))
    reject('rendered source bytes missing',lambda:rendered_check(data,public,scene,references,text.replace(data['sourceProofs'][ref['nativeSourceIndex']]['entrySha256'],'wrong')))
    reject('affected stale unsupported disclaimer',lambda:rendered_check(data,public,scene,references,text+STALE))
    reject('rendered playback uncertainty removed',lambda:rendered_check(data,public,scene,references,text.replace('실제 재생 여부는 미확인','')))
    reject('rendered marker outside source disclosure',lambda:rendered_check(data,public,scene,references,text.replace('<details id="verified-sources">','<div>').replace('</details>','</div>')))
    def uint(value):
        out=bytearray()
        while value>=128:out.append((value&127)|128);value>>=7
        out.append(value);return bytes(out)
    name='test.playable';encoded=name.encode();fixture=uint(1976)+uint(6)+uint(len(encoded))+encoded+uint(8)
    reference={'terminalSpan':[0,len(fixture)],'fieldSpan':[3,len(fixture)-1],'mask':6,'nativeType':8}
    terminal_check(fixture,reference,name)
    extended=deepcopy(reference);extended['terminalSpan'][1]+=1
    reject('native terminal trailing byte',lambda:terminal_check(fixture+b'\x00',extended,name))
    truncated=deepcopy(reference);truncated['terminalSpan'][1]-=1
    reject('native terminal truncated type',lambda:terminal_check(fixture[:-1],truncated,name))
    reject('native terminal literal differs',lambda:terminal_check(fixture,reference,'wrong.playable'))
    reject('native terminal wrong discriminator',lambda:terminal_check(bytes([0])+fixture[1:],reference,name))
    wrong=deepcopy(reference);wrong['mask']=63
    reject('native opaque terminal mask',lambda:terminal_check(fixture,wrong,name))
    return {'negativeCases':len(tests),'rejected':tests}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=SITE)
    parser.add_argument('--data',type=Path)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--audit',type=Path)
    parser.add_argument('--native-inputs',type=Path)
    parser.add_argument('--installed-root',type=Path)
    parser.add_argument('--dist',type=Path)
    parser.add_argument('--publication-report',type=Path)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args();repo=args.repo.resolve();path=args.data or repo/'data/public-snapshot-native-corroboration.json';raw=path.read_bytes()
    require(sha(raw)==OVERLAY_SHA and b'\r'not in raw,'Exact compact UTF8 LF public payload changed')
    data=json.loads(raw);references=source_check(repo,data)
    checks={'source':{'exactPairs':len(references),'scenes':1400,'sharedNativeSources':239,'newBodies':0,'scope':'Exact base/root/owner/reference joins and immutable overlay proof pin','callerEditionStatus':UNKNOWN}}
    require(not args.installed_root or args.audit,'Current native input replay requires frozen --audit')
    if args.audit:checks['actual']=audit_check(repo,data,args.audit,args.native_inputs,args.installed_root)
    if args.self_test:checks['selfTests']=self_tests(repo,data)
    if args.dist:checks['dist']=dist_check(repo,data,args.dist,args.publication_report)
    result={'status':'PASS','verifierSha256':file_sha(Path(__file__)),'publicPayloadSha256':sha(raw),'checks':checks}
    if args.report:args.report.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
