"""Compare universe source pages with preserved records and their cited originals.

This is generated-HTML QA. It does not establish browser layout or runtime filtering.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

from verify_site import Page


VOID = set("area base br col embed hr img input link meta param source track wbr".split())


class SourcePage(Page):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.bodies = {}
        self.scenes = {}
        self.record_links = []
        self.message_links = []
        self.message_paragraphs = []
        self.panels = {}
        self.clusters = []
        self.h1 = []
        self.paragraphs = []
        self.controls = []
        self.pending_choices = []
        self.choice_links = []
        self.universe_node_contexts = []
        self.nested_p = 0

    @staticmethod
    def classes(attrs):
        return set(attrs.get('class', '').split())

    def ancestor(self, predicate):
        return next((n for n in reversed(self.stack) if predicate(n)), None)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        super().handle_starttag(tag, attrs)
        n = {'tag': tag, 'attrs': a, 'text': '', 'children': []}
        if tag == 'p' and self.ancestor(lambda x: x['tag'] == 'p'):
            self.nested_p += 1
        if self.stack:
            self.stack[-1]['children'].append(n)
        if 'data-universe-node-record' in a:
            n['heading'] = next((child for child in reversed(self.stack[-1]['children'][:-1]) if child['tag'] == 'h3'), None) if self.stack else None
            self.universe_node_contexts.append(n)
        if tag == 'section' and 'source-section' in self.classes(a):
            self.scenes[a.get('id')] = a
        if tag == 'p' and 'original-body' in self.classes(a):
            row = self.ancestor(lambda x: 'original-row' in self.classes(x['attrs']))
            scene = self.ancestor(lambda x: 'source-section' in self.classes(x['attrs']))
            n['row'] = row['attrs'] if row else {}
            n['scene'] = scene['attrs'].get('id') if scene else None
            self.bodies[a.get('id')] = n
        if tag == 'p' and 'mission-message-source' in self.classes(a):
            self.message_paragraphs.append(n)
        if 'data-choice-text-pending' in a:
            self.pending_choices.append(n)
        if tag == 'a':
            if 'data-choice-target' in a:
                self.choice_links.append((a, self.ancestor(lambda x: 'original-row' in self.classes(x['attrs']))))
            shelf = self.ancestor(lambda x: x['attrs'].get('id') == 'source-records')
            if shelf and 'data-source-record' in a:
                self.record_links.append(a)
            message = self.ancestor(lambda x: 'mission-message-source' in self.classes(x['attrs']))
            if message:
                scene = self.ancestor(lambda x: 'source-section' in self.classes(x['attrs']))
                self.message_links.append((a, scene['attrs'].get('id') if scene else None))
            if 'data-cluster-evidence' in a:
                panel = self.ancestor(lambda x: 'data-cluster-panel' in x['attrs'])
                if panel:
                    self.panels[panel['attrs']['data-cluster-panel']]['links'].append(a)
        if 'data-universe-cluster' in a:
            self.clusters.append(a['data-universe-cluster'])
        if 'data-cluster-panel' in a:
            self.panels[a['data-cluster-panel']] = {'links': [], 'quotes': []}
        if tag == 'blockquote' and 'rw-quotation' in self.classes(a):
            panel = self.ancestor(lambda x: 'data-cluster-panel' in x['attrs'])
            if panel:
                self.panels[panel['attrs']['data-cluster-panel']]['quotes'].append(n)
        if self.ancestor(lambda x: x['attrs'].get('id') == 'source-records') and any(k in a for k in ('data-source-query', 'data-source-more', 'data-source-count', 'data-source-empty')):
            self.controls.append((tag, a))
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        index = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i]['tag'] == tag), None)
        if index is None:
            return
        n = self.stack[index]
        if tag == 'h1':
            self.h1.append(n['text'])
        if tag == 'p':
            self.paragraphs.append(n['text'])
        del self.stack[index:]

    def handle_data(self, data):
        super().handle_data(data)
        for n in self.stack:
            n['text'] += data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    dist = args.dist or repo / 'dist'
    records_data = json.loads((repo / 'data/universe-source-records.json').read_text(encoding='utf-8'))
    discovery = json.loads((repo / 'data/universe-discovery.json').read_text(encoding='utf-8'))
    clusters_data = json.loads((repo / 'data/universe-reading-clusters.json').read_text(encoding='utf-8'))
    catalog = json.loads((repo / 'data/catalog.json').read_text(encoding='utf-8'))
    coverage = json.loads((repo / 'data/mission-dialogue-supplements.json').read_text(encoding='utf-8'))['coverage']
    errors = []
    counts = Counter()
    pages = {}

    def check(condition, message):
        if not condition:
            errors.append(message)

    def page(relative):
        relative = str(relative)
        if relative not in pages:
            path = dist / relative
            if not path.is_file():
                errors.append(f'Missing HTML: {relative}')
                pages[relative] = None
            else:
                p = SourcePage()
                p.feed(path.read_text(encoding='utf-8'))
                p.close()
                check(not p.duplicates, f'{relative}: duplicate IDs {p.duplicates[:5]}')
                check(not p.nested_p, f'{relative}: nested paragraph markup ({p.nested_p})')
                pages[relative] = p
        return pages[relative]

    def local_link(url):
        parsed = urlsplit(url or '')
        if parsed.scheme or parsed.netloc or not parsed.path.startswith('/starrail-quests/'):
            return None
        relative = unquote(parsed.path.removeprefix('/starrail-quests/'))
        if '..' in Path(relative).parts or '\\' in relative:
            return None
        return relative, unquote(parsed.fragment)

    def source_link(a, label, variant='cta'):
        check('rw-source-link' in SourcePage.classes(a), f'{label}: source link class missing')
        check(a.get('data-reading-template') == 'source-link', f'{label}: source link boundary missing')
        check(a.get('data-source-link-variant') == variant, f'{label}: source link variant differs')
        check('data-reading-link' in a, f'{label}: reading return marker missing')
        check(local_link(a.get('href')) is not None, f'{label}: source link is not a safe local reading URL')

    ids = [r['id'] for m in records_data['modes'] for r in m['records']]
    pending_counts = Counter(field['recordId'] for field in records_data['unresolvedScriptTextFields'])
    check(set(pending_counts) <= set(ids), 'Input: pending option text refers to an unknown record')
    check(len(ids) == len(set(ids)), 'Input: repeated universe record IDs')
    actual_ids = {p.stem for p in (dist / '우주/기록').glob('*.html')}
    check(actual_ids == set(ids), f'Record page membership differs: missing={sorted(set(ids)-actual_ids)[:10]}, extra={sorted(actual_ids-set(ids))[:10]}')
    for mode in records_data['modes']:
        mode_page = page(f"우주/{mode['id']}.html")
        if mode_page:
            source_directory = next(item for item in discovery['items'] if item['modeId'] == mode['id'])
            edges = source_directory['edges']
            expected_nodes = Counter(edge['to'] for edge in edges)
            expected_nodes.update(set(edge['from'] for edge in edges))
            contexts = mode_page.universe_node_contexts
            check(Counter(n['attrs']['data-universe-node-record'] for n in contexts) == expected_nodes, f"{mode['id']}: branch passage membership differs")
            by_id = {record['id']: record for record in mode['records']}
            for node in contexts:
                attrs = node['attrs']
                record_id = attrs['data-universe-node-record']
                record = by_id.get(record_id)
                label = f"{mode['id']}/{record_id}/branch-passage"
                if not record:
                    check(False, f'{label}: unknown original record')
                    continue
                candidates = [(scene, index, row) for scene in record['scenes'] for index, row in enumerate(scene['rows'], 1) if row.get('text', '').strip()]
                check(bool(candidates), f'{label}: no original text')
                if not candidates:
                    continue
                scene, index, row = candidates[0]
                anchor = row.get('readerRowAnchor') or f"{scene['anchor']}-row-{index}"
                check(attrs.get('data-universe-quote-anchor') == anchor and attrs.get('data-universe-quote-hash') == row.get('hash', '') and attrs.get('data-universe-quote-speaker') == row.get('speaker', ''), f'{label}: source identity or speaker differs')
                quotes = [child for child in node['children'] if child['tag'] == 'blockquote']
                check(len(quotes) == 1 and quotes[0]['text'] == row['text'][:170], f'{label}: exact original prefix differs')
                attribution = [child for child in node['children'] if 'universe-node-attribution' in SourcePage.classes(child['attrs'])]
                title = next(item for item in source_directory['records'] if item['id'] == record_id)
                expected_attribution = ('원문 제목' if title['titleKind'] == 'original' else '식별용 제목') + ' · 원문 발췌' + (' · ' + row['speaker'] if row.get('speaker') else '')
                check(len(attribution) == 1 and attribution[0]['text'] == expected_attribution, f'{label}: title provenance or quotation attribution differs')
                continued = [child for child in node['children'] if 'universe-node-continuation' in SourcePage.classes(child['attrs'])]
                check(bool(continued) == (len(row['text']) > 170) and all(child['text'] == '…' for child in continued), f'{label}: truncation mark differs')
                links = [child for child in node['children'] if child['tag'] == 'a']
                heading = node.get('heading') or {'children': []}
                title_links = [child for child in heading['children'] if child['tag'] == 'a']
                check(len(links) == 1 and len(title_links) == 1, f'{label}: source/title link missing')
                if len(links) == 1 and len(title_links) == 1:
                    link, title_link = links[0]['attrs'], title_links[0]['attrs']
                    check(link.get('href') == f'/starrail-quests/우주/기록/{record_id}.html#{anchor}', f'{label}: quotation target differs')
                    check(title_link.get('href') == f'/starrail-quests/우주/기록/{record_id}.html', f'{label}: title target differs')
                    check(bool(title_link.get('id')) and link.get('id') == title_link.get('id') + '-quote' and 'data-reading-link' in link and 'data-reading-link' in title_link, f'{label}: stable reading return anchors missing')
                    target = page(f'우주/기록/{record_id}.html')
                    if target:
                        check(target.original.get(anchor) == row['text'], f'{label}: quotation does not reach the full original row')
                counts['branchPassages'] += 1
            check('source-records' in mode_page.ids, f"{mode['id']}: source-records anchor missing")
            check([a.get('data-source-record') for a in mode_page.record_links] == [r['id'] for r in mode['records']], f"{mode['id']}: record membership/order differs")
            for key, tag in (('data-source-query', 'input'), ('data-source-more', 'button'), ('data-source-count', 'p'), ('data-source-empty', 'p')):
                matches = [(t, a) for t, a in mode_page.controls if key in a]
                check(len(matches) == 1 and matches[0][0] == tag, f"{mode['id']}: {key} control missing or repeated")
            for i, (r, a) in enumerate(zip(mode['records'], mode_page.record_links)):
                label = f"{mode['id']}/{r['id']}"
                check(a.get('href') == f"/starrail-quests/우주/기록/{r['id']}.html", f'{label}: record URL differs')
                check('data-reading-link' in a, f'{label}: record return marker missing')
                check(a.get('id') == 'universe-source-' + r['id'], f'{label}: stable record return anchor missing')
                check(a.get('data-search') == ' '.join(row['text'] for s in r['scenes'] for row in s['rows']), f'{label}: searchable original text differs')
                check(('hidden' in a) == (i >= 12), f'{label}: initial record visibility differs')
                counts['modeLinks'] += 1
        for r in mode['records']:
            relative = f"우주/기록/{r['id']}.html"
            p = page(relative)
            if not p:
                continue
            counts['records'] += 1
            pending = pending_counts[r['id']]
            if pending:
                expected_notice = f'이 기록의 선택지 문구 {pending}개는 한국어 연결을 확인 중입니다. 현재 본문에는 확인된 대사를 수록했습니다.'
                check(len(p.pending_choices) == 1 and p.pending_choices[0]['tag'] == 'p' and p.pending_choices[0]['text'] == expected_notice, f'{relative}: pending choice count/status notice differs')
                counts['pendingChoiceRecords'] += 1
                counts['pendingChoiceFields'] += pending
            else:
                check(not p.pending_choices, f'{relative}: pending choice notice without unresolved input')
            check(p.h1 == [r['title']], f'{relative}: displayed title differs')
            neutral = r['titleStatus'] == 'NEUTRAL_RECORD_ID'
            check(any('표시 제목은 자료 종류와 식별자를 사용합니다.' in t for t in p.paragraphs) == neutral, f'{relative}: title provenance notice differs')
            if r['titleStatus'] == 'NEUTRAL_RECORD_ID':
                check(str(r['sourceRecordId']) in r['title'], f'{relative}: neutral title loses source record ID')
            expected = {}
            expected_choice_links = []
            check(set(p.scenes) == {s['anchor'] for s in r['scenes']}, f'{relative}: source scene membership differs')
            for s in r['scenes']:
                counts['scenes'] += 1
                a = p.scenes.get(s['anchor'], {})
                check({'rw-reader', 'not-content', 'source-section'} <= SourcePage.classes(a) and a.get('data-reading-template') == 'reader', f"{relative}/{s['anchor']}: reader boundary differs")
                talk_anchors = {str(row.get('talk_id')): f"{s['anchor']}-row-{j}" for j, row in enumerate(s['rows'], 1)}
                for i, row in enumerate(s['rows'], 1):
                    anchor = f"{s['anchor']}-row-{i}"
                    expected[anchor] = row['text']
                    body = p.bodies.get(anchor)
                    check(body is not None, f'{relative}/{anchor}: body missing')
                    if body:
                        check(body['scene'] == s['anchor'], f'{relative}/{anchor}: scene ownership differs')
                        check('rw-source-body' in SourcePage.classes(body['attrs']), f'{relative}/{anchor}: source body class missing')
                        check({'original-row', 'rw-source-row'} <= SourcePage.classes(body['row']) and body['row'].get('data-reading-template') == 'row', f'{relative}/{anchor}: row boundary differs')
                        missing = row.get('label') == '대사 누락' or not isinstance(row.get('text'), str) or not row['text'].strip() or (row['text'] == '한국어 본문 미수록' and row.get('hash') == '' and row.get('source', '').startswith('MessageItemConfig:') and row.get('source', '').endswith(('.MainText', '.OptionText')))
                        kind = 'gap' if missing else 'choice' if row.get('label') == '선택지' or row.get('displayKind') in ('choice', '선택지') else 'dialogue'
                        check(body['row'].get('data-reading-kind') == kind and body['row'].get('data-passage') == kind, f'{relative}/{anchor}: passage metadata differs')
                        check(body['row'].get('data-speaker') == (row.get('speaker') or '화자 미지정'), f'{relative}/{anchor}: speaker metadata differs')
                        check(all(n['tag'] == 'span' and 'original-paragraph' in SourcePage.classes(n['attrs']) for n in body['children']) and bool(body['children']), f'{relative}/{anchor}: paragraph wrappers differ')
                    counts['rows'] += 1
                    for target in row.get('branchTargets', []):
                        check(row.get('displayKind') in ('choice', '선택지'), f'{relative}/{anchor}: branch target on non-choice row')
                        target_anchor = talk_anchors.get(str(target['talkId']))
                        check(target_anchor is not None, f'{relative}/{anchor}: choice target has no original row')
                        expected_choice_links.append((anchor, str(target['talkId']), '#' + (target_anchor or '')))
            check(p.original == expected, f'{relative}: original text or row anchors differ')
            actual_choice_links = []
            for a, row_node in p.choice_links:
                origin_node = next((child for child in (row_node or {}).get('children', []) if child['tag'] == 'p' and 'original-body' in SourcePage.classes(child['attrs'])), None)
                origin_anchor = origin_node['attrs'].get('id') if origin_node else None
                actual_choice_links.append((origin_anchor, a.get('data-choice-target'), a.get('href')))
                check(a.get('data-reading-template') == 'source-link' and a.get('data-source-link-variant') == 'cta', f'{relative}/{origin_anchor}: choice link template differs')
            check(Counter(actual_choice_links) == Counter(expected_choice_links), f'{relative}: explicit choice target links differ')
            counts['choiceTargetLinks'] += len(actual_choice_links)

    for cluster in clusters_data['clusters']:
        relative = f"우주/{cluster['modeId']}.html"
        p = page(relative)
        if not p:
            continue
        counts['clusters'] += 1
        check(p.clusters.count(cluster['id']) == 1, f"{relative}: cluster {cluster['id']} boundary missing/repeated")
        expected_panels = {f"{cluster['id']}-{i}" for i in range(len(cluster['panels']))}
        actual_panels = {k for k in p.panels if k.startswith(cluster['id'] + '-')}
        check(actual_panels == expected_panels, f"{relative}/{cluster['id']}: panel membership differs")
        for i, panel in enumerate(cluster['panels']):
            label = f"{relative}/{cluster['id']}-{i}"
            actual = p.panels.get(f"{cluster['id']}-{i}", {'links': [], 'quotes': []})
            counts['panels'] += 1
            check(len(actual['links']) == len(panel['evidence']), f'{label}: citation link count differs')
            check([q['text'] for q in actual['quotes']] == [e['quote'] for e in panel['evidence']], f'{label}: visible quotations differ')
            for e, a in zip(panel['evidence'], actual['links']):
                document_path = repo / 'data/documents' / f"{e['docId']}.json"
                d = json.loads(document_path.read_text(encoding='utf-8'))
                section = next((s for s in d['sections'] if s['anchor'] == e['anchor']), None)
                rows = section['rows'] if section else []
                indexes = [j for j, row in enumerate(rows) if str(row.get('talk_id')) == str(e['talkId'])] if e.get('talkId') else [j for j, row in enumerate(rows) if row['text'] == e['quote']]
                check(len(indexes) == 1, f'{label}: citation has no unique canonical source row')
                if len(indexes) != 1:
                    continue
                index = indexes[0]
                check(rows[index]['text'] == e['quote'], f'{label}: citation differs from preserved original')
                anchor = f"{e['anchor']}-row-{index+1}"
                expected_href = f"/starrail-quests/문서/{e['docId']}.html#{anchor}"
                check(a.get('href') == expected_href, f'{label}: citation URL does not identify its actual row')
                source_link(a, label)
                target = page(f"문서/{e['docId']}.html")
                if target:
                    check(target.original.get(anchor) == e['quote'], f'{label}: citation target row missing or changed')
                counts['citations'] += 1

    quests = [c for c in catalog if c['id'].startswith('quest-')]
    for c in quests:
        relative = f"문서/{c['id']}.html"
        p = page(relative)
        if not p:
            continue
        counts['questPages'] += 1
        expected_message_links = {}
        for ref_id in dict.fromkeys(ref['id'] for ref in coverage.get(c['id'], {}).get('relatedDocuments', [])):
            d = json.loads((repo / 'data/documents' / (ref_id + '.json')).read_text(encoding='utf-8'))
            for section in d['sections']:
                if section['rows']:
                    scene = f"mission-message-{d['id']}-{section['anchor']}"
                    expected_message_links[scene] = '/starrail-quests/' + d['url']
        check(Counter(scene for _, scene in p.message_links) == Counter(expected_message_links.keys()), f'{relative}: linked message section membership differs')
        check(len(p.message_links) == len(p.message_paragraphs), f'{relative}: message source must contain exactly one link per paragraph')
        for n in p.message_paragraphs:
            check(sum(child['tag'] == 'a' for child in n['children']) == 1, f'{relative}: message source link wrapper differs')
        for a, scene in p.message_links:
            label = f'{relative}/{scene}/message-source'
            source_link(a, label)
            check(a.get('id') == f'{scene}-original-message', f'{label}: source CTA ID differs')
            check(a.get('href') == expected_message_links.get(scene), f'{label}: canonical message source URL differs')
            resolved = local_link(a.get('href'))
            if resolved:
                target = page(resolved[0])
                if target and resolved[1]:
                    check(resolved[1] in target.ids, f'{label}: message source anchor missing')
            counts['messageSourceLinks'] += 1
        # Quest HTML is large; retain citation targets only until their checks finish.
        pages.pop(relative, None)
    print(json.dumps({'status': 'FAIL' if errors else 'PASS', 'counts': dict(counts), 'errors': errors[:100], 'errorCount': len(errors), 'scope': 'Generated HTML source preservation and links; browser layout/runtime not assessed'}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
