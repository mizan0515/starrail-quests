"""Check every generated HTML head and the complete canonical sitemap.

These are static publication checks, not a claim that Google has indexed a URL.
"""
import argparse
import html
import json
import re
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlparse


SITE = 'https://mizan0515.github.io'
BASE = '/starrail-quests'
GLOBAL_DESCRIPTION = '스타레일 한국어 임무와 설정을 맥락으로 연결한 자료집'
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
VERIFICATION_FILENAME = 'google450473d70e90c4cc.html'
VERIFICATION_BYTES = b'google-site-verification: google450473d70e90c4cc.html'
PRIVATE_METADATA = re.compile(r'(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|localhost|127\.0\.0\.1|\.codex-work|node_modules|SKILL\.md|AGENTS\.md)', re.I)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Head(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.lang = ''
        self.titles = []
        self.in_title = False
        self.canonical = []
        self.meta = {}
        self.redirect = False
        self.feed(text.split('</head>', 1)[0])

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'html':
            self.lang = a.get('lang', '')
        if tag == 'title':
            self.in_title = True
            self.titles.append('')
        if tag == 'link' and a.get('rel') == 'canonical':
            self.canonical.append(a.get('href', ''))
        if tag == 'meta':
            key = (a.get('name') or a.get('property') or '').lower()
            if key:
                self.meta.setdefault(key, []).append(a.get('content', ''))
            if a.get('http-equiv', '').lower() == 'refresh':
                self.redirect = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.titles[-1] += data


def canonical_url(relative, base=BASE):
    return SITE + base.rstrip('/') + '/' + quote(relative, safe='/')


def source_reader(relative, repository):
    if relative.startswith('우주/기록/') or relative.startswith('우주/설정/'):
        return True
    if relative.startswith('대사/') and relative not in ['대사/official-4.6.html']:
        return True
    if relative.startswith('문서/') and repository:
        path = repository / 'data/documents' / (Path(relative).stem + '.json')
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            return any(row.get('text', '').strip() and row.get('text') != '한국어 본문 미수록'
                       for section in data.get('sections', []) for row in section.get('rows', []))
    return False


def inspect(root, repository=None, base=BASE):
    root = Path(root)
    pages = {}
    indexable = set()
    counts = Counter()
    for path in sorted(root.rglob('*.html')):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8')
        # The single proof file downloaded for this site is an exact 53-byte artifact.
        if re.fullmatch(r'google.*\.html', relative):
            require(relative == VERIFICATION_FILENAME and path.read_bytes() == VERIFICATION_BYTES,
                    relative + ': invalid Google verification filename/bytes')
            counts['verificationFiles'] += 1
            continue
        head = Head(text)
        require(len(head.titles) == 1 and head.titles[0].strip(), relative + ': missing or duplicate title')
        require(len(head.canonical) == 1, relative + ': canonical must occur exactly once')
        canonical = head.canonical[0]
        parsed = urlparse(canonical)
        require(parsed.scheme == 'https' and parsed.netloc == urlparse(SITE).netloc,
                relative + ': canonical must be an absolute HTTPS site URL')
        require(not parsed.query and not parsed.fragment, relative + ': reader state leaked into canonical')
        require(unquote(parsed.path).startswith(base.rstrip('/') + '/'), relative + ': canonical outside site base')
        target = unquote(parsed.path)[len(base.rstrip('/')) + 1:]
        require(target.endswith('.html') and (root / target).is_file(), relative + ': canonical target file missing')
        robots = ','.join(head.meta.get('robots', []) + head.meta.get('googlebot', [])).lower()
        noindex = bool(re.search(r'\b(?:noindex|none)\b', robots))
        nofollow = bool(re.search(r'\b(?:nofollow|none)\b', robots))
        status = relative in ['404.html', '500.html']
        home_alias = relative == '시작.html'
        if status:
            require(noindex, relative + ': status page must be noindex')
        if home_alias:
            require(canonical == canonical_url('index.html', base), relative + ': home alias canonical differs')
        require(not noindex or head.redirect or status or home_alias, relative + ': unexpected robots/googlebot noindex')
        excluded = head.redirect or status or home_alias or noindex
        if not excluded:
            require(not nofollow, relative + ': indexable page cannot be nofollow')
            require(canonical == canonical_url(relative, base), relative + ': canonical differs from output path')
            require(head.lang == 'ko', relative + ': Korean document language missing')
            descriptions = head.meta.get('description', [])
            require(len(descriptions) == 1 and descriptions[0].strip(), relative + ': missing or duplicate description')
            require(descriptions[0] != GLOBAL_DESCRIPTION, relative + ': page still uses global description')
            require(len(descriptions[0]) <= 500, relative + ': description is not a concise page summary')
            for key in ['og:title', 'og:description', 'og:url']:
                require(len(head.meta.get(key, [])) == 1, relative + ': missing or duplicate ' + key)
            require(head.meta['og:url'][0] == canonical, relative + ': OG URL differs from canonical')
            require(head.meta['og:description'][0] == descriptions[0], relative + ': OG description differs')
            require(not PRIVATE_METADATA.search(head.titles[0] + ' ' + descriptions[0]),
                    relative + ': private implementation metadata')
            body = text.split('</head>', 1)[-1]
            main = re.search(r'<main\b[^>]*>([\s\S]*?)</main>', body)
            require(main is not None, relative + ': server HTML has no main body')
            links = re.findall(r'<a\b[^>]*\bhref="([^"]+)"', main[1])
            require(any(link and not link.startswith(('#', 'javascript:')) for link in links),
                    relative + ': no crawlable HTML link in main body')
            if source_reader(relative, repository):
                source = re.search(r'<p\b[^>]*\bclass="[^"]*\brw-source-body\b[^"]*"[^>]*>([\s\S]*?)</p>', main[1])
                require(source is not None and html.unescape(re.sub(r'<[^>]*>', '', source[1])).strip(),
                        relative + ': source reader has no server-rendered original text')
                counts['sourceReaders'] += 1
            indexable.add(canonical)
            counts['indexableHtml'] += 1
        else:
            counts['excludedHtml'] += 1
        pages[canonical_url(relative, base)] = {'canonical': canonical, 'excluded': excluded, 'path': relative}
        counts['html'] += 1
    require(counts['verificationFiles'] == 1, 'registered Google verification artifact missing')
    sitemap_index = root / 'sitemap-index.xml'
    require(sitemap_index.exists(), 'sitemap-index.xml missing')
    entries = ET.parse(sitemap_index).findall('s:sitemap/s:loc', NS)
    require(entries, 'empty sitemap index')
    sitemap_urls = []
    for entry in entries:
        parsed = urlparse(entry.text or '')
        require(parsed.scheme == 'https' and parsed.netloc == urlparse(SITE).netloc and not parsed.query and not parsed.fragment,
                'invalid sitemap index URL')
        require(unquote(parsed.path).startswith(base.rstrip('/') + '/'), 'sitemap index outside project base')
        filename = unquote(parsed.path)[len(base.rstrip('/')) + 1:]
        require('/' not in filename and re.fullmatch(r'sitemap-\d+\.xml', filename), 'invalid sitemap child path')
        child = root / filename
        require(child.exists(), 'sitemap child file missing: ' + filename)
        require(child.stat().st_size <= 50 * 1024 * 1024, 'sitemap exceeds 50 MiB')
        rows = ET.parse(child).findall('s:url/s:loc', NS)
        require(len(rows) <= 50000, 'sitemap exceeds 50,000 URLs')
        sitemap_urls.extend(entry.text or '' for entry in rows)
    require(len(sitemap_urls) == len(set(sitemap_urls)), 'duplicate sitemap URL')
    for url in sitemap_urls:
        require(url in pages, 'sitemap URL has no exact output HTML: ' + url)
        page = pages[url]
        require(not page['excluded'], 'excluded/redirect/status URL in sitemap: ' + page['path'])
        require(url == page['canonical'], 'sitemap URL differs from canonical: ' + page['path'])
    require(set(sitemap_urls) == indexable, 'indexable canonical missing from sitemap: ' + str(sorted(indexable - set(sitemap_urls))[:4]))
    counts['sitemapUrls'] = len(sitemap_urls)
    counts['sitemaps'] = len(entries)
    return dict(counts)


def self_test():
    canonical = canonical_url('index.html')
    valid = ('<!doctype html><html lang="ko"><head><title>임무 자료집</title>'
             f'<link rel="canonical" href="{canonical}"><meta name="description" content="임무·원문 찾기">'
             '<meta property="og:title" content="임무 자료집"><meta property="og:description" content="임무·원문 찾기">'
             f'<meta property="og:url" content="{canonical}"></head><body><main><a href="/starrail-quests/설정집.html">설정집</a></main></body></html>')
    def fixture(root, text=valid, urls=None):
        (root / 'index.html').write_text(text, encoding='utf-8')
        (root / VERIFICATION_FILENAME).write_bytes(VERIFICATION_BYTES)
        (root / 'sitemap-index.xml').write_text(f'<sitemapindex xmlns="{NS["s"]}"><sitemap><loc>{SITE}{BASE}/sitemap-0.xml</loc></sitemap></sitemapindex>', encoding='utf-8')
        (root / 'sitemap-0.xml').write_text(f'<urlset xmlns="{NS["s"]}">' + ''.join(f'<url><loc>{html.escape(url)}</loc></url>' for url in (urls if urls is not None else [canonical])) + '</urlset>', encoding='utf-8')
    faults = {
        'extensionless sitemap': (valid, [canonical[:-5]]),
        'duplicate sitemap': (valid, [canonical, canonical]),
        'missing sitemap page': (valid, []),
        'query canonical': (valid.replace(canonical, canonical + '?speaker=ice'), None),
        'fragment canonical': (valid.replace(canonical, canonical + '#original'), None),
        'relative canonical': (valid.replace(canonical, BASE + '/index.html'), None),
        'duplicate canonical': (valid.replace('</head>', f'<link rel="canonical" href="{canonical}"></head>'), None),
        'global description': (valid.replace('임무·원문 찾기', GLOBAL_DESCRIPTION), None),
        'private metadata': (valid.replace('임무·원문 찾기', 'D:/game/.codex-work/private'), None),
        'googlebot noindex': (valid.replace('</head>', '<meta name="googlebot" content="noindex"></head>'), None),
        'robots nofollow': (valid.replace('</head>', '<meta name="robots" content="nofollow"></head>'), None),
        'redirect in sitemap': (valid.replace('</head>', '<meta http-equiv="refresh" content="0;url=/starrail-quests/index.html"></head>'), None),
        'empty server body': (valid.replace('<main>', '<section>').replace('</main>', '</section>'), None),
        'no crawlable links': (valid.replace('href="/starrail-quests/설정집.html"', 'href="#original"'), None),
    }
    with tempfile.TemporaryDirectory(prefix='star-seo-canary-') as directory:
        root = Path(directory)
        fixture(root)
        inspect(root)
        for name, (text, urls) in faults.items():
            fixture(root, text, urls)
            try:
                inspect(root)
            except AssertionError:
                continue
            raise AssertionError('accepted SEO fault: ' + name)
        fixture(root)
        source_path = root / '대사/test.html'
        source_path.parent.mkdir()
        source_url = canonical_url('대사/test.html')
        source_html = valid.replace(canonical, source_url).replace('</main>', '<p class="original-body rw-source-body">원문 대사</p></main>')
        source_path.write_text(source_html, encoding='utf-8')
        fixture(root, urls=[canonical, source_url])
        inspect(root)
        source_path.write_text(source_html.replace('원문 대사', ''), encoding='utf-8')
        try:
            inspect(root)
        except AssertionError:
            pass
        else:
            raise AssertionError('accepted empty server-rendered source reader')
        source_path.unlink()
        source_path.parent.rmdir()
        fixture(root)
        verification = root / VERIFICATION_FILENAME
        require(inspect(root)['verificationFiles'] == 1, 'exact registered Google proof not recognized')
        for name, proof in [('malformed proof', VERIFICATION_BYTES + b'\n'), ('wrong proof target', VERIFICATION_BYTES.replace(b'450473', b'450474'))]:
            verification.write_bytes(proof)
            try:
                inspect(root)
            except AssertionError:
                pass
            else:
                raise AssertionError('accepted ' + name)
        verification.unlink()
        try:
            inspect(root)
        except AssertionError:
            pass
        else:
            raise AssertionError('accepted missing registered Google proof')
        fixture(root)
        arbitrary = root / 'google012345abcdef.html'
        arbitrary.write_bytes(b'google-site-verification: google012345abcdef.html')
        try:
            inspect(root)
        except AssertionError:
            pass
        else:
            raise AssertionError('accepted arbitrary Google verification filename')
        arbitrary.unlink()
        modified = root / 'google450473d70e90c4cc-extra.html'
        modified.write_bytes(VERIFICATION_BYTES)
        try:
            inspect(root)
        except AssertionError:
            pass
        else:
            raise AssertionError('accepted modified Google verification filename suffix')
    return len(faults) + 6


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('dist'))
    parser.add_argument('--base', default=BASE)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--self-test-only', action='store_true')
    args = parser.parse_args()
    canaries = self_test() if args.self_test or args.self_test_only else 0
    if args.self_test_only:
        print(json.dumps({'status': 'PASS', 'faultCanaries': canaries, 'scope': 'static SEO validator self-test'}))
        return
    counts = inspect(args.root, Path(__file__).resolve().parents[1], args.base)
    print(json.dumps({'status': 'PASS', **counts, 'faultCanaries': canaries, 'scope': 'static HTML metadata and sitemap, Google indexing unverified'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
