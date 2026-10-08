"""Check generated CVA topics, curated catalogue and research source boundaries.

This is an HTML/content gate. Browser filtering, layout and focus require the
separate actual-use check; presence of a hidden-capable card is not that check.
"""
import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text('utf8'))


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.nodes, self.stack = [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        n = {'tag': tag, 'attrs': dict(attrs), 'text': '', 'parent': self.stack[-1] if self.stack else None}
        self.nodes.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]['tag'] == tag:
                del self.stack[i:]
                return

    def handle_data(self, text):
        if any(n['tag'] in ('script', 'style') for n in self.stack):
            return
        for n in self.stack:
            n['text'] += text

    def selected(self, attr, value=None):
        return [n for n in self.nodes if attr in n['attrs'] and
                (value is None or n['attrs'][attr] == value)]


def inside(n, parent):
    while n:
        if n is parent:
            return True
        n = n['parent']
    return False


def ancestor(n, predicate):
    while n:
        if predicate(n):
            return n
        n = n['parent']
    return None


def verify(dist):
    topics = read(SITE / 'editorial/topics.json')
    resolved = {t['id']: t for t in read(SITE / 'data/topics.json')}
    counts = Counter()
    for t in topics:
        page = Page((dist / '설정' / (t['id'] + '.html')).read_text('utf8'))
        boundary = page.selected('data-topic-relations', t['id'])
        require(len(boundary) == 1, 'Missing/duplicate topic relation boundary')
        boundary = boundary[0]
        for i, (relation, proof) in enumerate(zip(t['relations'], t['relationEvidence'])):
            details = page.selected('id', f"topic-{t['id']}-edge-relation-{i}")
            require(len(details) == 1 and inside(details[0], boundary), 'Missing/duplicate relation proof')
            detail = details[0]
            card = ancestor(detail, lambda n: 'data-cva-item-index' in n['attrs'])
            require(card is not None and all(v in card['text'] for v in relation[:3]),
                    'CVA relation lost actor/predicate/target')
            label = {'inference': '편집자의 연결', 'attributed': '발언·기록에 따른 관계',
                     'explicit': '원문에 명시된 관계'}[proof['statementType']]
            require(label in detail['text'] and (not proof['speaker'] or proof['speaker'] in detail['text']),
                    'Relation attribution differs')
            actual_quote_nodes = [n for n in page.nodes if n['tag'] == 'blockquote' and inside(n, detail)]
            actual_quotes = [n['text'] for n in actual_quote_nodes]
            require(actual_quotes == [e['quote'] for e in proof['evidence']], 'Visible relation original quotes differ')
            for evidence_index, e in enumerate(proof['evidence']):
                d = read(SITE / 'data/documents' / (e['id'] + '.json'))
                rows = next(s['rows'] for s in d['sections'] if s['anchor'] == e['anchor'])
                indexes = [j for j, r in enumerate(rows) if str(r.get('hash')) == str(e['hash']) and e['quote'] in r['text']]
                require(len(indexes) == 1, 'Relation quote has no unique original row')
                href = f"/starrail-quests/문서/{e['id']}.html#{e['anchor']}-row-{indexes[0]+1}"
                source = ancestor(actual_quote_nodes[evidence_index], lambda n: n['attrs'].get('data-topic-evidence') == e['id'])
                require(source is not None, 'Relation quote lost its own evidence boundary')
                links = [n for n in page.nodes if n['tag'] == 'a' and inside(n, source) and n['attrs'].get('href') == href]
                require(len(links) == 1 and links[0]['attrs'].get('data-reading-template') == 'source-link',
                        'Relation source CTA lost exact row/template')
                counts['relationQuotes'] += 1
            counts['relations'] += 1
        require(len(page.selected('data-cva')) >= len(t['sections']) + 2, 'Topic lacks real CVA sections/network/directory')
        for i, section in enumerate(t['sections']):
            nodes = page.selected('id', 'reading-' + str(i))
            require(len(nodes) == 1 and section['text'] in nodes[0]['text'] and section['title'] in nodes[0]['text'],
                    'Topic section prose/title/anchor changed')
            for e in resolved[t['id']]['sections'][i]['evidence']:
                require(any(n['tag'] == 'blockquote' and inside(n, nodes[0]) and n['text'] == e['quote']
                            for n in page.nodes), 'Section citation changed')
                counts['sectionQuotes'] += 1
        directories = [n for n in page.nodes if 'reading-list' in n['attrs'].get('class', '').split()]
        require(len(directories) == 1, 'Recommended reading boundary missing')
        for ref in resolved[t['id']]['reading']:
            href = f"/starrail-quests/문서/{ref['id']}.html"
            links = [n for n in page.nodes if n['tag'] == 'a' and inside(n, directories[0]) and n['attrs'].get('href') == href]
            require(len(links) == 1 and 'data-reading-link' in links[0]['attrs'] and ref['title'] in links[0]['text'],
                    'Recommended original title/body link differs')
            card = ancestor(links[0], lambda n: 'data-cva-item-index' in n['attrs'])
            require(card is not None and ref['why'] in card['text'], 'Recommended original reading reason differs')
            counts['recommendedOriginals'] += 1
        counts['topics'] += 1

    atlas = read(SITE / 'editorial/context-atlas.json')
    page = Page((dist / '설정집.html').read_text('utf8'))
    hubs = page.selected('data-atlas-hub')
    require(len(hubs) == 1, 'Curated catalogue boundary missing')
    entries = [n for n in page.selected('data-atlas-entry') if inside(n, hubs[0])]
    require(len(entries) == len(atlas['nodes']), 'Curated catalogue membership differs')
    for original in atlas['nodes']:
        search = ' '.join([original['name'], original['question'], *original['terms']])
        found = [n for n in entries if n['attrs'].get('data-search') == search]
        require(len(found) == 1 and original['name'] in found[0]['text'], 'Catalogue identity/search metadata differs')
        card = ancestor(found[0], lambda n: 'data-cva-item-index' in n['attrs'])
        require(card is not None and original['question'] in card['text'], 'Filter target has no actual CVA card')
        group = ancestor(card, lambda n: n['attrs'].get('data-axis-group') == original['axis'])
        require(group is not None, 'Catalogue card axis differs')
        require(found[0]['attrs'].get('href', '').endswith('/' + original['id'] + '.html'), 'Catalogue individual body link differs')
    counts['atlasEntries'] = len(entries)

    for c in read(SITE / 'data/universe-reading-clusters.json')['clusters']:
        page = Page((dist / '우주' / (c['modeId'] + '.html')).read_text('utf8'))
        for i, panel in enumerate(c['panels']):
            nodes = page.selected('data-cluster-panel', c['id'] + '-' + str(i))
            require(len(nodes) == 1, 'Research panel CVA boundary missing/duplicated')
            n = nodes[0]
            require(all(v in n['text'] for v in (panel['title'], panel['text'], panel['author'])), 'Research panel prose/author changed')
            for part in panel.get('parts', []):
                require(part['title'] in n['text'] and part['text'] in n['text'], 'Research split role changed')
            quotes = [x['text'] for x in page.nodes if x['tag'] == 'blockquote' and inside(x, n)]
            require(quotes == [e['quote'] for e in panel['evidence']], 'Research exact original quote differs')
            counts['researchPanels'] += 1
        if c['layout'] == 'sequence':
            require('함께 읽는 순서' in ''.join(n['text'] for n in page.selected('data-universe-cluster')),
                    'Reading sequence label missing')
        counts['researchClusters'] += 1
    return dict(counts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=SITE / 'dist')
    args = parser.parse_args()
    print(json.dumps(verify(args.dist), ensure_ascii=False, indent=2))
