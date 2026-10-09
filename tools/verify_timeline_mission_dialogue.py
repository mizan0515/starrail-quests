"""Read-only candidate gate for typed Timeline dialogue and built mission readers.

Run from any directory with --site. No generator is imported or run, no files are
written, and Python bytecode is disabled. Audit mode compares independently
preserved native/official/context artifacts. --deep-replay rehashes saved native
objects and metadata archive members; optional --official-root/--skill also
decodes the official packs through the existing read-only decoder.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import tarfile
from urllib.parse import unquote, urlsplit

sys.dont_write_bytecode = True
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def at(obj, pointer):
    require(pointer == '' or pointer.startswith('/'), 'Invalid JSON pointer')
    for token in pointer.split('/')[1:]:
        key = token.replace('~1', '/').replace('~0', '~')
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    return obj


def same(actual, expected, label):
    require(actual == expected, label + ' differs from preserved input')


def hash_strings(value):
    # The preserved join serializes UInt64 hash fields as decimal strings for JS.
    if isinstance(value, list):return [hash_strings(v) for v in value]
    if isinstance(value, dict):
        return {k:str(v) if k in ('Hash','hash') and type(v) is int else hash_strings(v) for k,v in value.items()}
    return value


def safe_path(site, relative):
    require(isinstance(relative, str) and not re.search(r'^[A-Za-z]:|^[/\\]|\\', relative), 'Unsafe public relative path')
    require('..' not in PurePosixPath(relative).parts, 'Traversal in public relative path')
    path = (site / relative).resolve()
    require(path.is_relative_to(site.resolve()), 'Public path outside site')
    return path


def iter_scenes(data):
    for mission, scenes in data['missions'].items():
        for scene in scenes:
            yield mission, scene


def artifact_check(data, site, row_check, privacy_check, audit=None, joins=None, contexts=None,
                   expected_counts=None, expected_conditions=4, expected_options=6,
                   expected_repeats=None, owner_kind='EXPLICIT_MAIN_MISSION_ID'):
    require(not sys.flags.optimize, 'Gate must run without Python -O')
    privacy_check(data)
    same(data['schema'], 'starrail-timeline-mission-dialogue.v1', 'schema')
    evidence = data['evidence']
    same(evidence['installedVersion'], 'UNVERIFIED', 'installed version boundary')
    official = evidence['officialKorean']
    same(official['clientVersion'], 'OSPRODWin4.6.0', 'official text version')
    require(official['entry']['fullEofVerified'] and official['talkTable']['fullEofVerified'], 'Missing official full-entry proof')
    aliases = read(site / 'data/aliases.json')
    scenes = list(iter_scenes(data))
    anchors = [scene['anchor'] for _, scene in scenes]
    require(len(set(anchors)) == len(anchors), 'Timeline scene anchors collide')
    rows = [row for _, scene in scenes for row in scene['rows']]
    counts = {'missions': len(data['missions']), 'scenes': len(scenes), 'rows': len(rows),
              'uniqueTalkIds': len({r['talk_id'] for r in rows})}
    same(data['counts'], counts, 'counts')
    same(counts, expected_counts if expected_counts is not None else
         {'missions': 30, 'scenes': 80, 'rows': 1120, 'uniqueTalkIds': 1119}, 'frozen typed cohort')
    cache = {}
    def document(relative, expected_sha):
        if relative not in cache:
            p = safe_path(site, relative)
            cache[relative] = (sha(p), read(p))
        digest, value = cache[relative]
        same(digest, expected_sha, 'preserved file SHA ' + relative)
        return value
    for mission, scene in scenes:
        require(scene['recordType'] == 'TIMELINE_DIALOGUE' and
                scene['mapping'] == 'EXACT_TYPED_TIMELINE_TO_OFFICIAL_KOREAN_TALK', 'Source kind mislabelled')
        owner = scene['ownership'][0]
        require(owner['kind'] == owner_kind, 'Missing explicit ownership seed')
        canonical = 'quest-' + str(owner['canonicalMissionId'])
        same(aliases.get(canonical, canonical), mission, 'owner alias target')
        doc = read(site / 'data/documents' / (mission + '.json'))
        require(canonical in doc.get('missionParts', [doc['id']]), 'Canonical owner missing from preserved parts')
        require('quest-' + str(owner['missionId']) in doc.get('missionParts', [doc['id']]), 'Explicit seed not part of target')
        value = at(document(owner['membershipSource'], owner['membershipSha256']), owner['membershipPointer'])
        same(value, 'quest-' + str(owner['missionId']), 'explicit membership pointer')
        source = scene['timelineSource']
        same(source['ownerMissionId'], owner['missionId'], 'native owner seed')
        same(scene['anchor'], 'timeline-' + hashlib.sha256(scene['source'].encode()).hexdigest()[:16], 'deterministic source anchor')
        same(source['containerKey'], 'assets/asbres/' + scene['source'].lower(), 'exact Unity root container route')
        for value in [source['rootPathID'], source['talkTrackPathID'], *source['parentRouteTalkToRoot']]:
            require(isinstance(value, str) and re.fullmatch(r'-?\d+', value), '64-bit PPtr must remain decimal string')
        span = source['timelineFieldByteProof']
        require(0 <= span['start'] < span['end'] <= source['entryBytes'], 'TimelineName span outside source')
        same(span['pointer'], source['timelineFieldPointer'], 'TimelineName pointer proof')
        order = [(r['timelineClip']['start'], r['timelineClip']['trackClipIndex']) for r in scene['rows']]
        same(order, sorted(order), 'within-track reading order')
        same(source['timeSortedIndices'], [r['timelineClip']['trackClipIndex'] for r in scene['rows']], 'clip index order')
        same(Counter(source['serializedIndices']), Counter(source['timeSortedIndices']), 'serialized clip coverage')
        require(len(set(source['serializedIndices'])) == len(source['serializedIndices']), 'Repeated serialized index')
        require(all(c['branch'] in ('SuccessTaskList', 'FailedTaskList') for c in scene['triggerContext']['conditions']), 'Unknown trigger branch semantics')
        for option in scene['optionReferences']:
            require(option['role'] == 'NON_SPOKEN_OPTION_REFERENCE', 'Option marker promoted to speech')
            require(option['talk_id'] not in {r['talk_id'] for r in scene['rows']}, 'Nonspoken option counted in spoken scene')
            source_record = option['officialSource']
            table, text = source_record['tableRecord'], source_record['textRecord']
            same(option['talk_id'], table['TalkSentenceID'], 'option table ID')
            same(option['hash'], str(table['TalkSentenceText']['Hash']), 'option table text hash')
            same(option['hash'], str(text['hash']), 'option TextMap hash')
            same(option['raw'], text['raw'], 'option raw text')
            require(option['references'], 'Option marker lacks same-DS reference')
        for row in scene['rows']:
            row_check(row, official)
            same(row['voice'], row['officialSource']['tableRecord'].get('VoiceID', 0), 'voice provenance')
            require(row['label'] == '대사', 'Spoken clip changed passage kind')
            clip = row['timelineClip']
            require(all(type(clip[k]) in (int, float) and math.isfinite(clip[k]) for k in ('start', 'duration')), 'Nonfinite clip timing')
            require(clip['start'] >= 0 and clip['duration'] > 0, 'Invalid clip timing')
            require(isinstance(clip['pathID'], str) and isinstance(clip['trackPathID'], str), 'Lossy clip PPtr')
            same(clip['trackPathID'], source['talkTrackPathID'], 'clip track')
            low, high = clip['talkIDSpan']
            require(0 <= low < high <= clip['objectByteSize'] and high - low == 4, 'TalkID span outside typed native object')
            preserved = row['preservedSource']
            local = at(document(preserved['file'], preserved['sha256']), preserved['pointer'])
            for key in ('talk_id', 'text', 'hash', 'voice'):
                same(str(row[key]) if key == 'hash' else row[key], str(local[key]) if key == 'hash' else local[key], 'preserved row ' + key)
            target = '대사/' + Path(preserved['file']).stem + '.html#talk-' + str(row['talk_id'])
            same(row['url'], target, 'original dialogue link')
    same(sum(len(s['triggerContext']['conditions']) for _, s in scenes), expected_conditions, 'recognized trigger conditions')
    same(sum(len(s['optionReferences']) for _, s in scenes), expected_options, 'nonspoken option refs')
    repeat = Counter(r['talk_id'] for r in rows)
    same({tid: n for tid, n in repeat.items() if n > 1}, expected_repeats if expected_repeats is not None else
         {154010409: 2}, 'actual repeated clip occurrences')
    if audit is not None:
        require(joins is not None and contexts is not None, 'Audit requires joins and contexts')
        lookup = {r['talkID']: r for r in joins['joins']}
        context_map = {r['timelineName']: r for r in contexts['timelines']}
        expected = {}
        empty = []
        for timeline in audit['timelines']:
            require(timeline['ownerStatus'] == 'ONE_EXPLICIT_OWNER' and len(timeline['owners']) == 1, 'Ambiguous native owner')
            owner = timeline['owners'][0]
            require(owner['ownerExactValidation'] == 'PASS' and all(c['status'] == 'PASS' for c in owner['ownerSourceChecks']), 'Owner input not fully validated')
            target = aliases.get(owner['mission'], owner['mission'])
            if not timeline['spokenClips']:
                empty.append({'mission': owner['mission'], 'source': timeline['timelineName']})
            else:
                expected[timeline['timelineName']] = (target, timeline)
        same(set(expected), {s['source'] for _, s in scenes}, 'audited scene coverage')
        same(data['emptyTimelines'], empty, 'empty native timelines')
        for mission, scene in scenes:
            target, native = expected[scene['source']]
            same(mission, target, 'audited canonical owner')
            owner = native['owners'][0]
            same(scene['ownership'], owner['ownerChain'], 'audited owner chain')
            source = scene['timelineSource']
            for key, native_key in [('logicalJsonPath','logicalJsonPath'), ('nameHash','nameHash'), ('entrySha256','entrySha256'), ('timelineFieldPointer','timelineFieldPointer'), ('timelineFieldByteProof','timelineFieldByteProof'), ('entryBytes','consumedBytes')]:
                same(source[key], owner[native_key], 'DS source ' + key)
            receipt = native['sourceReceipt']
            for key, value in [('blockFile',Path(receipt['block']['path']).name), ('blockSha256',receipt['block']['sha256']), ('bundleOffset',receipt['expectedSpan']['offset']), ('bundleBytes',receipt['expectedSpan']['length']), ('cabName',receipt['expectedSpan']['cab']), ('cabSha256',receipt['cabSha256']), ('containerKey',native['directRootContainer']['key']), ('rootPathID',str(native['rootPathID'])), ('talkTrackPathID',str(native['talkTrackPathID'])), ('parentRouteTalkToRoot',list(map(str,native['parentRouteTalkToRoot']))), ('serializedIndices',[c['trackClipIndex'] for c in native['spokenClips']])]:
                same(source[key], value, 'native source ' + key)
            indexed = {c['trackClipIndex']: c for c in native['spokenClips']}
            same(len(scene['rows']), len(indexed), 'native occurrence count')
            for row in scene['rows']:
                clip = row['timelineClip']; original = indexed[clip['trackClipIndex']]
                same(row['talk_id'], original['talkID'], 'actual typed TalkID')
                obj = original['sourceObject']
                require(original['assetClass'] == obj['script']['m_ClassName'] == 'PlaySimpleTalkClip' and original['assetEOF'] == obj['byteSize'], 'Native typed EOF boundary')
                same(original['talkIDField']['field'], 'PlaySimpleTalkClip.Config.TalkSentenceID', 'typed field')
                for key, value in [('pathID',str(obj['pathID'])), ('trackPathID',str(original['trackPathID'])), ('objectByteStart',obj['byteStart']), ('objectByteSize',obj['byteSize']), ('objectSha256',obj['sha256']), ('talkIDSpan',original['talkIDField']['span']), ('start',original['timelineClip']['m_Start']), ('duration',original['timelineClip']['m_Duration'])]:
                    same(clip[key], value, 'actual native clip ' + key)
                same(source['trackRawSha256'], original['trackRawSha256'], 'actual native track digest')
                join = lookup[row['talk_id']]
                require(join['tableMatchCount'] == join['preservedMatchCount'] == 1 and join['status'] == 'EXACT_TALKID_TABLE_TEXTMAP_JOIN', 'Ambiguous official join')
                for key, value in [('tableRow',join['tableRow']), ('tableRecord',join['tableRecord']), ('textRecord',join['textRecord']), ('speakerRecord',join['speakerRecord'])]:
                    same(row['officialSource'][key], value, 'exact official ' + key)
                same(row['raw'], join['originalText'], 'exact raw Korean text')
            context = context_map[scene['source']]
            co = next(o for o in context['owners'] if o['mission'] == owner['mission'] and o['timelineFieldPointer'] == owner['timelineFieldPointer'])
            trigger = co['originalOwnerTrigger']; projected = scene['triggerContext']
            for key, value in [('source',trigger['source']), ('sourceSha256',trigger['sourceEvidence']['sha256']), ('referencePointer',trigger['referencePointer']), ('conditions',trigger['context']['conditions']), ('performanceId',trigger['task']['PerformanceID']), ('dsConditions',co['strictBinaryDSContext']['conditions'])]:
                same(projected[key], value, 'exact trigger context ' + key)
            markers = [m for m in context['simpleTalkMarkers'] if m['nonzero']]
            same([o['talk_id'] for o in scene['optionReferences']], [m['referenceOptionTalkID'] for m in markers], 'exact nonspoken marker coverage')
            option_joins = {j['talkID']:j for j in contexts['optionReferenceKoreanJoins']}
            for option, marker in zip(scene['optionReferences'], markers):
                join = option_joins[option['talk_id']]
                for key, value in [('pathID',str(marker['sourceObject']['pathID'])), ('objectSha256',marker['sourceObject']['sha256']), ('start',marker['timelineStart']), ('text',join['readableText']), ('raw',join['originalText']), ('hash',join['textmapHash']), ('references',[{'source':r['source'],'pointer':r['pointer'],'entrySha256':r['entrySha256']} for r in marker['sameExplicitDSReferences']])]:
                    same(option[key], value, 'exact option ref ' + key)
                for key in ('tableRow','tableRecord','textRecord'):
                    same(option['officialSource'][key], join[key], 'exact option official ' + key)
    return counts


class Node:
    def __init__(self, tag='', attrs=None, parent=None):
        self.tag, self.attrs, self.parent = tag, attrs or {}, parent
        self.children = []
    def text(self):
        return ''.join(c if isinstance(c,str) else c.text() for c in self.children)
    def descendants(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.descendants()
    def ancestor(self, predicate):
        node = self.parent
        while node is not None:
            if predicate(node): return True
            node = node.parent
        return False


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node(); self.current = self.root
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.current); self.current.children.append(node)
        if tag not in VOID: self.current = node
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:self.handle_endtag(tag)
    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent; return
            node = node.parent
    def handle_data(self, text): self.current.children.append(text)


def classed(node, value): return value in node.attrs.get('class','').split()


def html_scene_check(tree, scene):
    nodes = list(tree.root.descendants())
    chosen = [n for n in nodes if n.attrs.get('id') == scene['anchor']]
    require(len(chosen) == 1, 'Built typed scene missing/duplicated')
    node = chosen[0]
    require(node.ancestor(lambda n:'data-mission-reader' in n.attrs) and node.ancestor(lambda n:classed(n,'mission-scenes')), 'Typed scene outside primary reader')
    require(not node.ancestor(lambda n:'data-reference-scenes' in n.attrs), 'Typed scene demoted to reference')
    children = list(node.descendants())
    visible_rows = [n for n in children if classed(n,'original-row')]
    same(len(visible_rows), len(scene['rows']), 'HTML typed row count')
    for index, (rendered, source) in enumerate(zip(visible_rows, scene['rows']),1):
        parts = list(rendered.descendants())
        bodies = [n for n in parts if classed(n,'original-body')]
        require(len(bodies) == 1, 'HTML original body missing/duplicated')
        same(bodies[0].attrs.get('id'), scene['anchor']+'-row-'+str(index), 'HTML row order/anchor')
        same(bodies[0].text(), source['text'], 'HTML exact original text')
        same(rendered.attrs.get('data-passage'), 'dialogue', 'HTML spoken filter role')
        same(rendered.attrs.get('data-speaker'), source['speaker'] or '화자 미지정', 'HTML speaker')
        proofs = [n for n in parts if 'data-official-talk-proof' in n.attrs]
        require(len(proofs)==1 and proofs[0].attrs['data-official-talk-proof']==str(source['talk_id']), 'HTML official proof misbound')
        proof_text = proofs[0].text()
        for value in (source['raw'],source['hash'],source['speaker_hash'],source['officialSource']['clientVersion'].replace('OSPRODWin','')):
            require(str(value) in proof_text, 'HTML official citation field missing')
        links = [n for n in parts if n.tag=='a' and unquote(urlsplit(n.attrs.get('href','')).path).endswith('/'+source['url'].split('#')[0]) and urlsplit(n.attrs.get('href','')).fragment==source['url'].split('#')[1]]
        require(len(links)==1 and 'data-reading-link' in links[0].attrs and links[0].attrs.get('id'), 'HTML original source CTA/return origin missing')
    proof = [n for n in children if n.attrs.get('data-timeline-proof')==scene['anchor']]
    require(len(proof)==1, 'HTML typed native proof missing/duplicated')
    visible_conditions = [n for n in children if 'data-timeline-condition' in n.attrs]
    same([n.attrs['data-timeline-condition'] for n in visible_conditions], [c['predicatePointer'] for c in scene['triggerContext']['conditions']], 'HTML trigger condition coverage')
    for rendered, condition in zip(visible_conditions,scene['triggerContext']['conditions']):
        require(str(condition['predicate']['SubMissionID']) in rendered.text(), 'HTML sub-mission condition missing')
        branch = '조건 충족 경로' if condition['branch']=='SuccessTaskList' else '조건 미충족 경로'
        require(branch in rendered.text(), 'HTML condition branch reversed')
    options = [n for n in proof[0].descendants() if 'data-timeline-option' in n.attrs]
    same([n.attrs['data-timeline-option'] for n in options], [str(o['talk_id']) for o in scene['optionReferences']], 'HTML nonspoken option coverage')
    for rendered, option in zip(options,scene['optionReferences']):
        require(option['text'] in rendered.text() and option['hash'] in rendered.text(), 'HTML option source text missing')
    indices = [n.attrs['data-timeline-clip'] for n in proof[0].descendants() if 'data-timeline-clip' in n.attrs]
    same(indices, [str(r['timelineClip']['trackClipIndex']) for r in scene['rows']], 'HTML proof occurrence/order')
    require('임무 전체의 장면 순서와 선택지에 따른 재생 경로는 확인 중입니다.' in node.text(), 'HTML runtime scope disclosure missing')
    require('설치본의 출시 버전은 미확인입니다.' in proof[0].text(), 'HTML installed-version boundary missing')


def html_check(data, dist):
    count = 0; trees = {}; targets = {}
    for mission, scene in iter_scenes(data):
        if mission not in trees:
            p = dist / '문서' / (mission + '.html')
            require(p.is_file(), 'Built mission page missing '+mission)
            trees[mission] = Tree(p.read_text('utf-8'))
            ids = Counter(n.attrs['id'] for n in trees[mission].root.descendants() if n.attrs.get('id'))
            require(all(v==1 for v in ids.values()), 'Duplicate DOM ids in mission '+mission)
        html_scene_check(trees[mission], scene); count += 1
        for row in scene['rows']:
            relative, anchor = row['url'].split('#')
            if relative not in targets:
                p = dist / relative
                require(p.is_file(), 'Original CTA target page missing')
                targets[relative] = Counter(n.attrs['id'] for n in Tree(p.read_text('utf-8')).root.descendants() if n.attrs.get('id'))
            require(targets[relative][anchor]==1, 'Original CTA target anchor missing/duplicated')
    return count, trees


def deep_check(audit, contexts, official_root=None, skill=None, data=None):
    objects = blocks = 0; seen_blocks = set()
    resolution_input = next(i for i in audit['inputs'] if str(i['path']).endswith('cohort-resolution.json'))
    same(sha(resolution_input['path']),resolution_input['sha256'],'native decoded identity receipt SHA')
    resolution=read(resolution_input['path']); ds={}
    for timeline in audit['timelines']:
        owner=timeline['owners'][0];resolved=at(resolution,owner['resolutionPointer'])
        raw_entry=bytes.fromhex(resolved['entryRawHex'])
        same(hashlib.sha256(raw_entry).hexdigest(),owner['entrySha256'],'native DS full entry SHA')
        same(len(raw_entry),owner['consumedBytes'],'native DS full entry EOF')
        same(at(resolved['decoded'],owner['timelineFieldPointer']),timeline['timelineName'],'native decoded TimelineName pointer')
        span=owner['timelineFieldByteProof']
        require(timeline['timelineName'].encode() in raw_entry[span['start']:span['end']],'Native TimelineName span lacks exact path bytes')
        ds[owner['logicalJsonPath']]=resolved['decoded']
        receipt = timeline['sourceReceipt']; block = receipt['block']
        if block['path'] not in seen_blocks:
            same(Path(block['path']).stat().st_size,block['bytes'],'actual source block size')
            same(sha(block['path']),block['sha256'],'actual source block SHA')
            seen_blocks.add(block['path']); blocks += 1
        for clip in [*timeline['spokenClips'],*[c for c in timeline['talkTrackClips'] if c.get('assetClass')=='SimpleTalkMarkerClip' and c.get('optionReference')]]:
            raw = Path(clip['assetRawPath']).read_bytes(); obj=clip['sourceObject']
            same(len(raw),obj['byteSize'],'native typed object length')
            same(hashlib.sha256(raw).hexdigest(),obj['sha256'],'native typed object SHA')
            if clip['assetClass']=='PlaySimpleTalkClip':
                low,high=clip['talkIDField']['span']
                require(high-low==4, 'Unsupported typed TalkID encoding')
                same(struct.unpack('<i',raw[low:high])[0],clip['talkID'],'actual native TalkID bytes')
            objects += 1
    archive = next(Path(i['path']) for i in contexts['inputs'] if str(i['path']).endswith('.tar.gz'))
    archive_input = next(i for i in contexts['inputs'] if str(i['path']).endswith('.tar.gz'))
    same(sha(archive),archive_input['sha256'],'exact metadata archive SHA')
    wanted=dict(contexts['sourceFragments']); decoded={}
    if data is not None:
        for relative,digest in data['evidence']['metadataSourceFiles'].items():
            if relative not in contexts['missingExactArchiveSources']:
                wanted.setdefault(relative,{'sha256':digest})
    with tarfile.open(archive,'r:gz') as tf:
        for member in tf:
            relative=member.name.split('/',1)[-1]
            if relative in wanted:
                raw=tf.extractfile(member).read()
                same(hashlib.sha256(raw).hexdigest(),wanted[relative]['sha256'],'exact archive fragment '+relative)
                decoded[relative]=json.loads(raw)
    require(set(decoded)==set(wanted),'Missing selected archive fragment')
    for t in contexts['timelines']:
        for owner in t['owners']:
            trigger=owner['originalOwnerTrigger']; source=decoded[trigger['source']]
            same(at(source,trigger['referencePointer']),trigger['task']['PerformanceID'],'actual trigger ID pointer')
            for c in trigger['context']['conditions']:
                same(at(source,c['predicatePointer']),c['predicate'],'actual condition predicate')
                require(trigger['referencePointer'].startswith(c['branchPointer']+'/'),'Trigger outside annotated branch')
        for marker in t['simpleTalkMarkers']:
            if marker['nonzero']:
                for ref in marker['sameExplicitDSReferences']:
                    same(at(ds[ref['source']],ref['pointer']),marker['referenceOptionTalkID'],'actual same-DS nonspoken option pointer')
    if data is not None:
        for _,scene in iter_scenes(data):
            for edge in scene['ownership']:
                if edge['source'] not in decoded:continue  # partial source originals explicitly unavailable
                source=decoded[edge['source']]
                expected={'EXPLICIT_MAIN_MISSION_ID':edge.get('missionId'),'EXPLICIT_JSON_PATH':edge.get('target'),'EXPLICIT_SUBMISSION_FINISH_SCOPE':edge.get('submissionId'),'EXPLICIT_PERFORMANCE_LOOKUP':edge.get('performanceId')}[edge['kind']]
                same(at(source,edge['pointer']),expected,'actual explicit owner pointer')
                if edge['kind']=='EXPLICIT_PERFORMANCE_LOOKUP':
                    table=decoded[edge['tableSource']]
                    same(at(table,edge['idPointer']),edge['performanceId'],'performance table ID')
                    same(at(table,edge['pathPointer']),edge['target'],'performance table path')
    official_rows=0
    if official_root or skill:
        require(official_root and skill and data is not None,'Full official replay requires both root and skill')
        from build_official_mission_talks import decode_talk_input
        talks,texts,actual,_=decode_talk_input(official_root,skill)
        for key in ('manifestSha256','catalogSha256','koreanPack','entry','talkTable'):
            same(data['evidence']['officialKorean'][key],actual[key],'decoded official evidence '+key)
        for _,scene in iter_scenes(data):
            for row in scene['rows']:
                o=row['officialSource']
                same(o['tableRecord'],hash_strings(talks[o['tableRow']]),'official original table row')
                same(o['textRecord'],hash_strings(texts[row['hash']]),'official original TextMap row')
                same(o['speakerRecord'],hash_strings(texts.get(row['speaker_hash'])),'official original speaker row')
                official_rows += 1
            for option in scene['optionReferences']:
                o=option['officialSource']
                same(o['tableRecord'],hash_strings(talks[o['tableRow']]),'official original nonspoken option table row')
                same(o['textRecord'],hash_strings(texts[option['hash']]),'official original nonspoken option TextMap row')
    return {'deepNativeClipObjects':objects,'deepInstalledBlocks':blocks,'deepMetadataFragments':len(decoded),
            'metadataOriginalUnavailable':len(contexts['missingExactArchiveSources']),'deepOfficialRows':official_rows}


def mutations(data, check, has_audit):
    accepted=[]; tested=[]
    def attempt(name, mutate):
        changed=deepcopy(data);mutate(changed)
        try:check(changed)
        except (AssertionError,ValueError,KeyError,IndexError,StopIteration):tested.append(name)
        else:accepted.append(name)
    first=lambda d:next(iter_scenes(d))[1]
    row=lambda d:first(d)['rows'][0]
    condition=lambda d:next(s for _,s in iter_scenes(d) if s['triggerContext']['conditions'])
    option=lambda d:next(s for _,s in iter_scenes(d) if s['optionReferences'])
    attempt('raw text corruption',lambda d:row(d).__setitem__('raw','altered'))
    attempt('voice mismatch',lambda d:row(d).__setitem__('voice',row(d)['voice']+1))
    if has_audit:
        attempt('native pathID swap',lambda d:row(d)['timelineClip'].__setitem__('pathID','123'))
        attempt('object SHA substitution',lambda d:row(d)['timelineClip'].__setitem__('objectSha256','0'*64))
    attempt('span outside native object',lambda d:row(d)['timelineClip'].__setitem__('talkIDSpan',[0,999999]))
    if has_audit:attempt('native start time substitution',lambda d:row(d)['timelineClip'].__setitem__('start',row(d)['timelineClip']['start']+.125))
    attempt('reading order reversal',lambda d:first(d)['rows'].reverse())
    attempt('owner target swap',lambda d:first(d)['ownership'][0].__setitem__('canonicalMissionId',9999999))
    attempt('preserved file SHA mismatch',lambda d:row(d)['preservedSource'].__setitem__('sha256','0'*64))
    attempt('official table TalkID swap',lambda d:row(d)['officialSource']['tableRecord'].__setitem__('TalkSentenceID',1))
    if has_audit:attempt('condition branch reversal',lambda d:condition(d)['triggerContext']['conditions'][0].__setitem__('branch','FailedTaskList' if condition(d)['triggerContext']['conditions'][0]['branch']=='SuccessTaskList' else 'SuccessTaskList'))
    attempt('option promoted to speech',lambda d:option(d)['optionReferences'][0].__setitem__('role','SPOKEN'))
    attempt('option raw text corruption',lambda d:option(d)['optionReferences'][0].__setitem__('raw','altered'))
    attempt('public private path leakage',lambda d:d['evidence'].__setitem__('privatePath','D:/game/.codex-work/private.json'))
    def drop_repeat(d):
        scene=next(s for _,s in iter_scenes(d) if any(r['talk_id']==154010409 for r in s['rows']))
        scene['rows']=[r for r in scene['rows'] if r['talk_id']!=154010409]
    attempt('real duplicate clip deduplicated',drop_repeat)
    require(not accepted,'Accepted meaningful artifact mutations: '+','.join(accepted))
    return tested


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--data',type=Path)
    p.add_argument('--dist',type=Path)
    p.add_argument('--audit',type=Path);p.add_argument('--joins',type=Path);p.add_argument('--contexts',type=Path)
    p.add_argument('--deep-replay',action='store_true')
    p.add_argument('--official-root',type=Path);p.add_argument('--skill',type=Path)
    p.add_argument('--skip-mutations',action='store_true')
    args=p.parse_args();site=args.site.resolve()
    sys.path.insert(0,str(site/'tools'))
    from verify_official_mission_talks import row_check
    from verify_official_universe_texts import safe
    data_path=args.data or site/'data/timeline-mission-dialogue.json';data=read(data_path)
    supplied=[args.audit,args.joins,args.contexts]
    require(not any(supplied) or all(supplied),'Audit trio must be supplied together')
    audit,joins,contexts=[read(q) if q else None for q in supplied]
    if audit is not None:
        same(data['evidence']['auditSha256'],sha(args.audit),'audit receipt SHA')
        same(data['evidence']['joinSha256'],sha(args.joins),'join receipt SHA')
        same(data['evidence']['contextsSha256'],sha(args.contexts),'context receipt SHA')
        same(audit['koreanJoinOutput']['sha256'],sha(args.joins),'audit join binding')
        same(contexts['inputs'][0]['sha256'],sha(args.audit),'context audit binding')
        same(contexts['inputs'][1]['sha256'],sha(args.joins),'context join binding')
    check=lambda value:artifact_check(value,site,row_check,safe,audit,joins,contexts)
    counts=check(data)
    mutation_names=mutations(data,check,audit is not None) if not args.skip_mutations else []
    html_scenes=html_mutations=0
    if args.dist:
        html_scenes,trees=html_check(data,args.dist)
        mission,scene=next(iter_scenes(data));tree=deepcopy(trees[mission])
        target=next(n for n in tree.root.descendants() if n.attrs.get('id')==scene['anchor']+'-row-1')
        target.children=['altered original']
        try:html_scene_check(tree,scene)
        except ValueError:html_mutations+=1
        else:raise ValueError('Accepted HTML original-text corruption')
        tree=deepcopy(trees[mission]);target=next(n for n in tree.root.descendants() if n.attrs.get('id')==scene['anchor'])
        target.attrs['id']='wrong-anchor'
        try:html_scene_check(tree,scene)
        except ValueError:html_mutations+=1
        else:raise ValueError('Accepted HTML scene anchor corruption')
    deep={}
    if args.deep_replay:
        require(audit is not None,'Deep replay requires audit trio')
        deep=deep_check(audit,contexts,args.official_root,args.skill,data)
    print(json.dumps({'status':'PASS','scope':'typed-timeline-artifact-and-optional-built-reader',**counts,
                      'auditCompared':audit is not None,'artifactMutationRejections':len(mutation_names),
                      'mutationCases':mutation_names,'builtTimelineScenes':html_scenes,
                      'htmlMutationRejections':html_mutations,'browserReturn':'UNVERIFIED',**deep},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except (AssertionError,ValueError,KeyError,IndexError,StopIteration) as error:
        print(json.dumps({'status':'FAIL','error':type(error).__name__+': '+str(error)},ensure_ascii=False));raise SystemExit(1)
