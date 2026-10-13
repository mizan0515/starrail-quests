"""Verify rendered quest navigation against the existing Node metadata model.

This checks rendered links, explicit owners, catalogue order and role counts.
Original Korean/source decoding and the full publication inverse are separate
mandatory release gates. No producer, game code or build is executed here.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

sys.dont_write_bytecode = True
SITE = Path(__file__).resolve().parents[1]
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Element:
    def __init__(self, tag, attrs):
        self.tag, self.attrs, self.children, self.parts = tag, dict(attrs), [], []

    def descendants(self, tag=None, attr=None):
        for child in self.children:
            if (tag is None or child.tag == tag) and (attr is None or attr in child.attrs):
                yield child
            yield from child.descendants(tag, attr)

    def text(self):
        return ''.join(part if isinstance(part, str) else part.text() for part in self.parts)


class Complete(Exception):
    pass


class SectionParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root, self.stack = None, []

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs)
        if self.root is None:
            self.root = node
        elif self.stack:
            self.stack[-1].children.append(node)
            self.stack[-1].parts.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if not self.stack:
            return
        index = next((i for i in range(len(self.stack)-1,-1,-1) if self.stack[i].tag == tag), None)
        if index is not None:
            del self.stack[index:]
            if not self.stack:
                raise Complete()

    def handle_data(self, data):
        if self.stack:
            self.stack[-1].parts.append(data)


def section(text, marker):
    pattern = r'<section\b[^>]*\b' + (r'data-quest-reading-nav(?:\s|=|>)' if marker == 'nav' else r'id=["\']deep-timeline-originals["\']') + r'[^>]*>'
    found = list(re.finditer(pattern, text))
    require(len(found) <= 1, 'Duplicate '+marker+' section')
    if not found:
        return None
    parser = SectionParser()
    try:
        parser.feed(text[found[0].start():])
    except Complete:
        return parser.root
    raise ValueError('Unclosed '+marker+' section')


def normalized(text):
    return ' '.join(text.split())


def route(href, base):
    require(isinstance(href,str) and href and '\\' not in href, 'Invalid canonical link '+repr(href))
    url = urlsplit(href)
    require(not url.scheme and not url.netloc and not url.query, 'Noncanonical/external source link '+href)
    require(not re.search(r'%2f|%5c',url.path,re.I), 'Encoded path separator '+href)
    decoded = unquote(url.path)
    require(decoded.startswith(base+'/') and not any(p in {'.','..'} for p in decoded.split('/')), 'Source link escapes site base '+href)
    return decoded[len(base)+1:]


def model_check(model):
    sources, quests = model['sources'], model['quests']
    require(len(sources) == 15311 and len(quests) == 1284, 'Current model cohort size differs')
    require(len({s['id'] for s in sources}) == len(sources) and len({s['url'] for s in sources}) == len(sources), 'Duplicate model source')
    require(len({q['id'] for q in quests}) == len(quests), 'Duplicate model quest')
    owned = {mission for source in sources for mission in source['missions']}
    require(len(owned) == 640 and sum(not s['missions'] for s in sources) == 79, 'Explicit owner/orphan partition differs')
    require(model['optionReferences'] == 840, 'Separate option-reference count differs')
    for source in sources:
        require(route('/starrail-quests/'+source['url'],'/starrail-quests') == source['url'], 'Model canonical source route differs '+source['id'])
        require(source['occurrences'] == sum(source['roles'].values()) > 0, 'Role occurrence count differs '+source['id'])
        require(not any(field in source for field in ('text','rows','proof','sourceProofs')), 'Metadata export contains bodies/proofs')
    return {'quests':len(quests),'sources':len(sources),'explicitQuestGroups':len(owned),'ownerlessSources':79,'separateOptionReferences':840}


def load_model(repo, node):
    code = """
import fs from 'node:fs';
import {readingSources,questReadingSources,readingSourceRoute,groupReadingSources,nearbyReadingSources,readingRoleSummary} from './src/lib/quest-reading-sources.ts';
import {deepScenes} from './src/lib/deep-timeline.ts';
const nav=(record)=>({...record,groups:record.missions.map(mission=>({mission,groups:groupReadingSources(questReadingSources(mission)).map(group=>({kind:group.kind,total:group.records.length,ids:nearbyReadingSources(group.records,record.url).map(s=>s.id)}))}))});
const sources=readingSources.map(source=>nav({...source,roleSummary:readingRoleSummary(source)}));
const quests=JSON.parse(fs.readFileSync('data/catalog.json','utf8')).filter(q=>q.category==='퀘스트').map(q=>({...nav(readingSourceRoute('/문서/'+q.id+'.html')),id:q.id,sourceIds:questReadingSources(q.id).map(s=>s.id)}));
console.log(JSON.stringify({sources,quests,optionReferences:deepScenes.reduce((n,s)=>n+(s.optionReferences?.length||0),0)}));
"""
    result = subprocess.run([node,'--input-type=module','-e',code],cwd=repo,capture_output=True,text=True,encoding='utf8',timeout=120)
    require(result.returncode == 0, 'Node metadata export failed: '+result.stderr[-2000:])
    model = json.loads(result.stdout)
    model_check(model)
    return model


def nav_check(text, record, sources, base):
    nav = section(text, 'nav')
    require(nav is not None, 'Current navigation absent')
    current = list(nav.descendants('a','data-current-reader-title'))
    require(len(current) == 1 and route(current[0].attrs.get('href'),base) == record['url'], 'Current reader canonical URL differs')
    require(normalized(current[0].text()) == normalized(record['title']), 'Current reader title differs')
    require(current[0].attrs.get('aria-current') == 'page', 'Current reader semantic state absent')
    toc = list(nav.descendants('nav','data-quest-local-toc'))
    require(len(toc) == 1, 'Local TOC absent/duplicated')
    fallback = list(toc[0].descendants('a'))
    require(len(fallback) == 1 and fallback[0].attrs.get('href') == '#_top', 'Static local TOC fallback differs')
    require(re.search(r'\bid=["\']_top["\']',text) is not None, 'Static top anchor absent')
    owners = list(nav.descendants('details','data-reading-mission'))
    require([owner.attrs['data-reading-mission'] for owner in owners] == record['missions'], 'Rendered explicit owner IDs differ')
    expected_groups = {owner['mission']:owner['groups'] for owner in record['groups']}
    links_checked = 0
    for owner in owners:
        mission = owner.attrs['data-reading-mission']
        links = list(owner.descendants('a','data-quest-reading-link'))
        require(links and route(links[0].attrs.get('href'),base) == '문서/'+mission+'.html', 'Quest primary-reader link differs '+mission)
        require(urlsplit(links[0].attrs['href']).fragment == 'original', 'Quest primary-reader anchor differs '+mission)
        groups = list(owner.descendants('details','data-reading-group'))
        expected = expected_groups[mission]
        require([group.attrs['data-reading-group'] for group in groups] == [mission+':'+group['kind'] for group in expected], 'Source-kind groups differ '+mission)
        for group, specification in zip(groups, expected):
            summaries = [child for child in group.children if child.tag == 'summary']
            require(len(summaries) == 1 and normalized(summaries[0].text()) == specification['kind']+format(specification['total'],',')+'개', 'Source-kind catalogue total differs '+mission)
            direct = list(group.descendants('a','data-quest-reading-link'))
            ids = specification['ids']
            require(len(ids) <= 8, 'Model nearby source limit exceeded')
            require(len(direct) == len(ids)+(specification['total']>8), 'Bounded source-link count differs '+mission+':'+specification['kind'])
            for link, identifier in zip(direct, ids):
                source = sources[identifier]
                require(route(link.attrs.get('href'),base) == source['url'], 'Canonical source route differs '+identifier)
                require(mission in source['missions'] and source['kind'] == specification['kind'], 'Source menu forged ownership/kind '+identifier)
                require(link.attrs.get('id') == 'quest-nav-'+mission+'-'+identifier, 'Stable source return anchor differs '+identifier)
                require(link.attrs.get('aria-current') == ('page' if source['url'] == record['url'] else None), 'Related current-reader semantic state differs '+identifier)
                titles = list(link.descendants('span'))
                require(len(titles) == 1 and normalized(titles[0].text()) == normalized(source['title']), 'Related source title differs '+identifier)
                small = list(link.descendants('small'))
                expected_label = source['roleSummary']+(' · 공동 호출' if len(source['missions'])>1 else '')
                require(len(small) == 1 and normalized(small[0].text()) == expected_label, 'Menu role occurrence count differs '+identifier)
                links_checked += 1
            if specification['total']>8:
                require(route(direct[-1].attrs.get('href'),base) == '문서/'+mission+'.html' and urlsplit(direct[-1].attrs['href']).fragment == 'deep-timeline-originals', 'Full related-source catalogue link differs '+mission)
        expected_links = 1+sum(len(group['ids'])+(group['total']>8) for group in expected)
        require(len(links) == expected_links, 'Unexpected additional source links '+mission)
    global_nav = re.search(r'<nav\b[^>]*\baria-label=["\']주요 탐색["\'][^>]*>(.*?)</nav>',text,re.S)
    require(global_nav is not None and 'index.html' in global_nav[1] and '대사.html' in text, 'Global catalogue navigation absent')
    return links_checked


def appendix_check(text, quest, sources, base):
    appendix = section(text, 'appendix')
    expected = quest['sourceIds']
    if not expected:
        require(appendix is None, 'Unsupported quest appendix appeared')
        return 0
    require(appendix is not None, 'Complete quest source appendix absent')
    links = list(appendix.descendants('a','data-reading-link'))
    require([route(link.attrs.get('href'),base) for link in links] == [sources[identifier]['url'] for identifier in expected], 'Complete original-order quest appendix links differ')
    require([normalized(link.text()) for link in links] == [normalized(sources[identifier]['title']) for identifier in expected], 'Complete appendix source titles differ')
    rows = list(appendix.descendants('li'))
    require(len(rows) == len(expected), 'Quest appendix occurrence rows differ')
    for row, identifier in zip(rows, expected):
        source = sources[identifier]
        counts = [span for span in row.descendants('span') if 'quest-source-count' in span.attrs.get('class','').split()]
        label = source['kind']+' · '+source['roleSummary']+(' · 여러 임무가 함께 호출' if len(source['missions'])>1 else '')
        require(len(counts) == 1 and normalized(counts[0].text()) == label, 'Appendix role occurrence count differs '+identifier)
    return len(expected)


def expansion(dist, report_path, base):
    if report_path is None:
        return None, {'mode':'RAW_HTML','fullPublicationInverseGate':'Root mandatory when optimized'}
    import optimize_publication as publication
    raw = report_path.read_bytes()
    report = json.loads(raw)
    require(report['base'] == base, 'Publication receipt base differs')
    assets_checked = 0
    for name, receipt in report['assets'].items():
        require(Path(name).name == name, 'Shared asset receipt escapes its directory')
        file = dist/'_shared'/name
        require(file.is_file() and sha(file.read_bytes()) == receipt['sha256'], 'Actual shared asset differs '+name)
        assets_checked += 1
    for name, receipt in report.get('proofCodecFiles',{}).items():
        require(Path(name).name == name, 'Codec receipt escapes its directory')
        file = dist/'_publication'/name
        require(file.is_file() and file.stat().st_size == receipt['bytes'] and sha(file.read_bytes()) == receipt['sha256'], 'Actual publication codec differs '+name)
    for shard in report.get('proofShards',{}).values():
        relative = route(shard['url'],base)
        file = dist/relative
        require(relative.startswith('_shared/') and file.is_file() and sha(file.read_bytes()) == shard['assetSha256'], 'Actual publication proof shard differs '+relative)
    expand = publication.expansion_function(report)
    def checked(text, relative):
        restored = expand(text)
        require(relative in report['originalFiles'] and sha(restored.encode('utf8')) == report['originalFiles'][relative], 'Rendered HTML exact inverse differs '+relative)
        return restored
    return checked, {'mode':'EXACT_PUBLICATION_INVERSE','reportSha256':sha(raw),'actualSharedAssets':assets_checked,'actualProofShards':len(report.get('proofShards',{})),'actualCodecFiles':len(report.get('proofCodecFiles',{})),'fullPublicationInverseGate':'Root optimizer.verify remains mandatory for all generated files and size'}


def self_tests():
    # Minimal rendered fixture exercises the same production HTMLParser checks.
    source = {'id':'one','title':'자료','url':'대화/연출-one.html','kind':'연출 원문','missions':['quest-1'],'occurrences':1,'roles':{'NON_SPOKEN_OPTION_REFERENCE':1},'roleSummary':'선택지 참조 1'}
    quest = {'id':'quest-1','sourceIds':['one']}
    text = '<section id="deep-timeline-originals"><details><ul><li><a href="/starrail-quests/대화/연출-one.html" data-reading-link>자료</a><span class="quest-source-count">연출 원문 · 선택지 참조 1</span></li></ul></details></section>'
    require(appendix_check(text,quest,{'one':source},'/starrail-quests') == 1, 'Positive appendix fixture failed')
    record = dict(source,groups=[{'mission':'quest-1','groups':[{'kind':'연출 원문','total':1,'ids':['one']}]}])
    nav = '<div id="_top"></div><section data-quest-reading-nav data-pagefind-ignore><a data-current-reader-title href="/starrail-quests/대화/연출-one.html" aria-current="page">자료</a><nav data-quest-local-toc><a href="#_top">처음</a></nav><details data-reading-mission="quest-1"><a data-quest-reading-link href="/starrail-quests/문서/quest-1.html#original">임무</a><details data-reading-group="quest-1:연출 원문"><summary>연출 원문<span>1개</span></summary><a data-quest-reading-link id="quest-nav-quest-1-one" aria-current="page" href="/starrail-quests/대화/연출-one.html"><span>자료</span><small>선택지 참조 1</small></a></details></details></section><nav aria-label="주요 탐색"><a href="/starrail-quests/index.html">목록</a></nav><a href="/starrail-quests/대사.html">원문 자료실</a>'
    require(nav_check(nav,record,{'one':source},'/starrail-quests') == 1, 'Positive navigation fixture failed')
    tests = []
    for name, altered in [('missing appendix',''),('wrong canonical path',text.replace('연출-one','연출-two')),('option-only zero count',text.replace('참조 1','참조 0')),('role promoted to spoken',text.replace('선택지 참조','대사')),('duplicate appendix source',text.replace('</ul>','<li><a href="/starrail-quests/대화/연출-one.html" data-reading-link>자료</a></li></ul>'))]:
        try:
            appendix_check(altered,quest,{'one':source},'/starrail-quests')
        except ValueError:
            tests.append(name)
        else:
            raise ValueError('Negative fixture accepted '+name)
    try:
        route('https://outside.test/starrail-quests/대화/연출-one.html','/starrail-quests')
    except ValueError:
        tests.append('external source route')
    else:
        raise ValueError('External canonical route accepted')
    for name, altered in [('forged explicit owner',nav.replace('data-reading-mission="quest-1"','data-reading-mission="quest-2"')),('current reader title missing',nav.replace('data-current-reader-title','data-wrong-title')),('static top fallback broken',nav.replace('href="#_top"','href="#original"')),('nearby occurrence role differs',nav.replace('선택지 참조 1','대사 1'))]:
        try:
            nav_check(altered,record,{'one':source},'/starrail-quests')
        except ValueError:
            tests.append(name)
        else:
            raise ValueError('Negative navigation fixture accepted '+name)
    return {'negativeCases':len(tests),'rejected':tests}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=SITE)
    parser.add_argument('--dist',type=Path)
    parser.add_argument('--publication-report',type=Path)
    parser.add_argument('--base',default='/starrail-quests')
    parser.add_argument('--node',default='node')
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--report',type=Path)
    args = parser.parse_args()
    base = args.base.rstrip('/')
    result = {'status':'PASS','scope':'Rendered metadata-model conformance; original Korean/source decoding uses separate source gates','verifierSha256':sha(Path(__file__).read_bytes()),'checkedUrls':[],'checks':{}}
    current = None
    try:
        repo = args.repo.resolve()
        model = load_model(repo,args.node)
        result['checks']['model'] = model_check(model)
        result['modelSourceHashes'] = {name:sha((repo/name).read_bytes()) for name in ['src/lib/quest-reading-sources.ts','src/lib/deep-timeline.ts','src/components/QuestReadingNav.astro','src/components/DeepMissionSources.astro']}
        if args.self_test:
            result['checks']['selfTests'] = self_tests()
        if args.dist:
            dist = args.dist.resolve()
            expand, receipt = expansion(dist,args.publication_report,base)
            result['checks']['publication'] = receipt
            sources = {source['id']:source for source in model['sources']}
            expected = [('quest',quest) for quest in model['quests']]+[('source',source) for source in model['sources']]
            contexts = json.loads((repo/'data/dialogue-contexts.json').read_bytes())
            ranges = json.loads((repo/'data/mission-talk-range-dialogue.json').read_bytes())
            expected += [('unowned',{'url':'대화/'+group['id']+'.html','title':'현재 원문','missions':[],'groups':[]}) for group in contexts['groups']]
            expected += [('unowned',{'url':'대화/범위-'+record['id']+'.html','title':'현재 원문','missions':[],'groups':[]}) for record in ranges['records']]
            counts = Counter()
            require(len({record['url'] for _,record in expected}) == len(expected), 'Duplicate expected reader route')
            for kind, record in expected:
                current = record['url']
                file = dist/current
                require(file.is_file(), 'Rendered canonical reader absent')
                text = file.read_bytes().decode('utf8',errors='strict')
                if expand:
                    text = expand(text,current)
                else:
                    require(not re.search(r'data-(?:ui|pf|pj|ps|pr|publication-fragment)\b',text), 'Optimized reader requires --publication-report')
                counts['nearbySourceLinks'] += nav_check(text,record,sources,base)
                if kind == 'quest':
                    counts['completeAppendixLinks'] += appendix_check(text,record,sources,base)
                result['checkedUrls'].append(current)
                counts[kind] += 1
                if len(result['checkedUrls']) % 5000 == 0:
                    print('Navigation checked '+str(len(result['checkedUrls']))+'/'+str(len(expected)),file=sys.stderr,flush=True)
            result['checks']['dist'] = dict(counts,checkedReaders=len(expected),zeroRendererFailures=True)
        require(args.dist or args.self_test, 'Use --dist and/or --self-test')
    except (ValueError,KeyError,OSError,UnicodeError,subprocess.SubprocessError,json.JSONDecodeError) as error:
        result['status'] = 'FAIL'
        result['firstFailure'] = {'url':current,'reason':str(error)}
    if args.report:
        args.report.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    summary = {key:value for key,value in result.items() if key != 'checkedUrls'}
    summary['checkedUrlCount'] = len(result['checkedUrls'])
    print(json.dumps(summary,ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
