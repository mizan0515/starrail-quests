"""Independent stdlib verifier for closed native OptionTalk additions.

Read-only source, official primitive/locale, owner archive and static HTML
checks. No producer imports or game-script execution. Unknown native fields
outside the declared choice bodies are not presented as independently decoded.
"""
import argparse
import base64
from collections import Counter
import copy
import gzip
import hashlib
from html import escape
from publication_contract_reader import HTMLParser
import json
from pathlib import Path
import re
import struct
import sys
import tarfile
from urllib.parse import unquote, urlsplit

HASH = re.compile(r'^[0-9a-f]{64}$')
PARENT = 'RPG.GameCore.PlayOptionTalk'
OPTION = 'RPG.GameCore.OptionTalkInfo'
BASELINE = {
    'timeline-7ab33b57687b0b2b': '4367f71527f4a0b8823edf79be3d5ecee474e9b97603a12419b8382989e6de0a',
    'timeline-dceb37eba1a28afb': '0e50de001029c845cb8429d5f13e4c0eb08379f62162dc4be896f2e9020f2787',
}
PHASES = {
    'ba68dfa055f88c443d1d6d73a21bf91a0ba63af29adb66b8c4797437f8add87f':
        (30, 193, '319f7df6f5691c552c69a3c3d4625b9637d9edb433fea49b10630c2bb6c70b10',
         'b54f134a440fe496c389262a3ad734f9ae630d91ff782e208dfb71c29c7aaac5'),
    'c1802a09cf54b349831877052c6b411ef7dec0c54a1b504dde121c7e3ca2bb08':
        (3, 24, '0f8305ebc70bd373bcc1d2f7333d8de78812210ad2d67a51d6db313cff336376',
         '6eb8aa438f50371df9b2cabba4ea0b427761f6f616ea3be61efc69f8ff18024f'),
    '57ac250c81b172d729ed282cd79d522f617c46a4be20f5ae76c94156950c5bff':
        (1, 7, '78529ddd98ec39b3e608ba7e2d63440dd819ffff06a9b654b26c8adab5376626',
         '24045a6734ae7f3afaeaf671817160b7936c15d46779fc0a9d745633481d7f88'),
    'd5e01f3d642c22bbf62f7fb59f859fea42c2dade35288cef7137d3a86e9a44c6':
        (4, 11, 'e39e8e5bb9184558173e0b73b7c72ec692105f28cf48aa619b5c3b6dbaaa1ec3',
         'eff72144ee0f7f89072ee5b14315f37032352a40bc0648c1bc77680ba8d034bf'),
    '261ceed3ee495827b3044d54823c6b1a900016b41baeb74f1a76b9ebbb203671':
        (2, 10, '0d5c7a61fad8a26196d916044f1afddbb3e055ec89716b703d980a220551b4ff',
         'a656c7bbadb8bd91adf16fb7145ef4f0ee7b242f457d0e8607e5242730d644b8'),
    'da3da0fcafb3802279ae6c8b8cb2549976c03248d54c18b8f1805cabd899bde2':
        (1, 6, 'e75b0ce6a884119ac8cdd9ffd8c475a8d211a1c782c0e13d16565bea126b24c1',
         '57cd1d82f3b1c71c386808e34a021eac1c0f7f2a0e14141fb7b6f0c90a3960f1'),
}
PHASE2_SCENES = {'timeline-2685d8ce82e1731a', 'timeline-8035755d35f0edb7', 'timeline-0156d34db5dd8d0d'}
PHASE5_SCENES = {'timeline-1d9e796cbfb38ff8'}
FIELD_PHASE6_SCENES = {'timeline-3297d588b63693a2', 'timeline-8b4c2ac5caa314fd',
                       'timeline-5f63419fe65df04b', 'timeline-2fd9d9f5dca3c9cf'}
FIELD_PHASE8_SCENES = {'timeline-6d1dd1be8ea1c611', 'timeline-5d3ec60172fd754d'}
FIELD_PHASE10_SCENES = {'timeline-971e9da54f3ed9f1'}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')


def sequence_hash(values):
    return digest(json.dumps(sorted(values), separators=(',', ':')).encode('utf8'))


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def at(value, pointer):
    require(isinstance(pointer, str) and (not pointer or pointer.startswith('/')), 'JSON pointer domain')
    for token in pointer.split('/')[1:]:
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def relative(value):
    require(isinstance(value, str) and value and not value.startswith(('/', '\\'))
            and '\\' not in value and ':' not in value and '..' not in value.split('/'), 'Relative source path domain')


def safe_public(value, key=''):
    if isinstance(value, dict):
        for name, child in value.items():
            safe_public(child, name)
    elif isinstance(value, list):
        for child in value:
            safe_public(child, key)
    elif isinstance(value, str):
        require(not re.search(r'(?i)(?:[a-z]:[/\\]|file://|\\\\|\.codex-work[/\\])', value),
                'Private path in public choice source')
        if key in ('Hash', 'hash', 'speaker_hash', 'nameHash'):
            require(value.isdecimal() and 0 <= int(value) < 2 ** 64, 'Lossless UInt64 string domain')
    elif key in ('Hash', 'hash', 'speaker_hash', 'nameHash'):
        raise ValueError('Public UInt64 hash lost string precision')


def readable(raw):
    value = raw.replace('\\n', '\n').replace('\u00a0', ' ')
    value = re.sub(r'\{RUBY_[BE]#[^}]*\}', '', value)
    value = re.sub(r'</?(?:color|size|b|i|u|align|voffset|indent|line-height|unbreak)(?:=[^>]*)?>', '', value, flags=re.I)
    return re.sub(r'<br\s*/?>', '\n', value, flags=re.I)


class Primitive:
    def __init__(self, raw, start=0, end=None):
        self.raw = raw
        self.at = start
        self.end = len(raw) if end is None else end
        require(0 <= start <= self.end <= len(raw), 'Primitive byte bounds')

    def take(self, size):
        require(type(size) is int and 0 <= size <= self.end - self.at, 'Primitive truncated bytes')
        result = self.raw[self.at:self.at + size]
        self.at += size
        return result

    def uint(self, width=64):
        value = 0
        for shift in range(0, width + 7, 7):
            byte = self.take(1)[0]
            value |= (byte & 127) << shift
            if byte < 128:
                require(value < 2 ** width and (not shift or byte != 0), 'Unsigned varint width/canonical domain')
                return value
        raise ValueError('Unsigned varint continuation exceeds domain')

    def count(self):
        value = self.uint(32)
        count = (value >> 1) ^ -(value & 1)
        require(0 <= count <= 2000000, 'Array signed count domain')
        return count

    def string(self):
        return self.take(self.uint(32)).decode('utf8')

    def boolean(self):
        value = self.uint(8)
        require(value in (0, 1), 'Boolean primitive domain')
        return bool(value)

    def eof(self):
        require(self.at == self.end, 'Primitive body EOF differs')


def spans_for(proof):
    spans = {}
    length = proof['wholeFieldEOF']
    require(type(length) is int and length > 0, 'Whole source EOF domain')
    for span in proof['fieldSpans']:
        pointer = span['pointer']
        require(pointer not in spans and type(span['start']) is int and type(span['end']) is int
                and 0 <= span['start'] < span['end'] <= length, 'Source field span duplicate/bounds')
        at(proof['fields'], pointer)
        spans[pointer] = span
    require(spans.get('') == {'pointer': '', 'start': 0, 'end': length}, 'Source root span/EOF differs')
    for pointer, span in spans.items():
        if not pointer:
            continue
        parent = pointer.rsplit('/', 1)[0]
        while parent not in spans:
            parent = parent.rsplit('/', 1)[0]
        outer = spans[parent]
        require(outer['start'] <= span['start'] < span['end'] <= outer['end'], 'Nested source field span escapes parent')
    return spans


def membership_check(repo, owner, cache):
    require(set(owner) == {'mission', 'canonicalMission', 'title', 'ownerChain'},
            'Unexpected owner/region attribution field')
    chain = owner['ownerChain']
    require(len(chain) == 3 and [e['kind'] for e in chain] ==
            ['EXPLICIT_MAIN_MISSION_ID', 'EXPLICIT_JSON_PATH', 'EXPLICIT_PERFORMANCE_LOOKUP'], 'Owner typed chain domain')
    seed, path, lookup = chain
    require(type(seed['missionId']) is int and seed['missionId'] > 0
            and owner['mission'] == 'quest-' + str(seed['missionId']), 'Owner mission ID domain')
    require(owner['canonicalMission'] == 'quest-' + str(seed['canonicalMissionId']), 'Owner canonical mission domain')
    name = seed['membershipSource']
    relative(name)
    require(name == 'data/documents/' + owner['canonicalMission'] + '.json', 'Membership source/canonical mission mismatch')
    if name not in cache:
        raw = (repo / name).read_bytes()
        cache[name] = (digest(raw), json.loads(raw))
    sha, document = cache[name]
    require(sha == seed['membershipSha256'] and at(document, seed['membershipPointer']) == owner['mission'],
            'Actual preserved mission membership/source hash differs')
    require(document['id'] == owner['canonicalMission'] and owner['mission'] in document.get('missionParts', [document['id']]),
            'Mission canonical membership differs')
    require(path['source'] == seed['source'] and path['sourceSha256'] == seed['sourceSha256']
            and lookup['source'] == path['target'], 'Owner chain discontinuity')
    tables = {'D': 'ExcelOutput/PerformanceDS.json', 'C': 'ExcelOutput/PerformanceC.json'}
    require(lookup['performanceType'] in tables and lookup['lookupScope'] == 'TYPED_PRIMARY_TABLE'
            and lookup['tableSource'] == tables[lookup['performanceType']], 'Owner performance lookup ID/table domain')
    require(lookup['ownershipSeed']['missionId'] == seed['missionId']
            and lookup['ownershipSeed']['source'] == seed['source'], 'Lookup owner seed differs')
    for edge in chain:
        relative(edge['source'])
        require(HASH.fullmatch(edge['sourceSha256']), 'Owner source SHA domain')
        if 'target' in edge:
            relative(edge['target'])
        if 'tableSource' in edge:
            relative(edge['tableSource'])
            require(HASH.fullmatch(edge['tableSha256']), 'Owner table SHA domain')
    return chain


def source_check(repo, data, inverse):
    require(data['schema'] == 'starrail-deep-timeline-dialogue.v1', 'Deep timeline schema')
    safe_public(data)
    scenes = [s for s in data['scenes'] if s.get('kind') == 'NATIVE_CHOICES']
    byid = {s['id']: s for s in scenes}
    require(len(byid) == len(scenes), 'Duplicate native choice scene')
    for key, sha in BASELINE.items():
        require(key in byid and digest(canonical(byid[key])) == sha, 'Baseline native sixteen choices changed')
    declared = data['evidence'].get('nativeChoiceDeltas', [])
    require(declared and len({d['sha256'] for d in declared}) == len(declared), 'Closed delta evidence absent/duplicate')
    active = set()
    for delta in declared:
        require(delta['sha256'] in PHASES, 'Unclosed native choice delta')
        phase = PHASES[delta['sha256']]
        require((delta['scenes'], delta['rows']) == phase[:2], 'Native delta declared counts differ')
        active.add(delta['sha256'])
    require(next(iter(PHASES)) in active, 'First immutable choice delta absent')
    new = [s for s in scenes if s['id'] not in BASELINE]
    phase2 = [s for s in new if s['id'] in PHASE2_SCENES]
    phase5 = [s for s in new if s['id'] in PHASE5_SCENES]
    field6 = [s for s in new if s['id'] in FIELD_PHASE6_SCENES]
    field8 = [s for s in new if s['id'] in FIELD_PHASE8_SCENES]
    field10 = [s for s in new if s['id'] in FIELD_PHASE10_SCENES]
    phase1 = [s for s in new if s['id'] not in PHASE2_SCENES | PHASE5_SCENES | FIELD_PHASE6_SCENES | FIELD_PHASE8_SCENES | FIELD_PHASE10_SCENES]
    for sha, subset in zip(PHASES, (phase1, phase2, phase5, field6, field8, field10)):
        if sha not in active:
            require(not subset, 'Unannounced native choice phase source')
            continue
        nscene, nrow, idhash, scenehash = PHASES[sha]
        tids = [r['talkId'] for s in subset for r in s['rows']]
        require(sha == '261ceed3ee495827b3044d54823c6b1a900016b41baeb74f1a76b9ebbb203671'
                or len(tids) == len(set(tids)), 'Unexpected duplicate choice IDs in immutable phase')
        require(len(subset) == nscene and len(tids) == nrow
                and sequence_hash(set(tids)) == idhash and sequence_hash(s['id'] for s in subset) == scenehash,
                'Closed choice delta scene/ID cohort differs')
    rows_expected = sum(PHASES[sha][1] for sha in active)
    require(data['counts']['roles']['NATIVE_CHOICE'] == 16 + rows_expected, 'Native choice aggregate count differs')
    memberships = {}
    corpus = {}
    selected_ids = set()
    field_count = 0
    owner_sources = {}
    for scene in new:
        relative(scene['source'])
        require(scene['source'].startswith('Story/') and scene['source'].endswith('.json'), 'Native logical source domain')
        require(scene['ownerStatus'] == 'ONE_EXPLICIT_OWNER' and bool(scene['owners'])
                and len({o['canonicalMission'] for o in scene['owners']}) == 1, 'Native choice owner partition differs')
        proof = scene['proof']
        require(proof['kind'] == 'EXACT_NATIVE_WHOLE_FIELD_CHOICE_SOURCE' and HASH.fullmatch(proof['entrySha256']),
                'Native whole source proof domain')
        spans = spans_for(proof)
        field_count += len(spans)
        descriptor = proof['descriptor']
        require(descriptor['logicalJsonPath'] == scene['source'] and descriptor['entrySha256'] == proof['entrySha256']
                and descriptor['ownerExactValidation'] == 'PASS', 'Native source descriptor identity differs')
        match, = descriptor['catalogMatches']
        require(re.fullmatch(r'[0-9a-f]{32}\.bytes', match['file']) and type(match['offset']) is int
                and match['offset'] >= 0 and match['length'] == proof['wholeFieldEOF']
                and match['offset'] + match['length'] <= match['packExpectedBytes'], 'Actual entry descriptor bounds')
        require(proof['pack']['bytes'] == match['packExpectedBytes'] and HASH.fullmatch(proof['pack']['sha256'])
                and proof['pack']['md5MatchesFilename'] is True, 'Native source pack evidence differs')
        for owner in scene['owners']:
            chain = membership_check(repo, owner, memberships)
            require(chain[-1]['target'] == scene['source'] and (descriptor['ownerChain'] == chain or owner != scene['owners'][0])
                    and descriptor['mission'] == scene['owners'][0]['mission'], 'Native source owner chain endpoint differs')
            for edge in chain:
                for field, hfield in (('source', 'sourceSha256'), ('tableSource', 'tableSha256')):
                    if field in edge:
                        require(edge[field] not in owner_sources or owner_sources[edge[field]] == edge[hfield], 'Conflicting owner source hash')
                        owner_sources[edge[field]] = edge[hfield]
        actual_order = []
        for group in scene['options']:
            require(group['parentTaskType'] == PARENT and group['task']['$type'] == PARENT
                    and at(proof['fields'], group['pointer']) == group['task'], 'Typed choice parent source differs')
            require(group['optionListPointer'] == group['pointer'] + '/OptionList'
                    and group['options'] == group['task']['OptionList'], 'Choice list parent/source identity differs')
            for i, option in enumerate(group['options']):
                require(option['$type'] == OPTION and type(option['TalkSentenceID']) is int
                        and 0 < option['TalkSentenceID'] < 2 ** 32, 'OptionTalkInfo/TalkSentence UInt32 domain')
                actual_order.append((group['pointer'], group['optionListPointer'], i, option))
        require(len(actual_order) == len(scene['rows']), 'Native option/row partition differs')
        anchors = set()
        for row, (parent, container, index, option) in zip(scene['rows'], actual_order):
            tid = row['talkId']
            require(row['role'] == 'NATIVE_CHOICE' and row['parentTaskType'] == PARENT
                    and row['parentTaskPointer'] == parent and row['choiceContainerPointer'] == container
                    and row['optionIndex'] == index and row['option'] == option and option['TalkSentenceID'] == tid,
                    'Native choice role/typed parent/index/order differs')
            require(row['anchor'] == 'talk-' + str(tid) + '-occ1' and row['anchor'] not in anchors, 'Native occurrence anchor domain')
            anchors.add(row['anchor'])
            rp = row['proof']
            ptr = container + '/' + str(index) + '/TalkSentenceID'
            require(rp['kind'] == 'EXACT_NATIVE_OPTION_TALK_REFERENCE' and rp['source'] == scene['source']
                    and rp['entrySha256'] == proof['entrySha256'] and rp['wholeFieldEOF'] == rp['entryBytes'] == proof['wholeFieldEOF']
                    and rp['pointer'] == ptr and at(proof['fields'], ptr) == tid, 'Native row pointer/source proof differs')
            require(rp['fieldSpans'] == [s for s in proof['fieldSpans']
                                       if s['pointer'] == container + '/' + str(index)
                                       or s['pointer'].startswith(container + '/' + str(index) + '/')], 'Native row field span precision differs')
            link = '대화/연출-' + scene['id'] + '.html#' + row['anchor']
            require(any(x['url'] == link and x['source'] == scene['source'] and x['role'] == 'NATIVE_CHOICE'
                        for x in inverse['readerLinks'].get(str(tid), [])), 'Exact inverse choice anchor absent')
            join = data['joins'][str(tid)]
            source = join['preservedSource']
            relative(source['file'])
            require(source['file'].startswith('data/dialogues/'), 'Preserved Korean corpus domain')
            if source['file'] not in corpus:
                raw = (repo / source['file']).read_bytes()
                corpus[source['file']] = (digest(raw), json.loads(raw))
            sha, original = corpus[source['file']]
            original = at(original, source['pointer'])
            require(sha == source['sha256'] and original['talk_id'] == tid, 'Preserved Korean original source/ID differs')
            current = join['currentOfficialSource']
            table, text = current['tableRecord'], current['textRecord']
            require(table['TalkSentenceID'] == tid and str(table['TalkSentenceText']['Hash']) == original['hash'] == text['hash']
                    and text['raw'] == join['raw'] and readable(join['raw']) == original['text'], 'Korean raw/hash/table domain differs')
            speaker = table.get('TextmapTalkSentenceName', {'Hash': '0'})['Hash']
            require(str(speaker) == original['speaker_hash'] and table.get('VoiceID', 0) == original['voice'], 'Korean speaker/voice domain differs')
            sr = current['speakerRecord']
            require((sr is None and str(speaker) == '0' and join['speakerRaw'] == '')
                    or (sr is not None and sr['hash'] == str(speaker) and sr['raw'] == join['speakerRaw']
                        and readable(sr['raw']) == original['speaker']), 'Korean speaker raw domain differs')
            require(type(current['tableRowIndex']) is int and current['tableRowIndex'] >= 0
                    and 0 <= table['_offset'] < table['_end'] <= data['evidence']['officialKorean']['talkTable']['length']
                    and 0 <= text['offset'] < text['end'] <= data['evidence']['officialKorean']['entry']['length'], 'Official Korean source spans')
            selected_ids.add(tid)
    expected_ids = rows_expected - (5 if '261ceed3ee495827b3044d54823c6b1a900016b41baeb74f1a76b9ebbb203671' in active else 0)
    require(len(selected_ids) == expected_ids, 'Closed native IDs overlap/differ')
    return new, owner_sources, {'newChoiceScenes': len(new), 'newChoices': rows_expected, 'baselineChoices': 16,
                               'sourceFieldSpans': field_count, 'ownerArchiveSources': len(owner_sources),
                               'preservedKoreanFiles': len(corpus), 'newChoiceIds': len(selected_ids)}


def choice_primitives(raw, scene):
    proof = scene['proof']
    require(len(raw) == proof['wholeFieldEOF'] and digest(raw) == proof['entrySha256'], 'Actual native entry bytes/hash differ')
    spans = spans_for(proof)
    counts = Counter()
    for group in scene['options']:
        task = spans[group['pointer']]
        reader = Primitive(raw, task['start'], task['end'])
        require(reader.uint(32) == 1954, 'Actual parent task discriminator is not PlayOptionTalk1954')
        parent_mask = reader.uint(32)
        require(parent_mask in (2, 6), 'Unsupported PlayOptionTalk parent presence mask')
        ls = spans[group['optionListPointer']]
        require(reader.at == ls['start'], 'Actual OptionList span start differs')
        require(reader.count() == len(group['options']), 'Actual OptionList signed count differs')
        for i, option in enumerate(group['options']):
            pointer = group['optionListPointer'] + '/' + str(i)
            os = spans[pointer]
            require(reader.at == os['start'] and reader.uint(32) == 0, 'Actual option selector/span differs from OptionTalkInfo0')
            mask = reader.uint(32)
            expected_mask = 13 | (32 if 'DeleteAfterSelection' in option else 0)
            require(mask == expected_mask, 'Actual OptionTalkInfo presence mask differs')
            start = reader.at
            require(reader.uint(32) == option['TalkSentenceID'], 'Actual TalkSentenceID UInt32 differs')
            field = spans[pointer + '/TalkSentenceID']
            require((start, reader.at) == (field['start'], field['end']), 'Actual UInt32 varint ID span differs')
            start = reader.at
            enum_encoded = reader.uint(32)
            enum = (enum_encoded >> 1) ^ -(enum_encoded & 1)
            encoded = reader.uint(32)
            value = (encoded >> 1) ^ -(encoded & 1)
            require({'EnumIndex': enum, 'Value': value} == option['OptionIconType'], 'Actual choice icon enum differs')
            field = spans[pointer + '/OptionIconType']
            require((start, reader.at) == (field['start'], field['end']), 'Choice enum field span differs')
            start = reader.at
            require(reader.string() == option['TriggerCustomString'], 'Actual option trigger string differs')
            field = spans[pointer + '/TriggerCustomString']
            require((start, reader.at) == (field['start'], field['end']), 'Choice string field span differs')
            if mask & 32:
                start = reader.at
                require(reader.boolean() == option['DeleteAfterSelection'], 'Actual option deletion boolean differs')
                field = spans[pointer + '/DeleteAfterSelection']
                require((start, reader.at) == (field['start'], field['end']), 'Choice boolean field span differs')
            require(reader.at == os['end'], 'Actual whole option EOF differs')
            counts[(parent_mask, mask)] += 1
        require(reader.at == ls['end'], 'Actual whole OptionList EOF differs')
        if parent_mask & 4:
            start = reader.at
            require(reader.boolean() == group['task']['HideSelected'], 'Actual parent HideSelected differs')
            field = spans[group['pointer'] + '/HideSelected']
            require((start, reader.at) == (field['start'], field['end']), 'Parent HideSelected field span differs')
        reader.eof()
    return counts


def official_replay(root, data, scenes):
    files = {}
    evidence = data['evidence']['officialKorean']
    catalogs = list(root.rglob(evidence['catalogFile']))
    require(catalogs, 'Pinned DesignV catalog absent inside supplied official root')
    catalogs = [p for p in catalogs if digest(p.read_bytes()) == evidence['catalogSha256']]
    require(catalogs, 'Actual DesignV catalog SHA differs')
    catalog_raw = catalogs[0].read_bytes()
    require(len(catalog_raw) >= 16, 'DesignV catalog header bounds')
    magic, version, file_count, entry_count = struct.unpack_from('>IIII', catalog_raw)
    require((magic, version) == (255, 4), 'Unsupported DesignV catalog profile')
    pos, catalog, total = 16, {}, 0
    def catalog_take(size):
        nonlocal pos
        require(0 <= size <= len(catalog_raw) - pos, 'DesignV catalog byte bounds')
        raw = catalog_raw[pos:pos + size]
        pos += size
        return raw
    for _ in range(file_count):
        catalog_take(8)
        name = catalog_take(16).hex() + '.bytes'
        size, count = struct.unpack('>QI', catalog_take(12))
        entries, end = [], 0
        for _ in range(count):
            key, length, offset = struct.unpack('>QII', catalog_take(16))
            require(offset == end, 'DesignV catalog noncontiguous entry')
            end = offset + length
            entries.append((key, length, offset))
        language = catalog_take(struct.unpack('>H', catalog_take(2))[0]).decode('ascii')
        catalog_take(1)
        require(end == size, 'DesignV catalog pack EOF differs')
        if not language:
            for key, length, offset in entries:
                require(key not in catalog, 'DesignV non-language entry name hash ambiguity')
                catalog[key] = {'file': name, 'length': length, 'offset': offset, 'packExpectedBytes': size}
        total += count
    require(pos == len(catalog_raw) and total == entry_count, 'Whole DesignV catalog EOF/count differs')
    def pack(name, expected_sha, expected_size=None):
        require(re.fullmatch(r'[0-9a-f]{32}\.bytes', name), 'Actual pack filename domain')
        if name not in files:
            candidates = list(root.rglob(name))
            require(candidates, 'Actual pack absent inside supplied official root: ' + name)
            valid = [p for p in candidates if digest(p.read_bytes()) == expected_sha]
            require(valid, 'Actual pack SHA does not match immutable source')
            raw = valid[0].read_bytes()
            require(hashlib.md5(raw).hexdigest() == name[:-6], 'Actual pack MD5 filename identity differs')
            files[name] = raw
        raw = files[name]
        require(digest(raw) == expected_sha and (expected_size is None or len(raw) == expected_size), 'Actual pack SHA/size differs')
        return raw
    masks = Counter()
    for scene in scenes:
        proof = scene['proof']
        match, = proof['descriptor']['catalogMatches']
        require(catalog[int(proof['descriptor']['nameHash'])] == match,
                'Actual DesignV entry hash/pack/source descriptor differs')
        raw = pack(match['file'], proof['pack']['sha256'], match['packExpectedBytes'])
        masks.update(choice_primitives(raw[match['offset']:match['offset'] + match['length']], scene))
    ids = {row['talkId'] for scene in scenes for row in scene['rows']}
    tb = evidence['talkTable']
    raw = pack(tb['file'], tb['sha256'], tb['size'])[tb['offset']:tb['offset'] + tb['length']]
    require(digest(raw) == tb['entrySha256'], 'Actual TalkSentenceConfig entry SHA differs')
    reader = Primitive(raw)
    if raw[0] == 0:
        reader.take(1)
    total = reader.count()
    talks = {}
    for index in range(total):
        start = reader.at
        mask = reader.uint(32)
        require(mask & ~15 == 0, 'Unknown actual TalkSentenceConfig active fields')
        row = {}
        for bit, name in enumerate(('TalkSentenceID', 'VoiceID', 'TextmapTalkSentenceName', 'TalkSentenceText')):
            if mask & (1 << bit):
                row[name] = reader.uint(32) if bit < 2 else {'Legacy': reader.uint(32), 'Hash': str(reader.uint(64))}
        row.update(_offset=start, _end=reader.at)
        if row.get('TalkSentenceID') in ids:
            require(row['TalkSentenceID'] not in talks, 'Duplicate actual TalkSentenceConfig ID')
            talks[row['TalkSentenceID']] = (index, row)
    reader.eof()
    require(total == tb['rows'] and set(talks) == ids, 'Actual full TalkSentenceConfig EOF/count/ID set differs')
    hashes = {talks[tid][1]['TalkSentenceText']['Hash'] for tid in ids}
    hashes.update(r.get('TextmapTalkSentenceName', {'Hash': '0'})['Hash'] for _, r in talks.values())
    hashes.discard('0')
    kr, entry = evidence['koreanPack'], evidence['entry']
    raw = pack(kr['file'], kr['sha256'], kr['size'])[entry['offset']:entry['offset'] + entry['length']]
    require(digest(raw) == entry['sha256'], 'Actual Korean TextMap entry SHA differs')
    reader = Primitive(raw)
    total = reader.count()
    texts = {}
    seen = set()
    for _ in range(total):
        start = reader.at
        mask = reader.uint(32)
        require(mask & ~7 == 0, 'Unknown actual Korean TextMap active fields')
        legacy, key, text, params = 0, '0', '', 0
        if mask & 1:
            legacy, key = reader.uint(32), str(reader.uint(64))
        if mask & 2:
            text = reader.string()
        if mask & 4:
            params = reader.uint(32)
        require(key not in seen, 'Duplicate actual Korean TextMap hash')
        seen.add(key)
        if key in hashes:
            texts[key] = {'legacy': legacy, 'hash': key, 'raw': text, 'has_params': params, 'offset': start, 'end': reader.at}
    reader.eof()
    require(total == entry['rows'] and set(texts) == hashes, 'Actual full Korean TextMap EOF/count/hash set differs')
    for tid in ids:
        current = data['joins'][str(tid)]['currentOfficialSource']
        require(talks[tid] == (current['tableRowIndex'], current['tableRecord']), 'Actual current TalkSentence row/span differs')
        require(texts[talks[tid][1]['TalkSentenceText']['Hash']] == current['textRecord'], 'Actual current Korean raw/span differs')
        speaker = talks[tid][1].get('TextmapTalkSentenceName', {'Hash': '0'})['Hash']
        require((texts.get(speaker) if speaker != '0' else None) == current['speakerRecord'], 'Actual current speaker raw/span differs')
    return {'actualNativeChoicePrimitives': sum(masks.values()), 'actualChoiceMasks': {str(k): v for k, v in masks.items()},
            'actualTalkTableRowsEOF': tb['rows'], 'actualKoreanTextMapRowsEOF': entry['rows'], 'actualKoreanChoiceIds': len(ids)}


def archive_replay(archive, scenes, needed):
    documents = {}
    with tarfile.open(archive, 'r|gz') as tar:
        for member in tar:
            if not member.isfile():
                continue
            name = member.name.split('/', 1)[-1]
            if name in needed:
                raw = tar.extractfile(member).read()
                require(name not in documents and digest(raw) == needed[name], 'Owner archive source duplicate/SHA differs')
                documents[name] = json.loads(raw)
                if len(documents) == len(needed):
                    break
    require(set(documents) == set(needed), 'Exact owner archive source absent')
    for scene in scenes:
        for owner in scene['owners']:
            chain = owner['ownerChain']
            seed = chain[0]
            require(at(documents[seed['source']], seed['pointer']) == seed['missionId'], 'Actual explicit owner mission ID differs')
            path = chain[1]
            require(at(documents[path['source']], path['pointer']) == path['target'], 'Actual explicit JSON owner path differs')
            edge = chain[2]
            value = at(documents[edge['source']], edge['pointer'])
            parent = at(documents[edge['source']], edge['pointer'].rsplit('/', 1)[0])
            table = documents[edge['tableSource']]
            require(parent['$type'] == 'RPG.GameCore.TriggerPerformance' and parent.get('PerformanceType', '') == edge['performanceType']
                    and value == edge['performanceId'] and at(table, edge['idPointer']) == value
                    and at(table, edge['pathPointer']) == scene['source'], 'Actual typed performance owner lookup differs')
            require({r['PerformancePath'] for r in table if r.get('PerformanceID') == value} == {scene['source']},
                    'Actual performance table lookup is ambiguous')
    return {'actualOwnerArchiveSources': len(documents), 'actualOwnerChains': sum(len(s['owners']) for s in scenes)}


class ProofExpansion:
    """Decode trusted publication receipts without JavaScript or producer imports.

    Shards/UI strings are decoded once per invocation; hashes and lengths are
    checked before a technical proof slot can be used. Static originals are
    checked before this expansion is applied.
    """
    def __init__(self, report, dist=None):
        self.report = report
        self.dist = dist
        self.shards = {}
        self.decoded_inline = {}

    def slot(self, number):
        pool = self.report.get('proofPool', [])
        require(0 <= number < len(pool), 'Compressed proof slot domain')
        item = pool[number]
        shard_id = str(item['shard'])
        shard = self.report['proofShards'][shard_id]
        if shard_id not in self.shards:
            if self.dist is not None:
                url = urlsplit(shard['url'])
                require(not url.scheme and not url.netloc, 'Compressed proof shard external URL')
                relative_path = unquote(url.path)
                base = self.report.get('base', '/starrail-quests')
                require(relative_path.startswith(base + '/'), 'Compressed proof shard base URL differs')
                target = (self.dist / relative_path[len(base) + 1:]).resolve()
                require(target.is_relative_to(self.dist.resolve()), 'Compressed proof shard escaped dist')
                source = target.read_bytes()
                expected = ('__starrailPublicationLoadProofs(' + str(shard['start']) + ',"' + shard['payload']
                            + '",' + str(shard['rawBytes']) + ',' + json.dumps(shard['sizes'], separators=(',', ':')) + ');\n').encode('utf8')
                require(digest(source) == shard['assetSha256'] and source == expected,
                        'Actual compressed proof shard source/receipt differs')
            raw = gzip.decompress(base64.b64decode(shard['payload'], validate=True))
            require(len(raw) == shard['rawBytes'] and digest(raw) == shard['rawSha256'], 'Compressed proof shard hash/length differs')
            values = json.loads(raw)
            require(isinstance(values, list) and len(values) == shard['count'] == len(shard['sizes']), 'Compressed proof shard count differs')
            for i, value in enumerate(values):
                require(isinstance(value, str), 'Compressed proof slot is not text')
                receipt = pool[shard['start'] + i]
                encoded = value.encode('utf8')
                require(len(encoded) == shard['sizes'][i] == receipt['rawBytes']
                        and digest(encoded) == receipt['sha256'] and str(receipt['shard']) == shard_id,
                        'Compressed proof slot byte receipt differs')
            self.shards[shard_id] = values
        offset = number - shard['start']
        require(0 <= offset < len(self.shards[shard_id]), 'Compressed slot outside declared shard')
        return self.shards[shard_id][offset]

    def expand(self, body):
        def inline(match):
            sha, payload, size = match.groups()
            if sha not in self.decoded_inline:
                raw = gzip.decompress(base64.b64decode(payload, validate=True))
                require(len(raw) == int(size) and digest(raw) == sha, 'Inline compressed proof hash/length differs')
                self.decoded_inline[sha] = (payload, size, raw.decode('utf8'))
            require(self.decoded_inline[sha][:2] == (payload, size), 'Ambiguous compressed inline proof payload')
            return self.decoded_inline[sha][2]
        body = re.sub(r'<script data-pc="([0-9a-f]{64})">__starrailPublicationWrite\("([A-Za-z0-9+/=]+)",([0-9]+)\);</script>', inline, body)
        if self.dist is not None:
            for match in re.finditer(r'<script>__spr\(([0-9]+)\);</script>', body):
                number = int(match[1])
                pool = self.report.get('proofPool', [])
                require(0 <= number < len(pool), 'Compressed proof slot domain')
                shard_id = str(pool[number]['shard'])
                url = self.report['proofShards'][shard_id]['url']
                require('<script src="' + url + '" data-pr-shard="' + shard_id + '"></script>' in body,
                        'Actual compressed proof shard import absent from reader')
        body = re.sub(r'<script>__spr\(([0-9]+)\);</script>', lambda m: self.slot(int(m[1])), body)
        replacements = self.report.get('replacements', {})
        for _ in range(16):
            old = body
            def ui(match):
                number = int(match[1])
                rows = self.report.get('uiPool', [])
                require(0 <= number < len(rows) and isinstance(rows[number], str), 'Compressed UI slot domain')
                return rows[number]
            body = re.sub(r'<script>__sp\(([0-9]+)\);</script>', ui, body)
            pattern = r'<script\b[^>]*\bdata-(?:pf|publication-fragment|pj|publication-script)\b[^>]*></script>|<link\b[^>]*\bdata-(?:ps|publication-style)\b[^>]*>'
            body = re.sub(pattern, lambda m: replacements.get(m[0], m[0]), body)
            if old == body:
                break
        else:
            raise ValueError('Compressed UI nesting cycle')
        require(not re.search(r'<script>__spr\(|<script>__sp\(|<script data-pc=', body), 'Compressed proof reference remained unresolved')
        return body


class ChoiceHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = Counter()
        self.rows = []
        self.links = []
        self.body_text = []
        self.proof_markers = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        parent = self.stack[-1] if self.stack else (None, None, None)
        row = parent[1]
        original = parent[2]
        if attrs.get('id'):
            self.ids[attrs['id']] += 1
        if 'data-deep-talk' in attrs:
            row = {'talkId': int(attrs['data-deep-talk']), 'role': attrs.get('data-deep-role'),
                   'passage': attrs.get('data-passage'), 'choiceClass': 'choice' in attrs.get('class', '').split(),
                   'paragraphs': [], 'links': []}
            self.rows.append(row)
        if tag == 'p' and 'original-body' in attrs.get('class', '').split():
            require(row is not None, 'Choice original body outside typed row')
            original = {'anchor': attrs.get('id'), 'text': ''}
            row['paragraphs'].append(original)
        if tag == 'a' and attrs.get('href'):
            link = unquote(attrs['href'])
            self.links.append(link)
            if row:
                row['links'].append(link)
        if 'data-deep-clip-proof' in attrs:
            self.proof_markers.append(attrs['data-deep-clip-proof'])
        if tag not in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'):
            self.stack.append((tag, row, original))

    def handle_endtag(self, tag):
        indices = [i for i, item in enumerate(self.stack) if item[0] == tag]
        if indices:
            del self.stack[indices[-1]:]

    def handle_data(self, text):
        self.body_text.append(text)
        if self.stack and self.stack[-1][2]:
            self.stack[-1][2]['text'] += text


def rendered_scene_check(scene, data, corpus, static, expanded):
    page = ChoiceHTML()
    page.feed(static)
    page.close()
    require(all(n == 1 for n in page.ids.values()), 'Duplicate static reader anchors')
    require([r['talkId'] for r in page.rows] == [r['talkId'] for r in scene['rows']], 'Static choice ID/order differs')
    for row, actual in zip(scene['rows'], page.rows):
        tid, anchor = row['talkId'], row['anchor']
        source = data['joins'][str(tid)]['preservedSource']
        original = at(corpus[source['file']], source['pointer'])
        require(actual['role'] == 'NATIVE_CHOICE' and actual['passage'] == 'choice' and actual['choiceClass'], 'Static choice role/appearance domain differs')
        require(actual['paragraphs'] == [{'anchor': anchor, 'text': original['text']}] and page.ids[anchor] == 1,
                'Static original choice body/anchor differs')
        link = '/starrail-quests/대사/' + Path(source['file']).stem + '.html#talk-' + str(tid)
        require(link in actual['links'], 'Choice return link to preserved original absent')
    for owner in scene['owners']:
        require('/starrail-quests/문서/' + owner['canonicalMission'] + '.html#deep-timeline-originals' in page.links,
                'Explicit owner reading return link absent')
    proof = ChoiceHTML()
    proof.feed(expanded)
    proof.close()
    require(proof.proof_markers == [r['anchor'] for r in scene['rows']] and 'verified-sources' in proof.ids,
            'Rendered technical choice proof markers absent/order differs')
    text = ''.join(proof.body_text)
    require(scene['source'] in text and scene['proof']['entrySha256'] in text and scene['proof']['pack']['sha256'] in text,
            'Rendered native source/hash precision absent')
    for row in scene['rows']:
        source = data['joins'][str(row['talkId'])]['preservedSource']
        original = at(corpus[source['file']], source['pointer'])
        span = next(s for s in row['proof']['fieldSpans'] if s['pointer'] == row['proof']['pointer'])
        require(row['proof']['pointer'] in text and str(original['hash']) in text
                and source['sha256'] in text and str(span['start']) + '–' + str(span['end']) in text,
                'Rendered UInt64/source pointer/native ID span precision absent')
    return len(scene['rows'])


def dist_replay(repo, data, dist, publication_report=None):
    scenes = [s for s in data['scenes'] if s.get('kind') == 'NATIVE_CHOICES']
    corpus = {}
    expansion = None
    for scene in scenes:
        for row in scene['rows']:
            name = data['joins'][str(row['talkId'])]['preservedSource']['file']
            if name not in corpus:
                corpus[name] = read(repo / name)
    rows = 0
    for scene in scenes:
        path = dist / '대화' / ('연출-' + scene['id'] + '.html')
        require(path.is_file(), 'Native choice static reader absent: ' + scene['id'])
        static = path.read_text(encoding='utf8')
        expanded = static
        if re.search(r'__spr\(|__sp\(|__starrailPublicationWrite\(', static):
            if expansion is None:
                report = publication_report or repo / '.codex-work/publication-build-report.json'
                expansion = ProofExpansion(read(report), dist)
            expanded = expansion.expand(static)
        rows += rendered_scene_check(scene, data, corpus, static, expanded)
    return {'staticChoiceReaders': len(scenes), 'staticChoiceOriginals': rows,
            'compressedProofShardsDecodedOnce': len(expansion.shards) if expansion else 0}


def self_test(repo, data, inverse):
    tests = []
    def reject(name, fn):
        try:
            fn()
        except (ValueError, KeyError, IndexError, UnicodeError, struct.error):
            tests.append(name)
            return
        raise ValueError('Negative native choice test accepted: ' + name)
    sample = next(s for s in data['scenes'] if s.get('kind') == 'NATIVE_CHOICES' and s['id'] not in BASELINE)
    # Test only the owned choice slice; cloning the unrelated 52k Timeline rows
    # for every mutation adds cost without any independent assertion.
    test_data = dict(data)
    test_data['scenes'] = [s for s in data['scenes'] if s.get('kind') == 'NATIVE_CHOICES']
    choice_ids = {str(r['talkId']) for s in test_data['scenes'] for r in s['rows']}
    test_data['joins'] = {key: data['joins'][key] for key in choice_ids}
    test_data['sourceProofs'] = {}
    def mutate(name, fn):
        bad = copy.deepcopy(test_data)
        scene = next(s for s in bad['scenes'] if s['id'] == sample['id'])
        fn(bad, scene)
        reject(name, lambda: source_check(repo, bad, inverse))
    mutate('choice role mismatch', lambda d, s: s['rows'][0].__setitem__('role', 'SPOKEN'))
    mutate('native parent type mismatch', lambda d, s: s['rows'][0].__setitem__('parentTaskType', 'RPG.GameCore.PlaySimpleTalk'))
    mutate('native option type mismatch', lambda d, s: s['rows'][0]['option'].__setitem__('$type', PARENT))
    mutate('native ID mismatch', lambda d, s: s['rows'][0].__setitem__('talkId', s['rows'][0]['talkId'] + 1))
    mutate('option array index mismatch', lambda d, s: s['rows'][0].__setitem__('optionIndex', 999))
    mutate('choice order mismatch', lambda d, s: s['rows'].reverse())
    mutate('choice span mismatch', lambda d, s: s['rows'][0]['proof']['fieldSpans'][0].__setitem__('start', 999999))
    mutate('whole source EOF mismatch', lambda d, s: s['proof'].__setitem__('wholeFieldEOF', 1))
    mutate('fake mission owner', lambda d, s: s['owners'][0].__setitem__('mission', 'quest-1'))
    mutate('invented region owner metadata', lambda d, s: s['owners'][0].__setitem__('region', 'Unknown'))
    mutate('membership hash mismatch', lambda d, s: s['owners'][0]['ownerChain'][0].__setitem__('membershipSha256', '0' * 64))
    mutate('owner path discontinuity', lambda d, s: s['owners'][0]['ownerChain'][1].__setitem__('target', 'Story/Unknown.json'))
    mutate('wrong performance table domain', lambda d, s: s['owners'][0]['ownerChain'][2].__setitem__('tableSource', 'ExcelOutput/PerformanceAS.json'))
    mutate('Korean raw mismatch', lambda d, s: d['joins'][str(s['rows'][0]['talkId'])].__setitem__('raw', 'invalid'))
    mutate('UInt64 precision converted to number', lambda d, s: d['joins'][str(s['rows'][0]['talkId'])]['currentOfficialSource']['textRecord'].__setitem__('hash', 2 ** 63))
    mutate('private source path', lambda d, s: s['proof']['pack'].__setitem__('path', 'Q:/private/source.bytes'))
    mutate('legacy sixteen original choices changed', lambda d, s: next(x for x in d['scenes'] if x['id'] in BASELINE)['rows'][0].__setitem__('anchor', 'invalid'))
    bad_inverse = dict(inverse)
    bad_inverse['readerLinks'] = dict(inverse['readerLinks'])
    bad_inverse['readerLinks'][str(sample['rows'][0]['talkId'])] = []
    reject('exact inverse anchor absence', lambda: source_check(repo, data, bad_inverse))
    reject('UInt32 varint overflow', lambda: Primitive(b'\x80\x80\x80\x80\x10').uint(32))
    reject('truncated varint', lambda: Primitive(b'\x80').uint(32))
    reject('noncanonical varint', lambda: Primitive(b'\x80\0').uint(32))
    reject('boolean primitive mismatch', lambda: Primitive(b'\x02').boolean())
    # Independent minimal native fixture, including both signed enum primitives.
    raw = bytes.fromhex('a20f0202000d0128040141')
    option = {'$type': OPTION, 'TalkSentenceID': 1, 'OptionIconType': {'EnumIndex': 20, 'Value': 2}, 'TriggerCustomString': 'A'}
    task = {'$type': PARENT, 'OptionList': [option]}
    fields = {'task': task}
    fixture_spans = [{'pointer': '', 'start': 0, 'end': 11}, {'pointer': '/task', 'start': 0, 'end': 11},
                     {'pointer': '/task/OptionList', 'start': 3, 'end': 11},
                     {'pointer': '/task/OptionList/0', 'start': 4, 'end': 11},
                     {'pointer': '/task/OptionList/0/TalkSentenceID', 'start': 6, 'end': 7},
                     {'pointer': '/task/OptionList/0/OptionIconType', 'start': 7, 'end': 9},
                     {'pointer': '/task/OptionList/0/TriggerCustomString', 'start': 9, 'end': 11}]
    fixture = {'proof': {'entrySha256': digest(raw), 'wholeFieldEOF': 11, 'fields': fields, 'fieldSpans': fixture_spans},
               'options': [{'pointer': '/task', 'optionListPointer': '/task/OptionList', 'task': task, 'options': [option]}]}
    require(choice_primitives(raw, fixture) == Counter({(2, 13): 1}), 'Native minimal positive fixture differs')
    for label, offset, value in [('actual native parent1954 mismatch', 0, 0xa3),
                                 ('actual native parent mask mismatch', 2, 0),
                                 ('actual native option0 mismatch', 4, 1),
                                 ('actual native option mask mismatch', 5, 12),
                                 ('actual native UInt32 TalkID mismatch', 6, 2),
                                 ('actual native icon enum mismatch', 7, 42)]:
        mutated = bytearray(raw)
        mutated[offset] = value
        fake = copy.deepcopy(fixture)
        fake['proof']['entrySha256'] = digest(mutated)
        reject(label, lambda mutated=bytes(mutated), fake=fake: choice_primitives(mutated, fake))
    reject('native entry SHA mismatch', lambda: choice_primitives(raw, {**fixture, 'proof': {**fixture['proof'], 'entrySha256': '0' * 64}}))
    corpus = {}
    for row in sample['rows']:
        name = data['joins'][str(row['talkId'])]['preservedSource']['file']
        if name not in corpus:
            corpus[name] = read(repo / name)
    original_html, proof_html = [], []
    for row in sample['rows']:
        tid = row['talkId']
        source = data['joins'][str(tid)]['preservedSource']
        original = at(corpus[source['file']], source['pointer'])
        original_html.append('<div class="choice" data-deep-talk="' + str(tid)
                             + '" data-deep-role="NATIVE_CHOICE" data-passage="choice"><p class="original-body" id="'
                             + row['anchor'] + '">' + escape(original['text']) + '</p><a href="/starrail-quests/대사/'
                             + Path(source['file']).stem + '.html#talk-' + str(tid) + '">원문</a></div>')
        span = next(s for s in row['proof']['fieldSpans'] if s['pointer'] == row['proof']['pointer'])
        proof_html.append('<li data-deep-clip-proof="' + row['anchor'] + '">' + escape(row['proof']['pointer'])
                          + ' ' + str(span['start']) + '–' + str(span['end']) + ' ' + original['hash'] + ' '
                          + source['sha256'] + '</li>')
    nav = ''.join('<a href="/starrail-quests/문서/' + owner['canonicalMission'] + '.html#deep-timeline-originals">임무</a>'
                  for owner in sample['owners'])
    metadata = escape(sample['source']) + ' ' + sample['proof']['entrySha256'] + ' ' + sample['proof']['pack']['sha256']
    metadata += '<ol>' + ''.join(proof_html) + '</ol>'
    html = nav + ''.join(original_html) + '<details id="verified-sources"><summary>출처</summary>' + metadata + '</details>'
    rendered_scene_check(sample, data, corpus, html, html)
    reject('HTML choice role mismatch', lambda: rendered_scene_check(sample, data, corpus, html.replace('data-deep-role="NATIVE_CHOICE"', 'data-deep-role="SPOKEN"'), html))
    reject('HTML original choice mutation', lambda: rendered_scene_check(sample, data, corpus, html.replace('class="original-body"', 'class="original-body" data-bad="1"').replace('</p>', 'extra</p>'), html))
    reject('HTML choice original absence', lambda: rendered_scene_check(sample, data, corpus, html.replace(original_html[0], ''), html))
    reject('HTML original return link absence', lambda: rendered_scene_check(sample, data, corpus, html.replace('.html#talk-', '.html#bad-'), html))
    reject('HTML technical span precision mismatch', lambda: rendered_scene_check(sample, data, corpus, html, html.replace('–', '-')))
    raw = metadata.encode('utf8')
    report = {'proofPool': [{'shard': 0, 'rawBytes': len(raw), 'sha256': digest(raw)}],
              'proofShards': {'0': {'start': 0, 'count': 1, 'sizes': [len(raw)],
                                   'payload': base64.b64encode(gzip.compress(canonical([metadata]), mtime=0)).decode(),
                                   'rawBytes': len(canonical([metadata])), 'rawSha256': digest(canonical([metadata]))}}}
    codec = ProofExpansion(report)
    compressed = html.replace(metadata, '<script>__spr(0);</script>')
    rendered_scene_check(sample, data, corpus, compressed, codec.expand(compressed))
    require(codec.expand(compressed) == html and len(codec.shards) == 1, 'Technical expansion cache replay differs')
    bad_report = copy.deepcopy(report)
    bad_report['proofShards']['0']['rawSha256'] = '0' * 64
    reject('Compressed shard hash mismatch', lambda: ProofExpansion(bad_report).expand(compressed))
    return tests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--official-root', type=Path, help='Explicit root containing the pinned native and official pack files')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--dist', type=Path)
    parser.add_argument('--publication-report', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    raw = (repo / 'data/deep-timeline-dialogue.json').read_bytes()
    data = json.loads(raw)
    inverse = read(repo / 'data/deep-dialogue-attribution.json')
    require(inverse['schema'] == 'starrail-deep-dialogue-attribution.v1'
            and inverse['evidence']['deepTimelineSha256'] == digest(raw), 'Exact inverse source SHA differs')
    scenes, needed, counts = source_check(repo, data, inverse)
    if args.official_root:
        counts.update(official_replay(args.official_root.resolve(), data, scenes))
    if args.archive:
        counts.update(archive_replay(args.archive.resolve(), scenes, needed))
    if args.dist:
        counts.update(dist_replay(repo, data, args.dist.resolve(), args.publication_report))
    tests = self_test(repo, data, inverse) if args.self_test else []
    report = {'schema': 'starrail-native-choice-independent-verification.v1', 'status': 'PASS',
              'deepTimelineSha256': digest(raw), 'closedDeltaSha256': [d['sha256'] for d in data['evidence']['nativeChoiceDeltas']],
              'counts': counts, 'negativeSelfTests': tests,
              'verifiedSurfaces': {'preservedSource': True, 'actualPackPrimitivesAndOfficialKorean': bool(args.official_root),
                                   'actualOwnerArchive': bool(args.archive), 'staticReaderHTML': bool(args.dist)},
              'limits': ['Serialized option list order preserved; actual playback branches remain unverified.',
                         'Choice parent/list/option primitives are independently consumed at their recorded EOF spans.',
                         'Other native task fields retain their producer/source evidence; this verifier does not execute or independently decode every task.']}
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, IndexError, UnicodeError, OSError, struct.error, tarfile.TarError) as error:
        print('Native choice verification FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
