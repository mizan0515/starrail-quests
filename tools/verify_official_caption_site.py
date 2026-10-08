"""Read-only source-to-built-HTML checks for every official video caption.

The binary/source audit is separate. This checker compares the preserved sidecar
with actual DOM text, primary reader placement, timing, proofs and conditions.
Mutations are in memory; no source, generated data or HTML file is modified.
"""
import argparse
import copy
import json
import math
import re
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

sys.dont_write_bytecode = True
from verify_mission_readers import MissionPage, ReadingTemplatePage, VOID

ROOT = Path(__file__).resolve().parents[1]


def require(value, message):
    if not value:
        raise AssertionError(message)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Node:
    def __init__(self, tag, attrs=None, parent=None, start=0, opening_end=0):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.parent = parent
        self.children = []
        self.start, self.opening_end = start, opening_end
        self.closing_start = self.closing_end = opening_end

    def classes(self):
        return set(self.attrs.get('class', '').split())

    def elements(self, predicate=lambda node: True):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if predicate(child):
                    result.append(child)
                result.extend(child.elements(predicate))
        return result

    def immediate(self, tag):
        return [child for child in self.children if isinstance(child, Node) and child.tag == tag]

    def text(self, breaks=True):
        if self.tag == 'br':
            return '\n' if breaks else ''
        return ''.join(child.text(breaks) if isinstance(child, Node) else child for child in self.children)

    def inside(self, predicate):
        parent = self.parent
        while parent is not None:
            if predicate(parent):
                return True
            parent = parent.parent
        return False


class Dom(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.content = content
        self.lines = [0]
        self.lines.extend(match.end() for match in re.finditer('\n', content))
        self.root = Node('document')
        self.stack = [self.root]
        self.feed(content)
        self.close()

    def absolute_position(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        start = self.absolute_position()
        node = Node(tag, attrs, self.stack[-1], start, start + len(self.get_starttag_text()))
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            node = self.stack.pop()
            node.closing_start = node.closing_end = node.opening_end

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                node = self.stack[index]
                node.closing_start = self.absolute_position()
                node.closing_end = self.content.index('>', node.closing_start) + 1
                del self.stack[index:]
                return

    def handle_data(self, value):
        self.stack[-1].children.append(value)


def one(nodes, description):
    require(len(nodes) == 1, f'{description}: expected one element, found {len(nodes)}')
    return nodes[0]


def by_attr(node, name, value=None):
    return node.elements(lambda child: name in child.attrs and (value is None or child.attrs[name] == str(value)))


def direct_pairs(dl):
    children = [child for child in dl.children if isinstance(child, Node)]
    require(len(children) % 2 == 0, 'proof definition list has an odd number of children')
    result = []
    for index in range(0, len(children), 2):
        dt, dd = children[index:index + 2]
        require((dt.tag, dd.tag) == ('dt', 'dd'), 'proof definition list must alternate dt/dd')
        result.append((dt.text().strip(), dd.text()))
    return result


def indexes(nodes, attribute, count, description):
    actual = Counter(node.attrs.get(attribute) for node in nodes)
    require(actual == Counter(str(index) for index in range(count)), f'{description}: index coverage differs: {actual}')
    return {int(node.attrs[attribute]): node for node in nodes}


def js_number(value):
    """Source timing is finite, nonnegative binary32; match JS numeric display."""
    number = float(value)
    require(math.isfinite(number) and number >= 0, 'invalid source caption time')
    return str(int(number)) if number.is_integer() else repr(number)


def timestamp(value):
    # Positive JS Math.round uses half-up, whereas Python round uses half-even.
    total = math.floor(float(value) * 1000 + 0.5)
    minutes, rest = divmod(total, 60000)
    seconds, milliseconds = divmod(rest, 1000)
    return f'{minutes:02d}:{seconds:02d}.{milliseconds:03d}'


def condition_label(condition):
    predicate = condition.get('predicate')
    branch = '충족' if condition.get('branch') == 'SuccessTaskList' else '미충족'
    if predicate and predicate.get('$type') == 'RPG.GameCore.ByCurrentAudioLanguage':
        return f"음성 언어 {predicate['AudioLanguage']} 조건 · {branch} 경로"
    return f'파일의 조건 · {branch} 경로' if predicate else '파일에 기록된 이벤트 호출'


def source_url(evidence, path):
    return f"https://github.com/{evidence['metadataRepository']}/blob/{evidence['metadataCommit']}/{path}"


def canonical_scenes(source, aliases, documents):
    """Alias folding requires preserved explicit source-owner membership."""
    grouped, anchors = defaultdict(list), set()
    for owner, scenes in source['missions'].items():
        target = aliases.get(owner, owner)
        require(target in documents, f'{owner}: canonical document missing: {target}')
        document = documents[target]
        require(document['id'] == target, f'{owner}: canonical document ID mismatch')
        require(owner in document.get('missionParts', [target]), f'{owner}: missing explicit missionParts membership in {target}')
        for scene in scenes:
            require('quest-' + str(scene['ownership']['missionId']) == owner, f'{owner}: source ownership differs')
            require(scene['anchor'] not in anchors, f"duplicate source caption anchor: {scene['anchor']}")
            require(scene['rows'], f'{owner}: source caption scene has no rows')
            anchors.add(scene['anchor'])
            grouped[target].append(scene)
    require(source['counts']['missions'] == len(source['missions']), 'source mission count differs')
    require(source['counts']['scenes'] == sum(map(len, grouped.values())), 'source scene count differs')
    require(source['counts']['rows'] == sum(len(scene['rows']) for scenes in grouped.values() for scene in scenes), 'source row count differs')
    return dict(grouped)


def check_page(content, scenes, evidence, mission_id):
    """Compare all expected caption scenes with actual HTML; raise on any gap."""
    dom = Dom(content)
    template = ReadingTemplatePage()
    template.feed(content)
    require(not template.finish(), f'{mission_id}: common reading template errors: {template.errors}')
    mission = MissionPage()
    mission.feed(content)
    expected_anchors = Counter(scene['anchor'] for scene in scenes)
    proofs = by_attr(dom.root, 'data-official-caption-proof')
    require(Counter(proof.attrs['data-official-caption-proof'] for proof in proofs) == expected_anchors,
            f'{mission_id}: caption proof scene coverage differs')
    caption_rows = dom.root.elements(lambda node: node.attrs.get('data-passage') == 'caption')
    count = sum(len(scene['rows']) for scene in scenes)
    require(len(caption_rows) == count, f'{mission_id}: actual caption row count differs')
    reader = one(by_attr(dom.root, 'data-mission-reader'), f'{mission_id} primary mission reader')
    reader_count = one(reader.elements(lambda node: 'mission-reader-count' in node.classes()), 'caption count label')
    actual_count = re.findall(r'영상 자막\s*([\d,]+)행', reader_count.text())
    require(actual_count == [f'{count:,}'], f'{mission_id}: reader caption count label differs')
    option = one(reader.elements(lambda node: node.tag == 'option' and node.attrs.get('value') == 'caption'), 'caption filter')
    require(option.text() == '영상 자막' and option.parent.attrs.get('name') == 'passage', 'caption filter identity differs')
    unknown = one(reader.elements(lambda node: node.tag == 'option' and node.attrs.get('value') == '화자 미지정'), 'unspecified speaker filter')
    require(unknown.text() == '화자 미지정' and unknown.parent.attrs.get('name') == 'speaker', 'speaker filter identity differs')
    for scene in scenes:
        anchor = scene['anchor']
        section = one(dom.root.elements(lambda node: node.tag == 'section' and node.attrs.get('id') == anchor), f'{mission_id}/{anchor} section')
        parsed_section = one([item for item in mission.sections if item['id'] == anchor], 'independent primary scene placement')
        require(parsed_section['insideReader'] and parsed_section['isPrimary'] and not parsed_section['isReference'], f'{anchor}: caption scene is outside primary reader')
        proof = one(by_attr(section, 'data-official-caption-proof', anchor), f'{anchor} source proof')
        require(proof.tag == 'details' and proof.attrs.get('data-reading-template') == 'disclosure' and 'rw-disclosure' in proof.classes(), f'{anchor}: source disclosure template missing')
        require(one(proof.immediate('summary'), 'caption proof summary').text() == '영상 자막의 원문과 임무 연결 근거', 'caption proof summary differs')
        context = one(section.elements(lambda node: 'caption-context' in node.classes()), 'official source version label')
        version = evidence['clientVersion'].removeprefix('OSPRODWin')
        require(context.text().split('\n')[0].strip() == f'게임 파일의 영상 자막 · {version}', f'{anchor}: official Korean source version differs')
        first = scene['rows'][0]
        caption, textmap = first['officialCaptionSource'], first['officialTextMapSource']
        caption_kind = '조건 분기에 지정된 자막' if scene['captionReference']['kind'] == 'EXPLICIT_OVERRIDE_CAPTION_PATH' else '영상 표에 지정된 자막'
        expected_pairs = [
            ('영상과 자막의 연결', f"영상 {scene['videoId']} · {caption_kind}\n{scene['captionPath']} ↗\n{scene['captionReference']['pointer']}"),
            ('자막 원본 위치', f"{caption['packFile']}\n엔트리 {caption['entryKey']} · 팩 오프셋 {caption['entryOffset']} · 길이 {caption['entryLength']}\nSHA-256 · {caption['packSha256']}"),
            ('한국어 문자열 원본 위치', f"{textmap['packFile']}\n엔트리 {textmap['entryKey']} · 팩 오프셋 {textmap['entryOffset']}\nSHA-256 · {textmap['packSha256']}"),
            ('소유 관계와 재생 조건의 자료', f"고정 버전의 구조 자료 · {evidence['metadataCommit']}\n{scene['source']} ↗\nSHA-256 · {scene['sourceSha256']}"),
        ]
        header = one(proof.immediate('dl'), 'caption scene proof header')
        require(direct_pairs(header) == expected_pairs, f'{anchor}: scene source/identity proof differs')
        links = header.elements(lambda node: node.tag == 'a')
        require([(node.attrs.get('href'), node.text()) for node in links] == [
            (source_url(evidence, scene['captionPath']), scene['captionPath'] + ' ↗'),
            (scene['sourceUrl'], scene['source'] + ' ↗')], f'{anchor}: source proof links differ')
        # The structural metadata version is visible separately from official KR.
        ownership = [scene['ownership']['ownershipSeed'], *scene['ownership']['chain']]
        owner_list = one([node for node in proof.immediate('ol') if 'caption-source-rows' not in node.classes()], 'explicit owner chain')
        owner_nodes = owner_list.immediate('li')
        require(len(owner_nodes) == len(ownership), f'{anchor}: owner chain edge coverage differs')
        labels = {'EXPLICIT_RUNTIME_OWNERMAINMISSIONID': '실행 그룹의 임무 소유 참조', 'EXPLICIT_MAIN_MISSION_ID': '임무 소속의 명시 참조', 'EXPLICIT_JSON_PATH': 'JSON 파일의 명시 경로', 'EXPLICIT_PERFORMANCE_LOOKUP': '연출 식별자와 파일 경로'}
        for node, edge in zip(owner_nodes, ownership):
            expected = labels.get(edge['kind'], edge['kind']) + ' · ' + edge['source'] + ' ↗'
            if edge.get('pointer'):
                expected += ' · ' + edge['pointer']
            if edge.get('missionId'):
                expected += ' · 임무 ' + str(edge['missionId'])
            if edge.get('event'):
                expected += ' · ' + edge['event']
            if edge.get('performanceId'):
                expected += ' · 연출 ' + str(edge['performanceId'])
            if edge.get('missionJsonPathPointer'):
                expected += ' · 임무 경로 ' + edge['missionJsonPathPointer'] + ' · ' + edge['missionJsonPath']
            # Only UI edge labels allow insignificant template whitespace.
            require(re.sub(r'\s+', ' ', node.text()).strip() == expected, f'{anchor}: explicit owner edge differs')
            link = one(node.elements(lambda item: item.tag == 'a'), 'owner source link')
            require(link.attrs.get('href') == source_url(evidence, edge['source']), f'{anchor}: owner source URL differs')
        visible_conditions = indexes(by_attr(section, 'data-caption-condition'), 'data-caption-condition', len(scene['conditions']), f'{anchor} visible conditions')
        condition_proofs = indexes(by_attr(proof, 'data-caption-condition-proof'), 'data-caption-condition-proof', len(scene['conditions']), f'{anchor} condition proofs')
        for index, condition in enumerate(scene['conditions']):
            require(visible_conditions[index].text().strip() == condition_label(condition), f'{anchor}: visible playback condition differs')
            node = condition_proofs[index]
            condition_pre = one(node.elements(lambda item: item.tag == 'pre'), 'exact playback predicate/event')
            require(json.loads(condition_pre.text()) == (condition.get('predicate') or condition['event']), f'{anchor}: condition predicate/event differs')
            prefix = ''.join(child.text() if isinstance(child, Node) else child for child in node.children if child is not condition_pre).strip()
            expected = f"{condition_label(condition)} · {condition['source']} ↗ · {condition['branchPointer']}"
            require(prefix == expected, f'{anchor}: condition source/branch pointer differs')
            link = one(node.elements(lambda item: item.tag == 'a'), 'condition source URL')
            require(link.attrs.get('href') == source_url(evidence, condition['source']), f'{anchor}: condition source URL differs')
        row_proofs = indexes(by_attr(proof, 'data-caption-row-proof'), 'data-caption-row-proof', len(scene['rows']), f'{anchor} per-row proofs')
        actual_rows = section.elements(lambda node: node.attrs.get('data-passage') == 'caption')
        require(len(actual_rows) == len(scene['rows']), f'{anchor}: scene caption row count differs')
        require(proof.start < actual_rows[0].start, f'{anchor}: source context must precede original rows')
        for index, (node, row) in enumerate(zip(actual_rows, scene['rows'])):
            row_id = f'{anchor}-row-{index + 1}'
            require(node.attrs.get('data-speaker') == '화자 미지정' and node.attrs.get('data-reading-template') == 'row' and {'rw-source-row', 'original-row', 'video-caption-row'} <= node.classes(), f'{row_id}: caption row or unspecified speaker template differs')
            body = one(node.elements(lambda item: item.tag == 'p' and 'original-body' in item.classes()), f'{row_id} original body')
            require(body.attrs.get('id') == row_id and body.text() == row['text'], f'{row_id}: actual DOM original text/anchor differs')
            require(mission.ids[row_id] == 1, f'{row_id}: original body ID is not unique')
            parsed_row = one([item for item in mission.rows if any(part['id'] == row_id for part in item['bodies'])], 'independent primary row placement')
            require(parsed_row['insideReader'] and parsed_row['isPrimary'] and not parsed_row['isReference'], f'{row_id}: row moved outside primary reader')
            require(one(node.elements(lambda item: 'rw-source-speaker' in item.classes()), 'caption row label').text() == '영상 자막', f'{row_id}: caption label differs')
            time = one(by_attr(node, 'data-caption-time', index), 'caption playback timestamp')
            require(time.text() == f"{timestamp(row['startTime'])}–{timestamp(row['endTime'])}", f'{row_id}: millisecond playback timestamp differs')
            expected_aria = f"영상 안의 재생 시각 {timestamp(row['startTime'])}부터 {timestamp(row['endTime'])}까지"
            require(time.attrs.get('aria-label') == expected_aria, f'{row_id}: accessible playback timestamp differs')
            c, t = row['officialCaptionSource'], row['officialTextMapSource']
            expected_row_pairs = [
                ('한국어 문자열과 재생 시각', f"문자열 {row['hash']} · {js_number(row['startTime'])}–{js_number(row['endTime'])}초\n자막 엔트리 내부 {c['rowOffset']}–{c['rowEnd']}\n한국어 엔트리 내부 {t['rowOffset']}–{t['rowEnd']}"),
                ('게임 파일의 한국어 문자열', row['raw']),
            ]
            row_dl = one(row_proofs[index].immediate('dl'), f'{row_id} source row definition list')
            require(direct_pairs(row_dl) == expected_row_pairs, f'{row_id}: hash, exact timing, spans or raw proof differs')
            require(one(row_dl.elements(lambda item: item.tag == 'pre'), 'raw Korean source string').text() == row['raw'], f'{row_id}: raw Korean source string differs')
    return dom


def replace_inside(content, node, replacement):
    require(node.closing_start >= node.opening_end, 'invalid mutation node span')
    return content[:node.opening_end] + replacement + content[node.closing_start:]


def rename_attribute(content, node, attribute):
    opening = content[node.start:node.opening_end]
    require(attribute + '=' in opening, 'mutation target attribute missing')
    return content[:node.start] + opening.replace(attribute + '=', 'data-rejected-mutation=', 1) + content[node.opening_end:]


def mutation_checks(content, dom, scenes, evidence, mission_id):
    """Every affected page must reject the same reusable corruption classes."""
    scene = scenes[0]
    section = one(dom.root.elements(lambda node: node.attrs.get('id') == scene['anchor']), 'mutation scene')
    proof = one(by_attr(section, 'data-official-caption-proof'), 'mutation proof')
    row = one(section.elements(lambda node: node.tag == 'p' and node.attrs.get('id') == scene['anchor'] + '-row-1'), 'mutation original body')
    time = one(by_attr(section, 'data-caption-time', 0), 'mutation playback time')
    row_proof = one(by_attr(proof, 'data-caption-row-proof', 0), 'mutation row proof')
    raw = one(row_proof.elements(lambda node: node.tag == 'pre'), 'mutation raw string')
    source_dd = one(row_proof.immediate('dl'), 'mutation row definition list').immediate('dd')[0]
    hash_inner = content[source_dd.opening_end:source_dd.closing_start]
    require(scene['rows'][0]['hash'] in hash_inner, 'mutation source hash is absent')
    wrong_hash_inner = hash_inner.replace(scene['rows'][0]['hash'], '1', 1)
    context = one(section.elements(lambda node: 'caption-context' in node.classes()), 'mutation source version')
    changes = {
        'missing-scene-proof': rename_attribute(content, proof, 'data-official-caption-proof'),
        'wrong-original-text': replace_inside(content, row, '__QA_WRONG_ORIGINAL__'),
        'wrong-visible-time': replace_inside(content, time, '99:59.999–99:59.999'),
        'wrong-hash': replace_inside(content, source_dd, wrong_hash_inner),
        'wrong-raw-source': replace_inside(content, raw, '__QA_WRONG_RAW__'),
        'wrong-official-version': replace_inside(content, context, '게임 파일의 영상 자막 · __QA_WRONG_VERSION__'),
    }
    conditional = dom.root.elements(lambda node: 'data-caption-condition' in node.attrs)
    if conditional:
        changes['missing-visible-condition'] = rename_attribute(content, conditional[0], 'data-caption-condition')
        condition_proof = one(by_attr(dom.root, 'data-caption-condition-proof', 0)[:1], 'mutation condition proof')
        changes['missing-condition-proof'] = rename_attribute(content, condition_proof, 'data-caption-condition-proof')
    for label, changed in changes.items():
        try:
            check_page(changed, scenes, evidence, mission_id)
        except AssertionError:
            pass
        else:
            raise AssertionError(f'{mission_id}: accepted HTML mutation: {label}')
    return len(changes)


def mapping_mutations(source, aliases, documents):
    merged = next((owner for owner in source['missions'] if aliases.get(owner, owner) != owner), None)
    if merged is None:
        return 0
    target = aliases[merged]
    bad_docs = copy.deepcopy(documents)
    bad_docs[target]['missionParts'].remove(merged)
    bad_aliases = dict(aliases)
    bad_aliases[merged] = next(key for key in documents if key != target and merged not in documents[key].get('missionParts', [key]))
    cases = [(aliases, bad_docs), (bad_aliases, documents)]
    for changed_aliases, changed_docs in cases:
        try:
            canonical_scenes(source, changed_aliases, changed_docs)
        except AssertionError:
            pass
        else:
            raise AssertionError('accepted unsafe canonical mission owner mutation')
    return len(cases)


def main(dist):
    source = read_json(ROOT / 'data/official-video-captions.json')
    require(source['schema'] == 'starrail-official-video-captions.v1', 'caption sidecar schema differs')
    aliases = read_json(ROOT / 'data/aliases.json')
    targets = {aliases.get(owner, owner) for owner in source['missions']}
    documents = {target: read_json(ROOT / 'data/documents' / (target + '.json')) for target in targets}
    grouped = canonical_scenes(source, aliases, documents)
    catalogue = read_json(dist / 'reading-catalog.json')
    built_quests = {item['id']: item for item in catalogue if item.get('category') == '퀘스트'}
    expected_anchors = Counter(scene['anchor'] for scenes in grouped.values() for scene in scenes)
    found_anchors, all_caption_rows = Counter(), 0
    for path in sorted((dist / '문서').glob('quest-*.html')):
        content = path.read_text(encoding='utf-8')
        found_anchors.update(re.findall(r'\bdata-official-caption-proof="([^"]+)"', content))
        all_caption_rows += len(re.findall(r'\bdata-passage="caption"', content))
    require(found_anchors == expected_anchors, 'whole-site caption proof coverage or uniqueness differs')
    require(all_caption_rows == source['counts']['rows'], 'whole-site caption row coverage differs')
    mutations = mapping_mutations(source, aliases, documents)
    for mission_id, scenes in sorted(grouped.items()):
        path = dist / '문서' / (mission_id + '.html')
        require(path.exists(), f'{mission_id}: built canonical mission page missing')
        content = path.read_text(encoding='utf-8')
        dom = check_page(content, scenes, source['evidence'], mission_id)
        count = sum(len(scene['rows']) for scene in scenes)
        require(mission_id in built_quests and built_quests[mission_id].get('captionCount') == count, f'{mission_id}: catalogue caption count differs')
        mutations += mutation_checks(content, dom, scenes, source['evidence'], mission_id)
    print(json.dumps({'status': 'PASS', 'sourceMissionIds': len(source['missions']), 'canonicalMissionPages': len(grouped),
                      'scenes': source['counts']['scenes'], 'rows': source['counts']['rows'],
                      'htmlAndOwnershipMutationRejections': mutations, 'dist': str(dist),
                      'scope': 'Static compiled DOM and sidecar comparison; browser layout/interaction is separately verified.'}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    try:
        main(args.dist.resolve())
    except (AssertionError, KeyError, ValueError) as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)}, ensure_ascii=False))
        raise SystemExit(1)
