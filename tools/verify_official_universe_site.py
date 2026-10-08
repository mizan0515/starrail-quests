"""Check generated official universe pages against the versioned source sidecar.

HTML structure, visible originals and links only; browser runtime is not assessed.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from verify_universe_source_site import SourcePage


def normalize(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')


class OfficialPage(SourcePage):
    def __init__(self):
        super().__init__()
        self.setting_links = []
        self.setting_controls = []
        self.setting_roots = []
        self.setting_options = []
        self.field_sections = []
        self.all_links = []
        self.title_proofs = []
        self.raw_fields = []
        self.catalog_returns = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        setting = self.ancestor(lambda n: n['attrs'].get('id') == 'setting-texts')
        super().handle_starttag(tag, attrs)
        node = self.stack[-1] if self.stack and self.stack[-1]['tag'] == tag else None
        if setting:
            if 'data-universe-records' in a:
                self.setting_roots.append(a)
            if tag == 'a' and 'data-source-record' in a:
                self.setting_links.append(node)
            if any(k in a for k in ('data-source-query', 'data-source-more', 'data-source-count', 'data-source-empty', 'data-source-kind')):
                self.setting_controls.append((tag, a, node))
            if tag == 'option':
                self.setting_options.append(node)
        if tag == 'section' and 'data-official-text-field' in a:
            self.field_sections.append(a)
        if tag == 'a':
            self.all_links.append(a)
        if 'data-official-title-proof' in a:
            self.title_proofs.append(node)
        if tag == 'pre' and 'official-source-raw' in self.classes(a):
            self.raw_fields.append(node)
        if 'data-catalog-return' in a:
            self.catalog_returns.append(node)


def parsed(html):
    p = OfficialPage()
    p.feed(html)
    p.close()
    return p


def body_errors(p, record):
    errors = []
    fields = record['fields']
    expected = {record['id'] + '-' + f['fieldKey'] + '-body': normalize(f['text']) for f in fields}
    actual = {k: normalize(v) for k, v in p.original.items()}
    if actual != expected:
        errors.append('original body membership/text differs')
    if p.h1 != [record['title']]:
        errors.append('displayed title differs')
    if p.duplicates:
        errors.append('duplicate IDs')
    if p.nested_p:
        errors.append('nested paragraph markup')
    for field in fields:
        anchor = record['id'] + '-' + field['fieldKey']
        section = next((a for a in p.field_sections if a.get('id') == anchor), {})
        body = p.bodies.get(anchor + '-body')
        if section.get('data-official-text-field') != field['fieldKey']:
            errors.append(anchor + ': field section missing')
        if not {'source-section', 'rw-reader', 'not-content'} <= p.classes(section) or section.get('data-reading-template') != 'reader':
            errors.append(anchor + ': reader boundary differs')
        if not body or body.get('scene') != anchor:
            errors.append(anchor + ': source body ownership differs')
        elif not {'rw-source-body', 'original-body'} <= p.classes(body['attrs']):
            errors.append(anchor + ': source body class missing')
        elif body['row'].get('data-reading-template') != 'row' or body['row'].get('data-reading-kind') != 'dialogue':
            errors.append(anchor + ': original row boundary differs')
    return errors


def self_test():
    r = {'id': 'fixture', 'title': '원문 제목', 'fields': [{'fieldKey': 'Story', 'text': '첫 문장.\n\n둘째 문장 & <기록>.'}]}
    html = '<h1>원문 제목</h1><section id="fixture-Story" class="source-section rw-reader not-content" data-reading-template="reader" data-official-text-field="Story"><div class="original-row" data-reading-template="row" data-reading-kind="dialogue"><p id="fixture-Story-body" class="original-body rw-source-body"><span>첫 문장.\n\n둘째 문장 &amp; &lt;기록&gt;.</span></p></div></section>'
    assert not body_errors(parsed(html), r)
    mutations = {
        'changed original': html.replace('첫 문장.', '바뀐 문장.'),
        'missing body': html.replace('fixture-Story-body', 'missing'),
        'wrong title': html.replace('원문 제목', '다른 제목'),
        'duplicate ID': html + '<div id="fixture-Story-body"></div>',
        'nested paragraph': html.replace('<span>', '<p>').replace('</span>', '</p>'),
        'wrong field': html.replace('data-official-text-field="Story"', 'data-official-text-field="Other"'),
    }
    assert all(body_errors(parsed(v), r) for v in mutations.values())
    shelf = parsed('<section id="source-records"><input data-source-query></section><section id="setting-texts"><div data-universe-records><input data-source-query><a data-source-record="a"><strong>A</strong></a></div></section>')
    assert len(shelf.setting_controls) == 1 and [n['attrs']['data-source-record'] for n in shelf.setting_links] == ['a']
    return {'status': 'PASS', 'negativeFixtures': len(mutations), 'scopeIsolation': True}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dist', type=Path)
    ap.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument('--report', type=Path)
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    repo, dist = args.repo, args.dist or args.repo / 'dist'
    official = json.loads((repo / 'data/official-universe-texts.json').read_text(encoding='utf8'))
    sources = json.loads((repo / 'data/universe-source-records.json').read_text(encoding='utf8'))
    originals = {r['id']: r for m in sources['modes'] for r in m['records']}
    records = official['records']
    errors, counts, pages = [], Counter(), {}

    def check(ok, label):
        if not ok: errors.append(label)

    def page(relative):
        if relative not in pages:
            path = dist / relative
            if not path.is_file():
                errors.append('Missing HTML: ' + relative)
                pages[relative] = None
            else:
                p = parsed(path.read_text(encoding='utf8'))
                check(not p.duplicates, relative + ': duplicate IDs')
                check(not p.nested_p, relative + ': nested paragraphs')
                pages[relative] = p
        return pages[relative]

    def metadata_url(table):
        return 'https://github.com/DimbreathBot/TurnBasedGameData/blob/' + official['evidence']['metadataCommit'] + '/' + table

    ids = [r['id'] for r in records]
    check(len(ids) == len(set(ids)), 'Input record IDs repeated')
    actual_ids = {p.stem for p in (dist / '우주/설정').glob('*.html')}
    check(actual_ids == set(ids), f'Official page membership differs: missing={sorted(set(ids)-actual_ids)[:8]}, extra={sorted(actual_ids-set(ids))[:8]}')
    for r in records:
        relative = '우주/설정/' + r['id'] + '.html'
        p = page(relative)
        if not p: continue
        errors.extend(relative + ': ' + e for e in body_errors(p, r))
        counts['records'] += 1
        counts['fields'] += len(r['fields'])
        expected_sections = [r['id'] + '-' + f['fieldKey'] for f in sorted(r['fields'], key=lambda f: f['role'] != 'story')]
        check([a.get('id') for a in p.field_sections] == expected_sections, relative + ': field order differs')
        expected_raw = [normalize(n['raw']) for n in r.get('names', [])] + [normalize(f['raw']) for f in sorted(r['fields'], key=lambda f: f['role'] != 'story')]
        check([normalize(n['text']) for n in p.raw_fields] == expected_raw, relative + ': escaped raw source text/order differs')
        check(any('한국어 수록본 4.6' in text for text in p.paragraphs), relative + ': observed version missing')
        links = [a.get('href') for a in p.all_links]
        for f in r['fields']:
            check('#' + r['id'] + '-' + f['fieldKey'] in links, relative + ': field jump link missing')
            check(metadata_url(f.get('sourceTable') or r['sourceTable']) in links, relative + ': field metadata URL missing')
        target_urls = ['/starrail-quests/우주/기록/' + i + '.html' for i in r['linkedSourceRecordIds']]
        linked_urls = [u for u in links if u and u.startswith('/starrail-quests/우주/기록/')]
        check(Counter(linked_urls) == Counter(target_urls), relative + ': linked original membership differs')
        for i in r['linkedSourceRecordIds']:
            check(i in originals, relative + ': unknown original record ' + i)
            target = page('우주/기록/' + i + '.html')
            if target and i in originals:
                check(target.h1 == [originals[i]['title']], relative + ': linked original title differs')
                counts['originalLinks'] += 1
        for ref in r['references']:
            for k in ('sourceTable', 'targetTable'):
                check(metadata_url(ref[k]) in links, relative + ': relationship metadata URL missing')
        expected_return = '/starrail-quests/우주/' + r['modeId'] + '.html#setting-texts'
        check(expected_return in links, relative + ': list return URL missing')
        check(bool(p.catalog_returns), relative + ': catalogue return boundary missing')
        names = r.get('names', [])
        if names:
            check(len(p.title_proofs) == 1, relative + ': title evidence panel missing/repeated')
            proof = p.title_proofs[0] if p.title_proofs else {'text': ''}
            for name in names:
                for value in (name['text'], name['sourcePointer'], name['textmapHash']):
                    check(str(value) in proof['text'], relative + ': title evidence value missing ' + str(value))
                check(metadata_url(name['sourceTable']) in links, relative + ': title metadata URL missing')
                for step in name.get('proof', []):
                    check(metadata_url(step['sourceTable']) in links, relative + ': title join metadata URL missing')
                    for value in (step['pointer'], step['value']):
                        check(str(value) in proof['text'], relative + ': title join value missing')
        else:
            check(not p.title_proofs, relative + ': title proof with no names')
    for mode in sources['modes']:
        expected = [r for r in records if r['modeId'] == mode['id']]
        if not expected: continue
        relative = '우주/' + mode['id'] + '.html'
        p = page(relative)
        if not p: continue
        check('setting-texts' in p.ids, relative + ': setting shelf missing')
        check(len(p.setting_roots) == 1, relative + ': setting index boundary missing/repeated')
        if p.setting_roots:
            a = p.setting_roots[0]
            for key, val in (('data-query-key', 'textQuery'), ('data-limit-key', 'textLimit'), ('data-kind-key', 'textKind')):
                check(a.get(key) == val, relative + ': independent filter state key differs')
        check([n['attrs'].get('data-source-record') for n in p.setting_links] == [r['id'] for r in expected], relative + ': setting list membership/order differs')
        for key, tag in (('data-source-query','input'),('data-source-more','button'),('data-source-count','p'),('data-source-empty','p')):
            found = [(t,a,n) for t,a,n in p.setting_controls if key in a]
            check(len(found)==1 and found[0][0]==tag, relative + ': '+key+' missing/repeated')
            if found:
                t,a,n=found[0]
                if key=='data-source-count':check(a.get('role')=='status' and a.get('aria-live')=='polite' and str(len(expected))+'개 기록' in n['text'],relative+': accessible initial count differs')
                if key=='data-source-query':check(a.get('type')=='search',relative+': search input type differs')
                if key=='data-source-empty':check('hidden' in a,relative+': initial empty state visible')
        categories = list(dict.fromkeys(r['kind'] for r in expected))
        kind_controls = [(t,a,n) for t,a,n in p.setting_controls if 'data-source-kind' in a]
        check(len(kind_controls)==int(len(categories)>1), relative + ': kind selector presence differs')
        if len(categories)>1:
            check(kind_controls[0][0]=='select' if kind_controls else False, relative+': kind control is not select')
            check([n['attrs'].get('value') for n in p.setting_options]==['']+categories,relative+': kind option membership/order differs')
        for i,(r,n) in enumerate(zip(expected,p.setting_links)):
            a=n['attrs'];label=relative+'/'+r['id']
            check(a.get('href')=='/starrail-quests/우주/설정/'+r['id']+'.html',label+': canonical URL differs')
            check(a.get('id')=='universe-source-'+r['id'] and 'data-reading-link' in a,label+': stable return anchor missing')
            check(a.get('data-source-kind-value')==r['kind'],label+': kind metadata differs')
            check(normalize(a.get('data-search',''))==normalize(' '.join(f['text'] for f in r['fields'])),label+': searchable source text differs')
            check(('hidden' in a)==(i>=12),label+': initial visibility differs')
            titles=[c['text'] for c in n['children'] for c in (c['children'] if c['tag']=='span' else [c]) if c['tag']=='strong']
            check(titles==[r['title']],label+': displayed list title differs')
            counts['modeLinks']+=1
        check(any('4.6 수록 문구' in t for t in p.paragraphs),relative+': setting list observed version missing')
    report={'status':'FAIL' if errors else 'PASS','counts':dict(counts),'errorCount':len(errors),'errors':errors[:100],'scope':'Generated HTML originals, source attribution and list structure; browser filtering/layout not assessed'}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return int(bool(errors))


if __name__=='__main__':
    sys.exit(main())
