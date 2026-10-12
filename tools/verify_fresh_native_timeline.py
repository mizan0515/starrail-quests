"""Independent stdlib verification of fresh native Timeline reader originals.

Uses closed raw object/inventory receipts, never producer imports or compiled
game execution. Resource limits are derived from exact serialized widths.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
import tarfile
from html.parser import HTMLParser
from html import escape
from urllib.parse import unquote

HASH = re.compile(r'^[0-9a-f]{64}$')
MINIMUM_CLIP_FIELDS = (60, 32, 32, 8, 4, 12, 4, 8, 16, 4)
MINIMUM_CLIP_BYTES = sum(MINIMUM_CLIP_FIELDS)
DOMAINS = {
    'PlaySimpleTalkClip': ('SPOKEN', 'PlaySimpleTalkClip.Config.TalkSentenceID'),
    'BPTalkClip': ('SPOKEN', 'BPTalkClip.TalkSentenceID'),
    'ScreenTransferTextClip': ('SCREEN_TEXT', 'ScreenTransferTextClip.SentenceID'),
    'SimpleTalkMarkerClip': ('NON_SPOKEN_OPTION_REFERENCE', 'SimpleTalkMarkerClip.ReferenceOptionTalkID'),
}
TRACK_CLASSES = {'PlaySimpleTalkTrack', 'BPTalkTrack', 'PlayScreenTransferTrack', 'ShowDialogTrack', 'PropSDFTextTrack', 'GroupTrack'}
NAMESPACES = {'TimelineAsset': 'UnityEngine.Timeline', 'GroupTrack': 'UnityEngine.Timeline',
              'PlaySimpleTalkClip': 'RPGTools.Timeline', 'PlaySimpleTalkTrack': 'RPGTools.Timeline',
              'SimpleTalkMarkerClip': 'RPGTools.Timeline', 'ScreenTransferTextClip': 'RPGTools.Timeline',
              'PlayScreenTransferTrack': 'RPGTools.Timeline',
              'BPTalkClip': 'RPGTools.Timeline.BattlePerform', 'BPTalkTrack': 'RPGTools.Timeline.BattlePerform'}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def pointer(value, path):
    for key in path.split('/')[1:]:
        key = key.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def relative(path):
    require(isinstance(path, str) and path and not path.startswith(('/', '\\'))
            and ':' not in path and '\\' not in path and '..' not in path.split('/'), 'Relative source domain')


def public_safe(value, key=''):
    if isinstance(value, dict):
        for name, child in value.items():
            public_safe(child, name)
    elif isinstance(value, list):
        for child in value:
            public_safe(child, key)
    elif isinstance(value, str):
        require(not re.search(r'(?i)(?:[a-z]:[/\\]|file://|\\\\|\.codex-work[/\\])', value), 'Private path in public native Timeline')
        if key in ('Hash', 'hash', 'speaker_hash', 'nameHash'):
            require(value.isdecimal() and int(value) < 2 ** 64, 'Public UInt64 hash precision/domain')
        if key == 'pathID':
            require(re.fullmatch(r'-?\d+', value) and -(2 ** 63) <= int(value) < 2 ** 63, 'Public signed native pathID precision/domain')
    elif key in ('Hash', 'hash', 'speaker_hash', 'nameHash', 'pathID'):
        raise ValueError('Public 64-bit identifier must remain a string')


class Native:
    """Bounded Unity primitive reader; own field records and exact EOF."""
    def __init__(self, raw):
        self.raw = raw
        self.at = 0
        self.fields = []

    def take(self, size):
        require(type(size) is int and 0 <= size <= len(self.raw) - self.at, 'Native object byte bounds')
        out = self.raw[self.at:self.at + size]
        self.at += size
        return out

    def num(self, kind, extrapolation=False):
        out = struct.unpack('<' + kind, self.take(struct.calcsize('<' + kind)))[0]
        if kind in ('f', 'd'):
            require(not math.isnan(out), 'Native NaN forbidden')
            if extrapolation:
                require(out >= 0, 'Native extrapolation negative')
                return 'Infinity' if math.isinf(out) else out
            require(math.isfinite(out), 'Native nonfinite scalar forbidden')
        return out

    def align(self):
        size = (-self.at) % 4
        require(self.take(size) == bytes(size), 'Native nonzero alignment')

    def boolean(self):
        out = self.num('B')
        require(out in (0, 1), 'Declared native boolean domain')
        self.align()
        return bool(out)

    def count(self, minimum=1):
        out = self.num('i')
        require(0 <= out <= (len(self.raw) - self.at) // minimum, 'Native array count exceeds byte-derived bound')
        return out

    def string(self):
        value = self.take(self.count()).decode('utf8')
        self.align()
        return value

    def pptr(self):
        return {'fileID': self.num('i'), 'pathID': str(self.num('q'))}

    def pointers(self):
        return [self.pptr() for _ in range(self.count(12))]

    def curve(self):
        keys = []
        for _ in range(self.count(28)):
            keys.append({name: self.num(kind) for name, kind in
                         [('time', 'f'), ('value', 'f'), ('inSlope', 'f'), ('outSlope', 'f'),
                          ('weightedMode', 'i'), ('inWeight', 'f'), ('outWeight', 'f')]})
        return {'keys': keys, 'preInfinity': self.num('i'), 'postInfinity': self.num('i'), 'rotationOrder': self.num('i')}

    def field(self, name, fn):
        start = self.at
        value = fn()
        self.fields.append({'field': name, 'span': [start, self.at], 'value': value})
        return value

    def base(self, obj):
        self.field('MonoBehaviour.m_GameObject', self.pptr)
        self.field('MonoBehaviour.m_Enabled', self.boolean)
        script = self.field('MonoBehaviour.m_Script', self.pptr)
        name = self.field('MonoBehaviour.m_Name', self.string)
        require(script == {'fileID': obj['scriptPointer']['m_FileID'], 'pathID': str(obj['scriptPointer']['m_PathID'])},
                'Actual MonoBehaviour script pointer differs')
        require(name == obj['name'] and self.at == obj['baseBytesRead'], 'Actual MonoBehaviour name/base byte span differs')

    def eof(self):
        require(self.at == len(self.raw), 'Native full object EOF differs')


def clip_in_track(reader, track_id):
    start = reader.at
    values = {}
    for name, kind in [('m_Version', 'i'), ('m_Start', 'd'), ('m_ClipIn', 'd')]:
        values[name] = reader.field('TimelineClip.' + name, lambda kind=kind: reader.num(kind))
    require(values['m_Version'] == 1, 'Native TimelineClip version')
    values['m_Asset'] = reader.field('TimelineClip.m_Asset', reader.pptr)
    for name in ('m_Duration', 'm_TimeScale'):
        values[name] = reader.field('TimelineClip.' + name, lambda: reader.num('d'))
    parent = reader.field('TimelineClip.m_ParentTrack', reader.pptr)
    require(parent == {'fileID': 0, 'pathID': str(track_id)}, 'Native clip parent PPtr differs')
    for name in ('m_EaseInDuration', 'm_EaseOutDuration', 'm_BlendInDuration', 'm_BlendOutDuration'):
        reader.field('TimelineClip.' + name, lambda: reader.num('d'))
    for name in ('m_MixInCurve', 'm_MixOutCurve'):
        reader.field('TimelineClip.' + name, reader.curve)
    for name in ('m_BlendInCurveMode', 'm_BlendOutCurveMode'):
        require(reader.field('TimelineClip.' + name, lambda: reader.num('i')) in (0, 1), 'Native blend enum domain')
    reader.field('TimelineClip.m_ExposedParameterNames', lambda: [reader.string() for _ in range(reader.count(4))])
    reader.field('TimelineClip.m_AnimationCurves', reader.pptr)
    reader.field('TimelineClip.m_Recordable', reader.boolean)
    for name in ('m_PostExtrapolationMode', 'm_PreExtrapolationMode'):
        require(reader.field('TimelineClip.' + name, lambda: reader.num('i')) in range(5), 'Native extrapolation mode domain')
    for name in ('m_PostExtrapolationTime', 'm_PreExtrapolationTime'):
        reader.field('TimelineClip.' + name, lambda: reader.num('d', extrapolation=True))
    values['m_DisplayName'] = reader.field('TimelineClip.m_DisplayName', reader.string)
    values['span'] = [start, reader.at]
    return values


def decode_track(raw, obj, kind):
    require(kind in TRACK_CLASSES, 'Unsupported native track class')
    reader = Native(raw)
    reader.base(obj)
    require(reader.field('TrackAsset.m_Version', lambda: reader.num('i')) == 3, 'Native TrackAsset version')
    reader.field('TrackAsset.m_AnimClip', reader.pptr)
    for name in ('m_Toggled', 'm_DeleteItemLocked', 'm_AddItemLocked', 'm_DragTrackLocked',
                 'm_DeleteTrackLocked', 'm_AddTrackLocked', 'm_Locked', 'm_Muted'):
        reader.field('TrackAsset.' + name, reader.boolean)
    reader.field('TrackAsset.m_CustomPlayableFullTypename', reader.string)
    reader.field('TrackAsset.m_Curves', reader.pptr)
    parent = reader.field('TrackAsset.m_Parent', reader.pptr)
    children = reader.field('TrackAsset.m_Children', reader.pointers)
    reader.field('TrackAsset.CharacterUniqueName', reader.string)
    reader.field('TrackAsset.NodePath', reader.string)
    count = reader.field('TrackAsset.m_Clips.Count', lambda: reader.count(MINIMUM_CLIP_BYTES))
    clips = [clip_in_track(reader, obj['pathID']) for _ in range(count)]
    reader.field('TrackAsset.m_Markers.m_Objects', reader.pointers)
    reader.field('TrackAsset.m_isTrackNameGUIReadOnly', reader.boolean)
    if kind == 'GroupTrack':
        reader.field('GroupTrack.customData', reader.pptr)
    reader.eof()
    return {'fields': reader.fields, 'parent': parent, 'children': children, 'clips': clips, 'eof': reader.at}


def decode_root(raw, obj):
    reader = Native(raw)
    reader.base(obj)
    require(reader.field('TimelineAsset.m_Version', lambda: reader.num('i')) == 0, 'Native TimelineAsset version')
    reader.field('TimelineAsset.m_BindingData', reader.pptr)
    tracks = reader.field('TimelineAsset.m_Tracks', reader.pointers)
    reader.field('TimelineAsset.m_FixedDuration', lambda: reader.num('d'))
    fps = reader.field('TimelineAsset.m_EditorSettings.m_Framerate', lambda: reader.num('f'))
    require(0 < fps <= 1000, 'Native root frame rate domain')
    require(reader.field('TimelineAsset.m_DurationMode', lambda: reader.num('i')) in (0, 1, 2), 'Native root duration mode')
    reader.field('TimelineAsset.m_MarkerTrack', reader.pptr)
    reader.eof()
    return {'fields': reader.fields, 'tracks': tracks, 'eof': reader.at}


SPECS = {
    'PlaySimpleTalkClip': [('UseTextOption', 'i'), ('Config.TextSpeed', 'f'), ('Config.TalkSentenceID', 'I'),
        ('Config.ProtectTime', 'f'), ('Config.ForceToNextTime', 'f'), ('Config.TyperType', 'i'),
        ('Style.StyleType', 'i'), ('Style.SpeakerID', 's'), ('BlackMask', 'b'), ('BlackMaskColor', 'i'),
        ('NeedFadeBlackMask', 'b'), ('BlackMaskFadeDuration', 'f'), ('ProtectByVoice', 'b'),
        ('ForceToNextOnProtectEnd', 'b'), ('HaveProtectTime', 'b'), ('UniqueName', 's'), ('Use3DVoice', 'b'), ('UseDiscussionMouthTalk', 'b')],
    'BPTalkClip': [('TalkSentenceID', 'I'), ('HaveProtectTime', 'b'), ('ProtectTime', 'f'), ('ProtectByVoice', 'b'),
                   ('ForceToNextTime', 'f'), ('Style.StyleType', 'i'), ('Style.SpeakerID', 's')],
    'ScreenTransferTextClip': [('SentenceID', 'I'), ('CanPauseTimeline', 'b'), ('NotAuto', 'b'), ('PlayVoice', 'b')],
    'SimpleTalkMarkerClip': [('HideAll', 'b'), ('DontHidePanels', 'i'), ('BlackMask', 'b'), ('BlackMaskColor', 'i'),
                              ('NeedFadeBlackMask', 'b'), ('BlackMaskFadeDuration', 'f'), ('ReferenceOptionTalkID', 'I')],
}


def decode_asset(raw, obj, kind):
    require(kind in DOMAINS, 'Unsupported native dialogue class/domain')
    reader = Native(raw)
    reader.base(obj)
    for name, code in SPECS[kind]:
        fn = reader.boolean if code == 'b' else reader.string if code == 's' else lambda code=code: reader.num(code)
        value = reader.field(kind + '.' + name, fn)
        if name in ('UseTextOption', 'Config.TyperType', 'Style.StyleType'):
            require(value in range(3), 'Native text/style enum domain')
        if name == 'BlackMaskColor':
            require(value in (0, 1), 'Native blackmask enum domain')
    reader.eof()
    return {'fields': reader.fields, 'eof': reader.at}


def normalize_fields(value):
    """Only lossless pathID precision normalization; no numeric interpretation."""
    if isinstance(value, dict):
        return {key: str(child) if key == 'pathID' else normalize_fields(child) for key, child in value.items()}
    if isinstance(value, list):
        return [normalize_fields(child) for child in value]
    return value


def raw_object(folder, cab, inventory, proof):
    pathid = int(proof['pathID'])
    objects = {int(o['pathID']): o for o in inventory['objects']}
    obj = objects[pathid]
    require(obj['classID'] == 114 and obj['byteStart'] == proof['byteStart'] and obj['byteSize'] == proof['byteSize']
            and obj['sha256'] == proof['sha256'], 'Actual object inventory/span/hash differs')
    script = obj['scriptPointer']
    require(script['m_FileID'] == 0 and int(script['m_PathID']) in objects, 'Actual local MonoScript PPtr absent')
    mono = objects[int(script['m_PathID'])]
    require(mono['script']['m_ClassName'] == proof['class'], 'Actual MonoScript native class differs')
    if proof['class'] in NAMESPACES:
        require(mono['script']['m_Namespace'] == NAMESPACES[proof['class']], 'Actual inventory-bound MonoScript namespace differs')
    raw = (folder / (cab + '-' + str(pathid) + '.bin')).read_bytes()
    require(len(raw) == proof['byteSize'] and sha(raw) == proof['sha256'], 'Actual raw object byte identity differs')
    return raw, obj


def audit_records(paths):
    for path in paths:
        with path.open(encoding='utf8') as file:
            for line in file:
                if line.strip():
                    yield json.loads(line)


def minimal_clip_fixture():
    """One 180-byte clip with empty names/curves; this is a wire fixture."""
    out = struct.pack('<iddiqddiq', 1, 0.0, 0.0, 0, 2, 1.0, 1.0, 0, 1)
    out += bytes(32)  # Four blend/ease doubles.
    out += bytes(32)  # Two empty AnimationCurve: count + three ints.
    out += bytes(8 + 4 + 12 + 4 + 8 + 16 + 4)
    require(len(out) == MINIMUM_CLIP_BYTES == 180, 'Clip minimum fixture arithmetic differs')
    return out


def guard_tests():
    tests = []
    def reject(name, fn):
        try:
            fn()
        except (ValueError, IndexError, UnicodeError, struct.error):
            tests.append(name)
            return
        raise ValueError('Native guard mutation accepted: ' + name)
    widths = []
    for width in (180, 204, 260):
        extra = width - 180
        raw = minimal_clip_fixture()[:176] + struct.pack('<i', extra) + b'x' * extra
        reader = Native(raw)
        clip_in_track(reader, 1)
        reader.eof()
        widths.append(len(raw))
        reject('clip-' + str(width) + ' truncation', lambda raw=raw: clip_in_track(Native(raw[:-1]), 1))
        def trailing(raw=raw):
            reader = Native(raw + b'\0')
            clip_in_track(reader, 1)
            reader.eof()
        reject('clip-' + str(width) + ' trailing bytes', trailing)
    two_short = struct.pack('<i', 2) + minimal_clip_fixture()[:176] + struct.pack('<i', 24) + b'x' * 24
    two_short += minimal_clip_fixture()[:176] + struct.pack('<i', 80) + b'x' * 80
    reader = Native(two_short)
    require(reader.count(MINIMUM_CLIP_BYTES) == 2, 'Byte-derived180 guard rejects legitimate204/260 pair')
    for _ in range(2):
        clip_in_track(reader, 1)
    reader.eof()
    reject('old296 minimum rejects valid204/260 pair', lambda: Native(two_short).count(296))
    for value in (-1, 3, 2147483647):
        reject('byte bound count ' + str(value), lambda value=value: Native(struct.pack('<i', value) + two_short[4:]).count(180))
    bad = bytearray(minimal_clip_fixture())
    bad[148] = 2
    reject('declared bool byte2', lambda: clip_in_track(Native(bytes(bad)), 1))
    bad = bytearray(minimal_clip_fixture())
    struct.pack_into('<d', bad, 4, float('nan'))
    reject('clip start NaN', lambda: clip_in_track(Native(bytes(bad)), 1))
    bad = bytearray(minimal_clip_fixture())
    struct.pack_into('<q', bad, 52, 999)
    reject('clip parent PPtr mismatch', lambda: clip_in_track(Native(bytes(bad)), 1))
    return {'guardMinimumFields': list(MINIMUM_CLIP_FIELDS), 'guardMinimumBytes': 180,
            'positiveClipWidths': widths, 'positiveShortClipCount': 2, 'negativeGuardTests': tests}



PROJECTION_SHA = 'cfb05b93a7fbba8057af256dea9da7d49c213b9401eb05b1002d9e6d33d06c9b'
SCENE_SET_SHA = 'e5f910dffb10864b9b8b6cd6cdcb52797da25c93ac3dfdfcb2f58dd22548ce55'
ID_SET_SHA = '77c6cbaac20be8dac0efdf088bd609a9b7290e9a7da7e7a2dd0118f816ebf5c8'


def sequence_hash(value):
    return sha(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf8'))


def scene_rows(scene):
    # Exact renderer order: serialized clip time, signed Int64 track, clip index.
    return sorted(scene['rows'] + scene.get('optionReferences', []),
                  key=lambda r: (r['start'], int(r['track']['pathID']), r['trackClipIndex']))


def readable(raw):
    text = raw.replace('\\n', '\n').replace('\u00a0', ' ')
    text = re.sub(r'\{RUBY_[BE]#[^}]*\}', '', text)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    return re.sub(r'</?(?:color|size|b|i|u|align|voffset|indent|line-height|unbreak)(?:=[^>]*)?>', '', text, flags=re.I)

def source_validate(repo, data, inverse=None):
    public_safe(data)
    require(data['schema'] == 'starrail-native-fresh-timeline-dialogue.v1', 'Fresh public Timeline schema')
    require(data['evidence']['officialKorean']['kind'] == 'OFFICIAL_GAME_KOREAN_TEXTMAP', 'Fresh Korean edition domain')
    files, memberships = {}, {}
    roles, ids, used_sources = Counter(), set(), set()
    scene_ids, occurrences = set(), set()
    for scene in data['scenes']:
        require(re.fullmatch(r'fresh-timeline-[0-9a-f]{20}', scene['id']) and scene['id'] not in scene_ids,
                'Fresh scene kind/duplicate identity')
        scene_ids.add(scene['id'])
        relative(scene['source'])
        require(scene_rows(scene), 'Fresh source has no readable rows')
        require(scene['source'] == scene['proof']['container']['key'], 'Exact canonical native source key differs')
        expected_status = 'UNOWNED_NATIVE_TIMELINE' if not scene['owners'] else 'ONE_EXPLICIT_OWNER' if len(scene['owners']) == 1 else 'MULTIPLE_EXPLICIT_OWNERS'
        require(scene['ownerStatus'] == expected_status, 'Fresh explicit owner status differs')
        proof = scene['proof']
        receipt, root, container = proof['receipt'], proof['root'], proof['container']
        require(root['class'] == 'TimelineAsset' and str(container['pathID']) == root['pathID'] and container['fileID'] == 0,
                'Fresh direct container/TimelineAsset root domain')
        require(HASH.fullmatch(root['sha256']) and HASH.fullmatch(receipt['cabSha256'])
                and HASH.fullmatch(receipt['sourceBlockSha256']), 'Fresh native root/source SHA domain')
        require(type(receipt['bundleOffset']) is int and receipt['bundleOffset'] >= 0
                and type(receipt['bundleBytes']) is int and receipt['bundleBytes'] > 0,
                'Fresh bundle byte bounds')
        owner_keys = {owner['mission'] for owner in scene['owners']}
        require(len(owner_keys) == len(scene['owners']), 'Duplicate explicit fresh owners')
        for owner in scene['owners']:
            require(set(owner) <= {'mission', 'canonicalMission', 'title'}, 'Unexpected inferred fresh owner/region field')
            name = 'data/documents/' + owner['canonicalMission'] + '.json'
            relative(name)
            if name not in memberships:
                memberships[name] = load(repo / name)
            doc = memberships[name]
            require(doc['id'] == owner['canonicalMission'] and owner['mission'] in doc.get('missionParts', [doc['id']]),
                    'Fresh mission actual membership differs')
        source_owners = set()
        for ref in proof['references']:
            key = str(ref['sourceIndex'])
            source = data['sourceProofs'][key]
            used_sources.add(key)
            relative(source['logicalJsonPath'])
            require(HASH.fullmatch(source['entrySha256']) and type(source['consumedBytes']) is int
                    and source['consumedBytes'] > 0, 'Fresh caller source SHA/EOF domain')
            match, = source['catalogMatches']
            require(source['consumedBytes'] == match['length'] and match['offset'] >= 0
                    and match['offset'] + match['length'] <= match['packExpectedBytes'], 'Fresh caller whole source bounds')
            span = ref['fieldSpan']
            require(span['pointer'] == ref['pointer'] and 0 <= span['start'] < span['end'] <= source['consumedBytes'],
                    'Fresh caller TimelineName typed field span bounds')
            require(ref['pointer'].endswith('/TimelineName'), 'Fresh caller field is not declared TimelineName')
            chain = source['ownerChain']
            require(chain and chain[0]['kind'] == 'EXPLICIT_MAIN_MISSION_ID', 'Fresh owner chain seed domain')
            seed = chain[0]
            require(source['mission'] == 'quest-' + str(seed['canonicalMissionId']) and source['mission'] in owner_keys,
                    'Fresh source owner/mission explicit ID differs')
            name = seed['membershipSource']
            relative(name)
            require(name == 'data/documents/quest-' + str(seed['canonicalMissionId']) + '.json', 'Fresh canonical membership source domain')
            raw = (repo / name).read_bytes()
            require(sha(raw) == seed['membershipSha256'] and pointer(json.loads(raw), seed['membershipPointer']) == 'quest-' + str(seed['missionId']),
                    'Fresh membership pointer/source SHA differs')
            require(chain[-1].get('target') == source['logicalJsonPath'], 'Fresh owner path does not reach caller source')
            for edge in chain:
                require(edge['kind'] in ('EXPLICIT_MAIN_MISSION_ID', 'EXPLICIT_JSON_PATH', 'EXPLICIT_PERFORMANCE_LOOKUP'),
                        'Unsupported fresh owner edge domain')
                relative(edge['source'])
                require(HASH.fullmatch(edge['sourceSha256']), 'Fresh owner source SHA domain')
                if edge['kind'] == 'EXPLICIT_PERFORMANCE_LOOKUP':
                    require(edge['lookupScope'] == 'TYPED_PRIMARY_TABLE'
                            and edge['performanceType'] in ('A', 'C', 'D', 'E'), 'Fresh performance caller/table domain')
                    require(edge['tableSource'] == 'ExcelOutput/Performance' + ('DS' if edge['performanceType'] == 'D' else edge['performanceType']) + '.json',
                            'Fresh performance type/table identity differs')
            context = ref['context']
            parent_pointer = ref['pointer'].rsplit('/', 1)[0]
            require(context['typedContainer'] == {'type': 'RPG.GameCore.PlayTimeline', 'pointer': parent_pointer}
                    and context['typedAncestors'][-1]['pointer'] == parent_pointer
                    and context['typedAncestors'][-1]['type'] == 'RPG.GameCore.PlayTimeline'
                    and context['typedAncestors'][-1]['branchOrChildKey'] == 'TimelineName',
                    'Fresh declared native TimelineName caller domain differs')
            relative(context['typedAncestors'][-1]['contextFields']['TimelineName'])
            require(ref['archiveTerminalStatus'] in ('EXACT_ARCHIVED_TERMINAL_CALL_PASS',
                    'ARCHIVE_TERMINAL_SOURCE_UNAVAILABLE_NATIVE_EOF_AND_EXACT_OWNER_TABLE_ROUTE_PASS'),
                    'Fresh terminal archive boundary missing')
            source_owners.add(source['mission'])
        require(source_owners == owner_keys, 'Fresh owner has no exact native caller source')
        for match in scene.get('existingRootMatches', []):
            require(match['sceneId'] in scene['existingSceneIds'], 'Existing native root identity absent')
        anchors = set()
        previous_time = -1
        for row in scene_rows(scene):
            tid = row['talkId']
            obj, field, track = row['object'], row['idField'], row['track']
            require(type(tid) is int and 0 < tid < 2 ** 32 and DOMAINS.get(obj['class']) == (row['role'], field['field'])
                    and field['value'] == tid, 'Fresh clip class/literal UInt32/role domain')
            require(row['anchor'] not in anchors and re.fullmatch(('reference-' if row['role'] == 'NON_SPOKEN_OPTION_REFERENCE' else 'talk-') + str(tid) + r'-[1-9]\d*', row['anchor']),
                    'Fresh original occurrence anchor domain')
            anchors.add(row['anchor'])
            require(all(type(row[key]) in (int, float) and math.isfinite(row[key]) for key in ('start', 'duration'))
                    and row['start'] >= previous_time and row['duration'] > 0, 'Fresh static source clip time/order differs')
            previous_time = row['start']
            start, end = field['span']
            require(type(start) is int and type(end) is int and 0 <= start < end <= obj['byteSize'] and end - start == 4,
                    'Fresh literal ID width/span differs')
            require(HASH.fullmatch(obj['sha256']) and HASH.fullmatch(track['sha256'])
                    and track['class'] in TRACK_CLASSES and type(row['trackClipIndex']) is int and row['trackClipIndex'] >= 0,
                    'Fresh object/track source domain')
            route = row['parentRoute']
            require(route and route[0] == track['pathID'] and route[-1] == root['pathID'] and len(route) == len(set(route)),
                    'Fresh native PPtr route endpoints/cycle')
            occurrence = (receipt['cabSha256'], root['pathID'], obj['pathID'], track['pathID'], row['trackClipIndex'])
            require(occurrence not in occurrences, 'Duplicate adopted exact fresh native occurrence')
            occurrences.add(occurrence)
            join = data['joins'][str(tid)]
            src = join['preservedSource']
            relative(src['file'])
            require(src['file'].startswith('data/dialogues/'), 'Fresh preserved Korean source domain')
            if src['file'] not in files:
                raw = (repo / src['file']).read_bytes()
                files[src['file']] = (sha(raw), json.loads(raw))
            h, corpus = files[src['file']]
            original = pointer(corpus, src['pointer'])
            require(h == src['sha256'] and original['talk_id'] == tid and isinstance(join['raw'], str),
                    'Fresh original Korean source/hash/ID differs')
            normalized = readable(join['raw'])
            require(normalized == original['text'] and (readable(join['speakerRaw']) or '화자 미지정') == original['speaker'], 'Fresh raw Korean projection differs')
            if inverse is not None:
                target = '대화/연출-' + scene['id'] + '.html#' + row['anchor']
                require(any(link['url'] == target and link['source'] == scene['source'] and link['role'] == row['role']
                            for link in inverse['readerLinks'].get(str(tid), [])), 'Fresh exact inverse original anchor absent')
            roles[row['role']] += 1
            ids.add(tid)
    require(set(data['joins']) == {str(tid) for tid in ids} and set(data['sourceProofs']) == used_sources,
            'Fresh adopted join/source proof partition differs')
    require(data['counts']['sceneCount'] == len(scene_ids) and data['counts']['includedUniqueIDs'] == len(ids)
            and all(data['counts']['occurrences']['included_' + role] == count for role, count in roles.items()),
            'Fresh declared adopted counts differ')
    require(sequence_hash(sorted(scene_ids)) == SCENE_SET_SHA and sequence_hash(sorted(ids)) == ID_SET_SHA,
            'Frozen fresh scene/ID cohort differs')
    return {'adoptedScenes': len(scene_ids), 'adoptedOriginals': sum(roles.values()), 'adoptedTalkIds': len(ids),
            'roles': dict(roles), 'preservedKoreanFiles': len(files), 'exactCallerSources': len(used_sources)}


class Primitive:
    """Independent bounded unsigned varint/UTF8 reader for literal callers."""
    def __init__(self, raw, start=0, end=None):
        self.raw, self.at, self.end = raw, start, len(raw) if end is None else end
        require(0 <= start <= self.end <= len(raw), 'Primitive byte bounds')

    def take(self, count):
        require(type(count) is int and 0 <= count <= self.end - self.at, 'Primitive truncated bytes')
        raw = self.raw[self.at:self.at + count]
        self.at += count
        return raw

    def uint(self, bits=32):
        value = 0
        for shift in range(0, bits + 7, 7):
            byte = self.take(1)[0]
            value |= (byte & 127) << shift
            if byte < 128:
                require(value < 2 ** bits and (not shift or byte != 0), 'Canonical varint width differs')
                return value
        raise ValueError('Varint continuation exceeds domain')

    def string(self):
        return self.take(self.uint()).decode('utf8')

    def count(self):
        encoded = self.uint()
        count = (encoded >> 1) ^ -(encoded & 1)
        require(0 <= count <= self.end - self.at, 'Array count exceeds remaining bytes')
        return count

    def eof(self):
        require(self.at == self.end, 'Primitive exact EOF differs')


def same_object(left, right):
    for key in ('pathID', 'class', 'sha256', 'byteStart', 'byteSize'):
        require(str(left[key]) == str(right[key]), 'Exact native object identity/span differs: ' + key)
    require(left['scriptPointer']['m_FileID'] == right['scriptPointer']['m_FileID']
            and str(left['scriptPointer']['m_PathID']) == str(right['scriptPointer']['m_PathID']),
            'Exact native object MonoScript identity differs')


def caller_replay(data, directory):
    path = directory / 'fresh-native-source-replay.json'
    raw = path.read_bytes()
    require(sha(raw) == data['evidence']['sourceReplaySha256'], 'Closed whole-source replay SHA differs')
    replay = json.loads(raw)
    require(replay['decoderSha256'] == data['evidence']['nativeDecoderSha256'], 'Closed caller decoder SHA differs')
    packs, sources, checked = {}, {}, set()
    for key, public in data['sourceProofs'].items():
        receipt = replay['sources'][key]
        require(receipt['sourceProof'] == public and receipt['status'] == 'WHOLE_NATIVE_EOF_PASS',
                'Public/closed whole native caller proof differs')
        pack_path = Path(receipt['packPath'])
        pack_key = (str(pack_path), public['callerPack']['sha256'])
        if pack_key not in packs:
            body = pack_path.read_bytes()
            require(sha(body) == pack_key[1] and len(body) == public['callerPack']['bytes'], 'Actual cached caller pack SHA/bytes differs')
            packs[pack_key] = body
        match, = public['catalogMatches']
        body = packs[pack_key][match['offset']:match['offset'] + match['length']]
        require(sha(body) == public['entrySha256'] and len(body) == public['consumedBytes'], 'Actual cached native caller entry SHA/whole bytes differs')
        spans = {field['pointer']: field for field in receipt['fieldSpans']}
        require(len(spans) == len(receipt['fieldSpans']) and spans[''] == {'pointer': '', 'start': 0, 'end': len(body)},
                'Closed native source full EOF/span partition differs')
        for span in spans.values():
            require(0 <= span['start'] <= span['end'] <= len(body), 'Closed native source field bounds differ')
            pointer(receipt['fields'], span['pointer'])
        sources[key] = (body, receipt['fields'], spans)
    for scene in data['scenes']:
        for ref in scene['proof']['references']:
            key = ref['sourceIndex']
            body, fields, spans = sources[key]
            require(spans[ref['pointer']] == ref['fieldSpan'], 'Actual caller field span differs')
            parent_pointer = ref['pointer'].rsplit('/', 1)[0]
            parent = pointer(fields, parent_pointer)
            context = ref['context']['typedAncestors'][-1]['contextFields']
            require(parent == dict(context, **{'$type': 'RPG.GameCore.PlayTimeline'}), 'Closed exact typed caller context differs')
            parent_span = spans[parent_pointer]
            reader = Primitive(body, parent_span['start'], parent_span['end'])
            require(reader.uint() == 1976, 'Actual PlayTimeline discriminator differs')
            mask = reader.uint()
            require(mask == (14 if 'Parameters' in context else 6), 'Actual PlayTimeline field mask differs')
            start = reader.at
            require(reader.string() == context['TimelineName'] and (start, reader.at) == (ref['fieldSpan']['start'], ref['fieldSpan']['end']),
                    'Actual literal TimelineName UTF8/span differs')
            enum_span = spans[parent_pointer + '/Type']
            start = reader.at
            require(reader.uint() == context['Type']['observedSerializedEnum']
                    and (start, reader.at) == (enum_span['start'], enum_span['end']), 'Actual native Timeline Type enum/span differs')
            if mask & 8:
                require(context['Parameters'] == [] and reader.count() == 0, 'Unsupported active native Timeline parameters')
            reader.eof()
            checked.add((key, parent_pointer))
    return {'actualCachedCallerPacks': len(packs), 'actualCallerEntries': len(sources),
            'actualWholePlayTimelineCalls': len(checked),
            'wholeSourceBoundary': 'Immutable full-EOF receipt and entry bytes independently rebound; exact PlayTimeline terminal independently decoded',
            'callerEditionStatus': data['evidence']['callerEditionStatus']}


def native_guard_replay(data, directory):
    raw = (directory / 'fresh-track-guard-canaries.json').read_bytes()
    require(sha(raw) == data['evidence']['guardCanariesSha256'], 'Immutable track guard canary SHA differs')
    receipt = json.loads(raw)
    bound = receipt['resourceBound']
    require(bound['old'] == 296 and bound['correct'] == MINIMUM_CLIP_BYTES == 180
            and bound['fieldWidths'] == list(MINIMUM_CLIP_FIELDS) and bound['fieldLayoutUnchanged'] is True,
            'Closed guard correction field-width derivation differs')
    lengths, negative, whole = Counter(), 0, 0
    for case in receipt['canaries']:
        source = case['source']
        inv_raw = Path(source['inventory']).read_bytes()
        require(sha(inv_raw) == source['inventorySha256'], 'Guard source inventory SHA differs')
        inv = json.loads(inv_raw)
        cab, = [c for c in inv['cabs'] if c['name'] == source['cabName']]
        require(inv['sourceSha256'] == source['blockSha256'] and cab['sha256'] == source['cabSha256'], 'Guard source CAB/block receipt differs')
        raw, obj = raw_object(Path(source['objectFolder']), source['cabName'], cab, case['object'])
        actual = decode_track(raw, obj, case['object']['class'])
        spans = [clip['span'] for clip in actual['clips']]
        require(actual['eof'] == case['actualEOF'] and spans == case['clipSpans'], 'Actual guard clip fields/EOF spans differ')
        field, = [f for f in actual['fields'] if f['field'] == 'TrackAsset.m_Clips.Count']
        require(field == case['countField'], 'Actual guard typed count field differs')
        require(case['oldResourceBoundWouldReject'] is True
                and field['value'] > (len(raw) - field['span'][1]) // 296,
                'Actual repaired track was not rejected by prior296 bound')
        for start, end in spans:
            lengths[end - start] += 1
        for stop in set((obj['baseBytesRead'] - 1, field['span'][1] - 1, spans[-1][1] - 1, len(raw) - 1)):
            try:
                decode_track(raw[:stop], obj, case['object']['class'])
            except (ValueError, IndexError, UnicodeError, struct.error):
                negative += 1
            else:
                raise ValueError('Actual native guard track truncation accepted')
        whole += 1
    require(whole == 32, 'Closed repaired-track canary cohort differs')
    return {'actualRepairedTracksEOF': whole, 'actualSerializedClipWidths': {str(k): v for k, v in lengths.items()},
            'independentActualTrackTruncationRejections': negative, 'minimumWidth': MINIMUM_CLIP_BYTES}


def native_replay(data, directory):
    # Read a closed scope's JSONL once, index only exact native root identities.
    paths = []
    for receipt in data['evidence']['rawAudits']:
        relative(receipt['file'])
        path = directory / receipt['file']
        require(sha(path.read_bytes()) == receipt['sha256'], 'Immutable CAB route audit SHA differs')
        paths.append(path)
    wanted = {}
    def target_key(receipt, container, root):
        return receipt.get('cabSha256'), container['key'], str(root['pathID']), root['sha256']
    for scene in data['scenes']:
        proof = scene['proof']
        key = target_key(proof['receipt'], proof['container'], proof['root'])
        require(key not in wanted, 'Duplicate exact adopted Timeline root')
        wanted[key] = scene
    inventories, inventory_names, found, decoded_counts, native_rows = {}, set(), set(), Counter(), 0
    raw_record_counts = Counter()
    for record in audit_records(paths):
        raw_record_counts['records'] += 1
        receipt = record['sourceReceipt']
        for target in record['targets']:
            if target.get('status') != 'SUPPORTED_TYPED_ROOT_ROUTE_PASS':
                raw_record_counts['nonTimelineTargets'] += 1
                continue
            raw_record_counts['supportedRoots'] += 1
            key = target_key(receipt, target['rootContainer'], target['rootObject'])
            if key not in wanted:
                continue
            require(key not in found, 'Duplicate raw exact adopted root identity')
            found.add(key)
            scene = wanted[key]
            public = scene['proof']['receipt']
            for old, new in [('blockFile', 'blockFile'), ('blockSha256', 'sourceBlockSha256'), ('bundleOffset', 'bundleOffset'),
                             ('bundleBytes', 'bundleBytes'), ('cabName', 'cabName'), ('cabSha256', 'cabSha256')]:
                require(receipt[old] == public[new], 'Actual CAB/container receipt identity differs')
            inv_path = Path(receipt['inventory'])
            inventory_names.add(str(inv_path))
            if str(inv_path) not in inventories:
                if len(inventories) >= 8:
                    inventories.clear()
                raw = inv_path.read_bytes()
                require(sha(raw) == receipt['inventorySha256'], 'Actual CAB inventory SHA differs')
                inv = json.loads(raw)
                require(inv['sourceSha256'] == receipt['blockSha256'], 'Actual inventory source block receipt differs')
                inventories[str(inv_path)] = inv
            inv = inventories[str(inv_path)]
            cab, = [cab for cab in inv['cabs'] if cab['name'] == receipt['cabName']]
            require(cab['sha256'] == receipt['cabSha256'] and cab['bytes'] == receipt['cabBytes']
                    and cab['bundleOffset'] == receipt['bundleOffset'], 'Actual inventory CAB receipt differs')
            folder = Path(receipt['objectFolder'])
            same_object(scene['proof']['root'], target['rootObject'])
            require(normalize_fields(target['rootContainer']) == scene['proof']['container'], 'Actual canonical container export differs')
            raw, obj = raw_object(folder, receipt['cabName'], cab, target['rootObject'])
            root = decode_root(raw, obj)
            require(root['fields'] == normalize_fields(target['rootFields']) and root['eof'] == target['rootEOF'], 'Independent native root fields/EOF differ')
            decoded_counts['TimelineAsset'] += 1
            tracks, assets = {}, {}
            def track(pathid):
                pathid = str(pathid)
                if pathid not in tracks:
                    proof = target['trackProofs'].get(pathid)
                    if proof is None:
                        inventory_object, = [o for o in cab['objects'] if str(o['pathID']) == pathid]
                        script, = [o for o in cab['objects'] if o['pathID'] == inventory_object['scriptPointer']['m_PathID']]
                        require(script['script']['m_ClassName'] == 'GroupTrack', 'Unsupported native parent track schema')
                        proof = {'object': dict(inventory_object, **{'class': 'GroupTrack'})}
                    raw, obj = raw_object(folder, receipt['cabName'], cab, proof['object'])
                    actual = decode_track(raw, obj, proof['object']['class'])
                    require(('fields' not in proof or actual['fields'] == normalize_fields(proof['fields']))
                            and ('eof' not in proof or actual['eof'] == proof['eof']),
                            'Independent native track fields/whole EOF differ')
                    tracks[pathid] = actual
                    decoded_counts[proof['object']['class']] += 1
                return tracks[pathid]
            candidates = {}
            for candidate in target['rows'] + target.get('options', []):
                ckey = (str(candidate['object']['pathID']), str(candidate['track']['pathID']), candidate['trackClipIndex'])
                require(ckey not in candidates, 'Duplicate raw native clip occurrence')
                candidates[ckey] = candidate
            refs = {(r['source'], r['pointer'], r['entrySha256'],
                     r['timelineName'], r['mission']) for r in target['nativeReferences']}
            for reference in scene['proof']['references']:
                source = data['sourceProofs'][reference['sourceIndex']]
                literal = reference['context']['typedAncestors'][-1]['contextFields']['TimelineName']
                require((source['logicalJsonPath'], reference['pointer'], source['entrySha256'], literal, source['mission']) in refs,
                        'Exact native container lookup/caller/owner proof absent')
            for row in scene_rows(scene):
                ckey = (row['object']['pathID'], row['track']['pathID'], row['trackClipIndex'])
                candidate = candidates[ckey]
                same_object(row['object'], candidate['object'])
                same_object(row['track'], candidate['track'])
                require(candidate['role'] == row['role'] and str(row['talkId']) == str(candidate.get('talkID', candidate.get('referenceOptionTalkID')))
                        and candidate['parentRoute'] == row['parentRoute'], 'Exact raw native role/ID/parent route differs')
                asset_key = row['object']['pathID']
                if asset_key not in assets:
                    raw, obj = raw_object(folder, receipt['cabName'], cab, candidate['object'])
                    actual = decode_asset(raw, obj, row['object']['class'])
                    require(actual['fields'] == normalize_fields(candidate['assetFields']) and actual['eof'] == candidate['assetEOF'],
                            'Independent native clip fields/whole EOF differ')
                    assets[asset_key] = actual
                    decoded_counts[row['object']['class']] += 1
                field, = [f for f in assets[asset_key]['fields'] if f['field'] == row['idField']['field']]
                require(field == row['idField'], 'Independent typed literal UInt32 span/value differs')
                route = row['parentRoute']
                for child, parent in zip(route, route[1:]):
                    require(track(child)['parent'] == {'fileID': 0, 'pathID': parent}, 'Independent native parent PPtr differs')
                    parents_children = root['tracks'] if parent == route[-1] else track(parent)['children']
                    require({'fileID': 0, 'pathID': child} in parents_children, 'Independent reciprocal root/track PPtr absent')
                clip = track(row['track']['pathID'])['clips'][row['trackClipIndex']]
                require(clip == normalize_fields(candidate['timelineClip']) and clip['m_Asset'] == {'fileID': 0, 'pathID': asset_key}
                        and clip['m_Start'] == row['start'] and clip['m_Duration'] == row['duration'],
                        'Independent native clip asset PPtr/time/order differs')
                require(set(row['sourceIndices']) == {r['sourceIndex'] for r in scene['proof']['references']}, 'Native row caller usage partition differs')
                native_rows += 1
    require(found == set(wanted), 'Adopted exact native root absent in closed route census')
    require(raw_record_counts == {'records': 3272, 'supportedRoots': 3272, 'nonTimelineTargets': 3059}, 'Whole closed native input scope differs')
    return {'rawScope': dict(raw_record_counts), 'actualAdoptedNativeRoots': len(found), 'actualNativeOriginalOccurrences': native_rows,
            'actualFullEOFObjects': dict(decoded_counts), 'inventoryFiles': len(inventory_names),
            'scriptClassBoundary': 'MonoScript 115 class/namespace is inventory-SHA/block-SHA/CAB-SHA bound; only MonoBehaviour 114 has raw export bytes',
            'installedVersion': 'UNVERIFIED', 'unadoptedRoots': 68}


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def archive_replay(data, archive):
    require(file_sha(archive) == data['evidence']['archiveSha256'], 'Exact owner archive SHA differs')
    needed, terminals = {}, set()
    def need(name, expected):
        relative(name)
        require(name not in needed or needed[name] == expected, 'Conflicting archive source SHA')
        needed[name] = expected
    for source in data['sourceProofs'].values():
        for edge in source['ownerChain']:
            need(edge['source'], edge['sourceSha256'])
            if 'tableSource' in edge:
                need(edge['tableSource'], edge['tableSha256'])
    for scene in data['scenes']:
        for ref in scene['proof']['references']:
            if ref['archiveTerminalStatus'] == 'EXACT_ARCHIVED_TERMINAL_CALL_PASS':
                terminals.add(data['sourceProofs'][ref['sourceIndex']]['logicalJsonPath'])
    documents = {}
    with tarfile.open(archive, 'r|gz') as tar:
        for member in tar:
            if not member.isfile():
                continue
            name = member.name.split('/', 1)[-1]
            if name in needed or name in terminals:
                raw = tar.extractfile(member).read()
                require(name not in documents, 'Duplicate actual archived source')
                if name in needed:
                    require(sha(raw) == needed[name], 'Actual archive owner/table source SHA differs')
                documents[name] = json.loads(raw)
    require(set(documents) == set(needed) | terminals, 'Exact archived owner/table/available terminal absent')
    for source in data['sourceProofs'].values():
        seed, path, edge = source['ownerChain']
        require(pointer(documents[seed['source']], seed['pointer']) == seed['missionId'], 'Actual archived explicit main mission ID differs')
        require(path['source'] == seed['source'] and pointer(documents[path['source']], path['pointer']) == path['target']
                and edge['source'] == path['target'], 'Actual archive owner source path continuity differs')
        parent = pointer(documents[edge['source']], edge['pointer'].rsplit('/', 1)[0])
        performance_id = pointer(documents[edge['source']], edge['pointer'])
        table = documents[edge['tableSource']]
        require(parent['$type'] == 'RPG.GameCore.TriggerPerformance' and parent['PerformanceType'] == edge['performanceType']
                and performance_id == edge['performanceId'] and pointer(table, edge['idPointer']) == performance_id
                and pointer(table, edge['pathPointer']) == source['logicalJsonPath'], 'Actual typed performance source/table target differs')
        require({r['PerformancePath'] for r in table if r.get('PerformanceID') == performance_id} == {source['logicalJsonPath']},
                'Actual typed performance lookup ambiguous')
    unavailable, checked = set(), set()
    for scene in data['scenes']:
        for ref in scene['proof']['references']:
            source = data['sourceProofs'][ref['sourceIndex']]
            name = source['logicalJsonPath']
            if ref['archiveTerminalStatus'] != 'EXACT_ARCHIVED_TERMINAL_CALL_PASS':
                require(name not in documents, 'Declared archive unavailable terminal actually present')
                unavailable.add(name)
                continue
            parent = pointer(documents[name], ref['pointer'].rsplit('/', 1)[0])
            context = ref['context']['typedAncestors'][-1]['contextFields']
            require(parent['$type'] == 'RPG.GameCore.PlayTimeline' and parent['TimelineName'] == context['TimelineName'],
                    'Actual archived typed TimelineName caller differs')
            checked.add((name, ref['pointer']))
    return {'actualArchiveOwnerTableFiles': len(needed), 'actualArchiveTerminalFiles': len(terminals),
            'actualArchiveOwnerChains': len(data['sourceProofs']), 'actualArchivedTerminalCalls': len(checked),
            'archiveUnavailableTerminalSources': sorted(unavailable),
            'archiveUnavailableBoundary': 'Typed native caller EOF and exact archived owner/table route pass; archived terminal bytes unavailable'}


def official_replay(repo, data, directory):
    evidence = data['evidence']['officialKorean']
    files = {}
    def pack(name, expected_sha, size):
        relative(name)
        if name not in files:
            candidates = list(directory.rglob(name))
            valid = [p for p in candidates if p.stat().st_size == size and file_sha(p) == expected_sha]
            require(valid, 'Pinned actual official pack absent/SHA differs: ' + name)
            raw = valid[0].read_bytes()
            require(hashlib.md5(raw).hexdigest() == name[:-6], 'Official pack MD5 identity differs')
            files[name] = raw
        return files[name]
    catalog_paths = list(directory.rglob(evidence['catalogFile']))
    require(any(file_sha(p) == evidence['catalogSha256'] for p in catalog_paths), 'Actual official catalog SHA absent/different')
    # Catalog itself is pinned; rows below are independently consumed to EOF.
    ids = {int(key) for key in data['joins']}
    table = evidence['talkTable']
    raw = pack(table['file'], table['sha256'], table['size'])[table['offset']:table['offset'] + table['length']]
    require(sha(raw) == table['entrySha256'], 'Actual official TalkSentence entry SHA differs')
    reader = Primitive(raw)
    if raw[0] == 0:
        reader.take(1)
    total, talks = reader.count(), {}
    for _ in range(total):
        start = reader.at
        mask = reader.uint()
        require(mask & ~15 == 0, 'Unknown official TalkSentence active field')
        row = {}
        for bit, key in enumerate(('id', 'voice', 'speaker_hash', 'hash')):
            if mask & (1 << bit):
                if bit < 2:
                    row[key] = reader.uint()
                else:
                    reader.uint()
                    row[key] = str(reader.uint(64))
        if row.get('id') in ids:
            require(row['id'] not in talks, 'Duplicate actual official TalkSentence ID')
            talks[row['id']] = dict(row, offset=start, end=reader.at)
    reader.eof()
    require(total == table['rows'] and set(talks) == ids, 'Actual official full TalkSentence count/EOF/IDs differ')
    keys = {r['hash'] for r in talks.values()} | {r.get('speaker_hash', '0') for r in talks.values()}
    keys.discard('0')
    kr, entry = evidence['koreanPack'], evidence['entry']
    raw = pack(kr['file'], kr['sha256'], kr['size'])[entry['offset']:entry['offset'] + entry['length']]
    require(sha(raw) == entry['sha256'], 'Actual official Korean TextMap entry SHA differs')
    reader = Primitive(raw)
    total, texts, seen = reader.count(), {}, set()
    for _ in range(total):
        start = reader.at
        mask = reader.uint()
        require(mask & ~7 == 0, 'Unknown official TextMap active field')
        key, text = '0', ''
        if mask & 1:
            reader.uint()
            key = str(reader.uint(64))
        if mask & 2:
            text = reader.string()
        if mask & 4:
            reader.uint()
        require(key not in seen, 'Duplicate actual Korean TextMap hash')
        seen.add(key)
        if key in keys:
            texts[key] = {'raw': text, 'offset': start, 'end': reader.at}
    reader.eof()
    require(total == entry['rows'] and set(texts) == keys, 'Actual full official TextMap count/EOF/hash set differs')
    corpus = {}
    for tid, row in talks.items():
        join = data['joins'][str(tid)]
        src = join['preservedSource']
        if src['file'] not in corpus:
            corpus[src['file']] = load(repo / src['file'])
        original = pointer(corpus[src['file']], src['pointer'])
        text = texts[row['hash']]
        speaker = texts.get(row.get('speaker_hash', '0'))
        require(original['hash'] == row['hash'] and original.get('speaker_hash', '0') == row.get('speaker_hash', '0')
                and original['voice'] == row.get('voice', 0), 'Actual official table/hash/voice differs from preserved Korean')
        require((row['offset'], row['end']) == (join['tableOffset'], join['tableEnd'])
                and (text['offset'], text['end']) == (join['textOffset'], join['textEnd']) and text['raw'] == join['raw'],
                'Actual official Korean raw native span differs')
        require((speaker['raw'] if speaker else '') == join['speakerRaw']
                and (speaker['offset'] if speaker else None) == join['speakerOffset']
                and (speaker['end'] if speaker else None) == join['speakerEnd'], 'Actual official Korean speaker raw span differs')
    return {'actualOfficialTalkTableRowsEOF': table['rows'], 'actualOfficialKoreanTextMapRowsEOF': entry['rows'],
            'actualOfficialKoreanIds': len(ids), 'officialVersion': evidence['clientVersion']}


class TimelineHTML(HTMLParser):
    """Static originals stay outside compressed technical metadata."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.rows, self.links, self.text, self.proof_markers = [], [], [], [], []
        self.ids = Counter()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        parent = self.stack[-1] if self.stack else (None, None, None)
        row, paragraph = parent[1:]
        if attrs.get('id'):
            self.ids[attrs['id']] += 1
        if 'data-deep-talk' in attrs:
            row = {'talkId': int(attrs['data-deep-talk']), 'role': attrs.get('data-deep-role'),
                   'speaker': attrs.get('data-speaker'), 'passage': attrs.get('data-passage'),
                   'choice': 'choice' in attrs.get('class', '').split(), 'paragraphs': [], 'links': []}
            self.rows.append(row)
        if tag == 'p' and 'original-body' in attrs.get('class', '').split():
            require(row is not None, 'Static original outside native row')
            paragraph = {'anchor': attrs.get('id'), 'text': ''}
            row['paragraphs'].append(paragraph)
        if tag == 'a' and attrs.get('href'):
            link = unquote(attrs['href'])
            self.links.append(link)
            if row is not None:
                row['links'].append(link)
        if 'data-deep-clip-proof' in attrs:
            self.proof_markers.append(attrs['data-deep-clip-proof'])
        if tag not in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'):
            self.stack.append((tag, row, paragraph))

    def handle_endtag(self, tag):
        indices = [i for i, item in enumerate(self.stack) if item[0] == tag]
        if indices:
            del self.stack[indices[-1]:]

    def handle_data(self, text):
        self.text.append(text)
        if self.stack and self.stack[-1][2] is not None:
            self.stack[-1][2]['text'] += text


def rendered_scene(scene, data, corpus, static, expanded):
    page = TimelineHTML()
    page.feed(static)
    page.close()
    rows = scene_rows(scene)
    require(all(n == 1 for n in page.ids.values()), 'Duplicate static original anchors')
    require([r['talkId'] for r in page.rows] == [r['talkId'] for r in rows], 'Static native originals ID/order differs')
    for row, actual in zip(rows, page.rows):
        source = data['joins'][str(row['talkId'])]['preservedSource']
        original = pointer(corpus[source['file']], source['pointer'])
        is_reference = row['role'] == 'NON_SPOKEN_OPTION_REFERENCE'
        require(actual['role'] == row['role'] and actual['speaker'] == original['speaker']
                and actual['passage'] == ('choice' if is_reference else 'dialogue') and actual['choice'] == is_reference,
                'Static native role/speaker/choice display differs')
        require(actual['paragraphs'] == [{'anchor': row['anchor'], 'text': original['text']}] and page.ids[row['anchor']] == 1,
                'Static Korean original body/anchor differs')
        href = '/starrail-quests/대사/' + Path(source['file']).stem + '.html#talk-' + str(row['talkId'])
        require(href in actual['links'], 'Native original return link absent')
    for owner in scene['owners']:
        require('/starrail-quests/문서/' + owner['canonicalMission'] + '.html#deep-timeline-originals' in page.links,
                'Native explicit owner reading return link absent')
    proof = TimelineHTML()
    proof.feed(expanded)
    proof.close()
    require(proof.proof_markers == [row['anchor'] for row in rows] and proof.ids['verified-sources'] == 1,
            'Rendered native technical markers/order absent')
    text = ''.join(proof.text)
    receipt = scene['proof']['receipt']
    require(all(value in text for value in (scene['source'], receipt['cabName'], receipt['cabSha256'],
                receipt['sourceBlockSha256'], scene['proof']['root']['sha256'], scene['proof']['root']['pathID'])),
            'Rendered exact native source/root identity absent')
    require(not re.search(r'(?i)[a-z]:[/\\]|file://|\.codex-work[/\\]', text), 'Private path in rendered native evidence')
    for ref in scene['proof']['references']:
        source = data['sourceProofs'][ref['sourceIndex']]
        require(source['logicalJsonPath'] in text and ref['pointer'] in text and source['entrySha256'] in text
                and str(ref['fieldSpan']['start']) + '–' + str(ref['fieldSpan']['end']) in text,
                'Rendered exact native caller span/hash absent')
    for row in rows:
        join = data['joins'][str(row['talkId'])]
        source = join['preservedSource']
        original = pointer(corpus[source['file']], source['pointer'])
        require(all(value in text for value in (row['object']['pathID'], row['object']['sha256'], row['track']['sha256'],
                    row['idField']['field'], '–'.join(map(str, row['idField']['span'])), original['hash'], join['raw'])),
                'Rendered native UInt64/literal ID/source raw proof absent')
    return len(rows)


def dist_replay(repo, data, directory, publication_report=None):
    corpus = {name: load(repo / name) for name in {j['preservedSource']['file'] for j in data['joins'].values()}}
    expansion, report, rows = None, None, 0
    for scene in data['scenes']:
        path = directory / '대화' / ('연출-' + scene['id'] + '.html')
        require(path.is_file(), 'Native fresh static reader absent: ' + scene['id'])
        static = path.read_text(encoding='utf8')
        expanded = static
        if re.search(r'__spr\(|__sp\(|__starrailPublicationWrite\(', static):
            if expansion is None:
                # Existing independent reader's shard hashes/bytes are validated;
                # its closure caches each decoded shard once for all 3,204 pages.
                from optimize_publication import expansion_function
                report = load(publication_report or repo / '.codex-work/publication-build-report.json')
                for shard in report.get('proofShards', {}).values():
                    url = unquote(shard['url'])
                    require(url.startswith('/starrail-quests/'), 'Technical shard URL base differs')
                    relative_name = url[len('/starrail-quests/'):]
                    relative(relative_name)
                    actual = (directory / relative_name).read_bytes()
                    require(sha(actual) == shard['assetSha256'], 'Actual technical shard source SHA differs')
                expansion = expansion_function(report)
            expanded = expansion(static)
        rows += rendered_scene(scene, data, corpus, static, expanded)
    return {'staticFreshReaders': len(data['scenes']), 'staticFreshOriginals': rows,
            'technicalProofExpansion': 'One cached expansion closure; originals validated before expansion',
            'proofShardReceipts': len(report.get('proofShards', {})) if report else 0}


def self_tests(repo, data, inverse):
    tests = []
    def reject(name, fn):
        try:
            fn()
        except (ValueError, KeyError, IndexError, UnicodeError, struct.error):
            tests.append(name)
            return
        raise ValueError('Semantic negative mutation accepted: ' + name)
    # Full adopted slice preserves the actual frozen IDs; shallow top-level copy
    # and one cloned scene/join keep mutation checks inexpensive and independent.
    def mutate(name, edit):
        bad = dict(data)
        bad['scenes'] = list(data['scenes'])
        bad['scenes'][0] = copy.deepcopy(data['scenes'][0])
        bad['joins'] = dict(data['joins'])
        bad['sourceProofs'] = dict(data['sourceProofs'])
        edit(bad, bad['scenes'][0])
        reject(name, lambda: source_validate(repo, bad, inverse))
    mutate('native role domain', lambda d, s: s['rows'][0].__setitem__('role', 'SCREEN_TEXT'))
    mutate('literal UInt32 ID', lambda d, s: s['rows'][0].__setitem__('talkId', 1))
    mutate('native literal field domain', lambda d, s: s['rows'][0]['idField'].__setitem__('field', 'UnrelatedID'))
    mutate('native literal span width', lambda d, s: s['rows'][0]['idField'].__setitem__('span', [60, 65]))
    mutate('clip NaN time', lambda d, s: s['rows'][0].__setitem__('start', float('nan')))
    mutate('clip negative duration', lambda d, s: s['rows'][0].__setitem__('duration', -1))
    mutate('native route root endpoint', lambda d, s: s['rows'][0]['parentRoute'].__setitem__(-1, '1'))
    mutate('native route cycle', lambda d, s: s['rows'][0]['parentRoute'].append(s['rows'][0]['track']['pathID']))
    mutate('native 64-bit path precision', lambda d, s: s['rows'][0]['track'].__setitem__('pathID', 123))
    mutate('invented region owner', lambda d, s: s['owners'][0].__setitem__('region', 'Unknown'))
    mutate('invented main mission', lambda d, s: s['owners'][0].__setitem__('mission', 'quest-1'))
    mutate('native root/class domain', lambda d, s: s['proof']['root'].__setitem__('class', 'UnrelatedAsset'))
    mutate('direct container identity', lambda d, s: s['proof']['container'].__setitem__('key', 'assets/unrelated.playable'))
    mutate('private path leak', lambda d, s: s.__setitem__('source', 'X:/private/game.playable'))
    def raw_mutation(d, s):
        key = str(s['rows'][0]['talkId'])
        d['joins'][key] = dict(d['joins'][key], raw=d['joins'][key]['raw'] + ' changed')
    mutate('Korean raw source mismatch', raw_mutation)
    def hash_mutation(d, s):
        key = str(s['rows'][0]['talkId'])
        j = copy.deepcopy(d['joins'][key])
        j['preservedSource']['sha256'] = '0' * 64
        d['joins'][key] = j
    mutate('Korean source SHA mismatch', hash_mutation)
    mutate('caller pointer mismatch', lambda d, s: s['proof']['references'][0].__setitem__('pointer', '/Wrong/TimelineName'))
    mutate('caller field byte bound', lambda d, s: s['proof']['references'][0]['fieldSpan'].__setitem__('end', 99999999))
    mutate('caller actual class domain', lambda d, s: s['proof']['references'][0]['context']['typedContainer'].__setitem__('type', 'RPG.GameCore.PlayOptionTalk'))
    mutate('archive unavailable boundary removal', lambda d, s: s['proof']['references'][0].__setitem__('archiveTerminalStatus', 'PASS'))
    if inverse is not None:
        bad = dict(inverse, readerLinks=dict(inverse['readerLinks']))
        bad['readerLinks'][str(data['scenes'][0]['rows'][0]['talkId'])] = []
        reject('inverse exact anchor absence', lambda: source_validate(repo, data, bad))
    obj = {'name': '', 'baseBytesRead': 32, 'pathID': '1', 'scriptPointer': {'m_FileID': 0, 'm_PathID': '7'}}
    base = bytes(12) + b'\x01\0\0\0' + struct.pack('<iqi', 0, 7, 0)
    root = base + bytes(4 + 12 + 4) + struct.pack('<dfi', 1.0, 24.0, 0) + bytes(12)
    decode_root(root, obj)
    bad = bytearray(root)
    struct.pack_into('<f', bad, 60, float('nan'))
    reject('root frame NaN', lambda: decode_root(bytes(bad), obj))
    bad = bytearray(root)
    struct.pack_into('<f', bad, 60, 0)
    reject('root frame zero', lambda: decode_root(bytes(bad), obj))
    bad = bytearray(root)
    bad[12] = 2
    reject('native declared enabled bool2', lambda: decode_root(bytes(bad), obj))
    reject('root trailing source bytes', lambda: decode_root(root + b'\0', obj))
    sample = next(s for s in data['scenes'] if len(scene_rows(s)) >= 2)
    corpus = {j['preservedSource']['file']: load(repo / j['preservedSource']['file'])
              for r in scene_rows(sample) for j in [data['joins'][str(r['talkId'])]]}
    static = ''
    proof = '<details id="verified-sources">'
    for owner in sample['owners']:
        static += '<a href="/starrail-quests/문서/' + owner['canonicalMission'] + '.html#deep-timeline-originals">owner</a>'
    receipt = sample['proof']['receipt']
    proof += escape(' '.join([sample['source'], receipt['cabName'], receipt['cabSha256'], receipt['sourceBlockSha256'],
                              sample['proof']['root']['sha256'], sample['proof']['root']['pathID']]))
    for ref in sample['proof']['references']:
        source = data['sourceProofs'][ref['sourceIndex']]
        proof += escape(source['logicalJsonPath'] + ref['pointer'] + source['entrySha256'] + str(ref['fieldSpan']['start']) + '–' + str(ref['fieldSpan']['end']))
    for row in scene_rows(sample):
        join = data['joins'][str(row['talkId'])]
        source = join['preservedSource']
        original = pointer(corpus[source['file']], source['pointer'])
        choice = row['role'] == 'NON_SPOKEN_OPTION_REFERENCE'
        static += '<div data-deep-talk="' + str(row['talkId']) + '" data-deep-role="' + row['role'] + '" data-speaker="' + escape(original['speaker'], quote=True) + '" data-passage="' + ('choice' if choice else 'dialogue') + '" class="' + ('choice' if choice else '') + '">'
        static += '<p class="original-body" id="' + row['anchor'] + '">' + escape(original['text']) + '</p>'
        static += '<a href="/starrail-quests/대사/' + Path(source['file']).stem + '.html#talk-' + str(row['talkId']) + '">return</a></div>'
        proof += '<li data-deep-clip-proof="' + row['anchor'] + '">' + escape(' '.join([row['object']['pathID'], row['object']['sha256'], row['track']['sha256'],
                            row['idField']['field'], '–'.join(map(str, row['idField']['span'])), original['hash'], join['raw']])) + '</li>'
    proof += '</details>'
    rendered_scene(sample, data, corpus, static, static + proof)
    first = scene_rows(sample)[0]
    reject('static missing original', lambda: rendered_scene(sample, data, corpus, '', proof))
    reject('static typed role mutation', lambda: rendered_scene(sample, data, corpus, static.replace('data-deep-role="SPOKEN"', 'data-deep-role="SCREEN_TEXT"', 1), static + proof))
    reject('static original body mutation', lambda: rendered_scene(sample, data, corpus, static.replace('<p class="original-body"', '<p class="changed"', 1), static + proof))
    reject('static original return link absence', lambda: rendered_scene(sample, data, corpus, static.replace('.html#talk-' + str(first['talkId']), '.html#wrong'), static + proof))
    reject('static duplicate original anchor', lambda: rendered_scene(sample, data, corpus, static + '<p id="' + first['anchor'] + '"></p>', static + proof))
    reject('technical source proof absence', lambda: rendered_scene(sample, data, corpus, static, static))
    tests.extend(guard_tests()['negativeGuardTests'])
    return tests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--projection', type=Path, help='Explicit closed input override for independent audit before integration')
    parser.add_argument('--audit', type=Path, help='Closed raw CAB/whole-source receipt directory; no producer execution')
    parser.add_argument('--official-root', type=Path, help='Explicit approved current official DesignV/pack cache')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--dist', type=Path)
    parser.add_argument('--publication-report', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    source = args.projection or repo / 'data/native-fresh-timeline-dialogue.json'
    raw = source.read_bytes()
    require(sha(raw) == PROJECTION_SHA, 'Immutable closed fresh projection SHA differs')
    data = json.loads(raw)
    inverse = load(repo / 'data/deep-dialogue-attribution.json')
    require(inverse['evidence']['freshTimelineSha256'] == sha(raw), 'Exact inverse fresh source SHA differs')
    require(file_sha(repo / 'data/deep-timeline-dialogue.json') == data['evidence']['existingDeepTimelineSha256'],
            'Preserved existing Timeline source SHA differs')
    require(data['evidence']['installedVersion'] == 'UNVERIFIED'
            and data['evidence']['callerEditionStatus'] == 'CACHED_SNAPSHOT_CURRENT_INSTALLED_EDITION_UNVERIFIED',
            'Unverified installed/caller edition boundary altered')
    require(data['evidence']['officialKorean']['entry']['fullEofVerified'] is True
            and data['evidence']['officialKorean']['talkTable']['fullEofVerified'] is True, 'Declared official EOF boolean altered')
    checks = {'source': source_validate(repo, data, inverse)}
    if args.audit:
        checks['caller'] = caller_replay(data, args.audit.resolve())
        checks['nativeGuard'] = native_guard_replay(data, args.audit.resolve())
        checks['native'] = native_replay(data, args.audit.resolve())
    if args.archive:
        checks['archive'] = archive_replay(data, args.archive.resolve())
    if args.official_root:
        checks['officialKorean'] = official_replay(repo, data, args.official_root.resolve())
    if args.dist:
        checks['dist'] = dist_replay(repo, data, args.dist.resolve(), args.publication_report)
    report = {'schema': 'starrail-fresh-native-independent-verification.v1', 'status': 'PASS',
              'projectionSha256': sha(raw), 'verifierSha256': file_sha(Path(__file__)), 'checks': checks,
              'guard': guard_tests(), 'negativeCanaries': self_tests(repo, data, inverse) if args.self_test else [],
              'limits': ['Current installed release edition remains UNVERIFIED.',
                         'Only supported typed adopted clips are attributed by this verifier; unsupported assets remain separate census STOPs.',
                         'MonoScript metadata is extraction-receipt bound, not an independent raw115/CAB decompression replay.',
                         'Full compiled caller sources use immutable whole-EOF receipts; literal PlayTimeline terminal bytes are independently decoded.',
                         'No branch execution or runtime play order is inferred from clip timing.',
                         'JSON is a mandatory repository build input; this task does not claim an additional public download mirror.']}
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, IndexError, OSError, UnicodeError, struct.error) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
