"""Adversarial publication attribute tests, with no site/build mutations.

Preflight fixtures use memory-backed files. The actual pinned pako is executed
in Node; DOM targets are explicit mocks and are not claimed as browser testing.
"""
import argparse
import base64
import copy
import gzip
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publication_attributes as A
import optimize_publication as P

INPUT_HASHES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (Path(A.__file__), Path(P.__file__))}


class OriginalProbe(HTMLParser):
    def __init__(self, value):
        super().__init__(convert_charrefs=True)
        self.attrs, self.bodies, self.active, self.stack = [], [], None, []
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.attrs.append((tag, attrs))
        if tag == 'p' and 'original-body' in attrs.get('class', '').split():
            self.active = {'id': attrs['id'], 'text': ''}
            self.bodies.append(self.active)
        if tag not in ('meta', 'link', 'br', 'img', 'input'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == 'p':
            self.active = None
        if tag in self.stack:
            del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]

    def handle_data(self, value):
        if self.active is not None and not any(t in self.stack for t in ('script', 'style')):
            self.active['text'] += value


def directory_fixture(values=None):
    values = values or ['한국어 &amp; &quot; &#39; 😀\r\n둘째 줄 ' * 40,
                        '개척자 &lt;기록&gt; &#x1f600;\n세 번째 줄 ' * 42]
    return ''.join('<a id="record-' + str(i) + '" data-source-record data-search="' + value
                   + '" href="/starrail-quests/원문/' + str(i) + '.html#row-1"><b>원문 제목 ' + str(i)
                   + '</b></a>' for i, value in enumerate(values))


def pooled_fixture():
    original = directory_fixture()
    records = {}
    changed, loader, count = A.search_attributes(original, records)
    assert loader is not None and count == 2
    return original, changed, loader, records


class AttributeTests(unittest.TestCase):
    def test_protected_semantic_classes_not_aliased(self):
        protected = {'original-body', 'original-paragraph', 'original-row', 'speaker', 'choice',
                     'original-text', 'reader-paragraph', 'reading-scene', 'rw-quotation'}
        self.assertFalse(protected & set(A.CLASS_ALIASES))
        self.assertEqual(len(A.CLASS_ALIASES), len(set(A.CLASS_ALIASES.values())))
        self.assertTrue(all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', v) for v in A.CLASS_ALIASES.values()))

    def test_original_body_speaker_roles_ids_and_href_stay_static(self):
        value = '<section id="original"><div class="original-row rw-source-row" data-speaker="단항" data-passage="dialogue" data-reading-kind="dialogue"><span class="speaker rw-source-speaker">단항</span><p class="original-body rw-source-body" id="talk-9"><span class="original-paragraph">한글 😀 &amp; &lt;기록&gt;\n둘째 줄</span></p><a data-reading-link href="/starrail-quests/대사/source.html#talk-9">원문 ↗</a></div></section>'
        changed = A.class_attributes(value, A.CLASS_ALIASES)
        self.assertEqual(A.class_attributes(changed, A.REVERSE_CLASSES), value)
        before, after = OriginalProbe(value), OriginalProbe(changed)
        self.assertEqual(before.bodies, after.bodies)
        for old, new in zip(before.attrs, after.attrs):
            self.assertEqual(old[0], new[0])
            self.assertEqual({k: v for k, v in old[1].items() if k != 'class'},
                             {k: v for k, v in new[1].items() if k != 'class'})
            if 'class' in old[1]:
                for protected in ('original-body', 'original-row', 'speaker', 'original-paragraph'):
                    self.assertEqual(protected in old[1]['class'].split(), protected in new[1]['class'].split())
        self.assertIn('>단항</span>', changed)
        self.assertNotIn('__sp(', changed)

    def test_raw_script_json_comments_style_and_prose_unchanged(self):
        parts = ['<!-- <div class="rw-source-row">comment</div> -->',
                 '<script>const template=\'<div class="rw-source-row">\';</script>',
                 '<script type="application/json">{"class":"rw-source-row"}</script>',
                 '<style>.rw-source-row{content:"rw-source-body"}</style>',
                 '<p>rw-source-body, rw-source-row, rw-source-speaker</p>']
        value = ''.join(parts) + '<div class="rw-source-row">정적 내용</div>'
        changed = A.class_attributes(value, A.CLASS_ALIASES)
        for part in parts:
            self.assertIn(part, changed)
        self.assertEqual(A.class_attributes(changed, A.REVERSE_CLASSES), value)

    def test_other_attribute_prose_is_not_a_class_attribute(self):
        value = '<p title="keep class=\'rw-source-body\' intact" data-note="class=\'rw-source-row\'" class="rw-source-body original-body">한글</p>'
        changed = A.class_attributes(value, A.CLASS_ALIASES)
        self.assertIn('title="keep class=\'rw-source-body\' intact"', changed)
        self.assertIn('data-note="class=\'rw-source-row\'"', changed)
        self.assertEqual(A.class_attributes(changed, A.REVERSE_CLASSES), value)

    def test_class_separators_quotes_and_entity_prose_exact_inverse(self):
        value = "<p CLASS = 'original-body\t rw-source-body\n  rw-source-row' id='talk-9'>&lt;p class=&quot;rw-source-body&quot;&gt;</p>"
        changed = A.class_attributes(value, A.CLASS_ALIASES)
        self.assertIn('\t ', changed)
        self.assertIn('\n  ', changed)
        self.assertIn('&lt;p class=&quot;rw-source-body&quot;&gt;', changed)
        self.assertEqual(A.class_attributes(changed, A.REVERSE_CLASSES), value)


class CSSTests(unittest.TestCase):
    def test_selector_dual_forms_preserve_class_specificity_and_inverse(self):
        css = '.rw-source-row[data-reading-kind="choice"] .rw-source-body:hover{color:red}@media(max-width:40rem){.rw-source-body{font-size:1rem}}'
        changed = A.css_aliases(css)
        for name in ('rw-source-row', 'rw-source-body'):
            self.assertIn(':is(.' + name + ',.' + A.CLASS_ALIASES[name] + ')', changed)
        self.assertIn('[data-reading-kind="choice"]', changed)
        self.assertEqual(A.restore_css(changed), css)

    def test_css_comments_strings_url_and_declarations_are_untouched(self):
        css = '/* .rw-source-row { protected } */ .rw-source-body{content:".rw-source-row";--name:.rw-source-speaker;background:url(".rw-source-body.svg");}.rw-source-row{color:red}'
        changed = A.css_aliases(css)
        self.assertIn('/* .rw-source-row { protected } */', changed)
        self.assertIn('content:".rw-source-row"', changed)
        self.assertIn('--name:.rw-source-speaker', changed)
        self.assertIn('url(".rw-source-body.svg")', changed)
        self.assertEqual(A.restore_css(changed), css)

    def test_css_inverse_does_not_rewrite_original_literal_dual_pattern(self):
        literal = ':is(.rw-source-body,.' + A.CLASS_ALIASES['rw-source-body'] + ')'
        css = '/* ' + literal + ' */ .rw-source-row{content:"' + literal + '";}'
        self.assertEqual(A.restore_css(A.css_aliases(css)), css)

    def test_custom_property_blocks_are_declarations_not_selectors(self):
        css = '.rw-source-row{--payload: .rw-source-body { token:1 };color:red}'
        changed = A.css_aliases(css)
        self.assertIn('--payload: .rw-source-body { token:1 }', changed)
        self.assertEqual(A.restore_css(changed), css)

    def test_inline_style_transform_retains_html_and_original_body(self):
        value = '<style media="screen">.rw-source-row{color:red}</style><p class="original-body" id="talk-9">한글</p>'
        changed = A.html_styles(value, A.css_aliases)
        self.assertIn('<p class="original-body" id="talk-9">한글</p>', changed)
        self.assertEqual(A.html_styles(changed, A.restore_css), value)


class SearchTests(unittest.TestCase):
    def test_korean_entities_newlines_utf8_raw_vs_dom_values_and_exact_inverse(self):
        original, changed, loader, records = pooled_fixture()
        self.assertIn('id="record-0"', changed)
        self.assertIn('href="/starrail-quests/원문/0.html#row-1"', changed)
        self.assertIn('<b>원문 제목 0</b>', changed)
        self.assertEqual(A.restore_search(loader + changed, records), original)
        match = A.SEARCH_LOADER.fullmatch(loader)
        values = json.loads(gzip.decompress(base64.b64decode(match[2], validate=True)))
        parser = OriginalProbe(original)
        expected = [attrs['data-search'] for tag, attrs in parser.attrs if tag == 'a']
        expected = [v.replace('\r\n', '\n').replace('\r', '\n') for v in expected]
        self.assertEqual(values, expected)
        self.assertNotIn('&quot;', values[0])
        self.assertIn('"', values[0])

    def test_only_eligible_directory_anchor_transforms(self):
        long = '한국어 검색 텍스트 ' * 100
        excluded = ['<div data-source-record data-search="' + long + '">div</div>',
                    '<input data-record data-search="' + long + '">',
                    '<a data-search="' + long + '">no domain</a>',
                    '<a data-record data-search="tiny">small</a>',
                    '<a data-record class="original-row" data-search="' + long + '">row</a>',
                    '<a data-record data-passage="dialogue" data-search="' + long + '">role</a>',
                    '<a data-record data-reading-kind="choice" data-search="' + long + '">choice</a>',
                    '<!-- <a data-record data-search="' + long + '">comment</a> -->',
                    '<script type="application/json">{"data-search":"' + long + '"}</script>']
        for value in excluded:
            with self.subTest(value=value[:60]):
                changed, loader, count = A.search_attributes(value, {})
                self.assertEqual((changed, loader, count), (value, None, 0))

    def test_reading_template_row_is_protected(self):
        value = '<a data-record data-reading-template="row" data-search="' + '한국어 검색 ' * 100 + '">원문</a>'
        self.assertEqual(A.search_attributes(value, {}), (value, None, 0))

    def test_original_paragraph_descendant_is_protected(self):
        value = '<p class="original-body" id="talk-9"><a data-record data-search="' + '한국어 검색 ' * 100 + '">한국어 본문</a></p>'
        self.assertEqual(A.search_attributes(value, {}), (value, None, 0))

    def test_empty_placeholder_calls_restore_without_materializing_originals(self):
        original, changed, loader, records = pooled_fixture()
        with patch.object(A, '_search_report', records):
            self.assertEqual(A.static_html(loader + changed), original)
        raw = '<script>__sp(999);</script><p class="original-body" id="talk-9">정적 원문</p>'
        self.assertEqual(A.static_html(raw), raw)

    def test_tampered_loader_payload_length_receipt_and_unknown_pool_fail(self):
        original, changed, loader, records = pooled_fixture()
        match = A.SEARCH_LOADER.fullmatch(loader)
        mutants = [loader.replace(match[1], '0' * 64), loader.replace(match[2], 'AAAA'),
                   loader.replace(',' + match[3] + ');', ',' + str(int(match[3]) + 1) + ');')]
        for mutant in mutants:
            with self.subTest(mutant=mutant[:90]):
                with self.assertRaises(ValueError):
                    A.restore_search(mutant + changed, records)
        bad = copy.deepcopy(records)
        bad[match[1]]['rawAttributes'][0] += ' altered'
        with self.assertRaises(ValueError):
            A.restore_search(loader + changed, bad)

    def test_reordered_duplicate_missing_and_out_of_range_slots_fail(self):
        original, changed, loader, records = pooled_fixture()
        mutants = [changed.replace('__ss(0)', '__ss(99)'),
                   changed.replace('__ss(1)', '__ss(0)'),
                   changed.replace('<script>__ss(1);</script>', ''),
                   changed.replace('__ss(0)', '__ss(tmp)').replace('__ss(1)', '__ss(0)').replace('__ss(tmp)', '__ss(1)')]
        for mutant in mutants:
            with self.subTest(mutant=mutant[:80]):
                with self.assertRaises(ValueError):
                    A.restore_search(loader + mutant, records)

    def test_duplicate_loader_and_missing_loader_fail(self):
        original, changed, loader, records = pooled_fixture()
        with self.assertRaises(ValueError):
            A.restore_search(loader + loader + changed, records)
        with self.assertRaises(ValueError):
            A.restore_search(changed, records)


class MemoryFile:
    def __init__(self, name, text):
        self.name, self.raw = name, text.encode('utf8')
        self.suffix = Path(name).suffix
        self.parts = (name,)
        self.writes = 0

    def read_bytes(self):
        return self.raw

    def write_text(self, *args, **kwargs):
        self.writes += 1
        raise AssertionError('Preflight mutated file before rejecting unsafe input')

    def __str__(self):
        return self.name


class MemoryRoot:
    def __init__(self):
        self.mutations = []

    def __truediv__(self, key):
        return self

    def exists(self):
        return False

    def mkdir(self, *args, **kwargs):
        self.mutations.append('mkdir')
        raise AssertionError('Preflight created output before rejecting unsafe input')


class PreflightTests(unittest.TestCase):
    def reject_before_mutation(self, name, content):
        file, root = MemoryFile(name, content), MemoryRoot()
        with patch.object(P, 'text_files', return_value=[file]), patch.object(P, 'total', return_value=len(file.raw)):
            with self.assertRaises(ValueError):
                P.optimize(root, '/starrail-quests', root)
        self.assertEqual(file.writes, 0)
        self.assertEqual(root.mutations, [])

    def test_generated_js_class_consumer_rejected_before_mutation(self):
        self.reject_before_mutation('reader.js', 'document.querySelector(".rw-source-body");')

    def test_inline_client_consumer_rejected_before_mutation(self):
        self.reject_before_mutation('one.html', '<head><script>document.querySelector(".rw-source-row")</script></head>')

    def test_alias_html_collision_rejected_before_mutation(self):
        alias = next(iter(A.REVERSE_CLASSES))
        self.reject_before_mutation('one.html', '<p class="' + alias + '">existing content</p>')

    def test_bare_css_alias_collision_rejected_before_mutation(self):
        alias = next(iter(A.REVERSE_CLASSES))
        self.reject_before_mutation('one.css', '.' + alias + '{color:red}')

    def test_existing_dual_selector_collision_rejected_before_mutation(self):
        name, alias = next(iter(A.CLASS_ALIASES.items()))
        self.reject_before_mutation('one.css', ':is(.' + name + ',.' + alias + '){color:red}')


NODE_PROGRAM = r'''
const fs=require('fs'),vm=require('vm');const input=JSON.parse(fs.readFileSync(0,'utf8'));
function fresh(){const context={TextDecoder,TextEncoder,Uint8Array,atob:s=>Buffer.from(s,'base64').toString('latin1'),document:{write:()=>{},currentScript:null}};context.window=context;vm.createContext(context);vm.runInContext(fs.readFileSync(input.codec,'utf8'),context);vm.runInContext(input.runtime,context);return context;}
function target(attrs={},tag='A'){const values=Object.assign({'data-search':'','data-source-record':''},attrs);return {tagName:tag,getAttribute:k=>Object.prototype.hasOwnProperty.call(values,k)?values[k]:null,hasAttribute:k=>Object.prototype.hasOwnProperty.call(values,k),setAttribute:(k,v)=>values[k]=v,values};}
function pool(ctx,rows){const raw=Buffer.from(JSON.stringify(rows),'utf8');const encoded=require('zlib').gzipSync(raw).toString('base64');ctx.__sl(encoded,raw.length);}
function checkReject(name,call){try{call();return {name,rejected:false};}catch(e){return {name,rejected:true};}}
const ctx=fresh();pool(ctx,input.values);const restored=[];
for(let id=0;id<input.values.length;id++){const node=target();ctx.document.currentScript={parentElement:node};ctx.__ss(id);restored.push(node.values['data-search']);}
const moduleObservation=restored.slice();let tests=[];
tests.push(checkReject('duplicate loader',()=>pool(ctx,input.values)));
for(const id of [-1,0.5,NaN,Infinity,'0',true,999]){const c=fresh();pool(c,input.values);c.document.currentScript={parentElement:target()};tests.push(checkReject('invalid slot '+String(id),()=>c.__ss(id)));}
for(const [label,attrs,tag] of [['nonanchor',{},'DIV'],['missing domain',{'data-source-record':undefined},'A'],['nonempty search',{'data-search':'already present'},'A']]){const c=fresh();pool(c,input.values);let node=target(attrs,tag);if(label==='missing domain')node={tagName:'A',getAttribute:k=>k==='data-search'?'':null,hasAttribute:()=>false,setAttribute:()=>{}};c.document.currentScript={parentElement:node};tests.push(checkReject(label,()=>c.__ss(0)));}
{const c=fresh();pool(c,input.values);c.document.currentScript={parentElement:null};tests.push(checkReject('missing parent',()=>c.__ss(0)));}
{const c=fresh();c.document.currentScript={parentElement:target()};tests.push(checkReject('unloaded pool',()=>c.__ss(0)));}
{const c=fresh();pool(c,input.values);c.document.currentScript={parentElement:target()};c.__ss(0);tests.push(checkReject('same target twice',()=>c.__ss(0)));}
for(const rows of [{not:'array'},[1],[true],[null]]){const c=fresh();tests.push(checkReject('bad values '+JSON.stringify(rows),()=>pool(c,rows)));}
{const c=fresh();const raw=Buffer.from(JSON.stringify(input.values));const payload=require('zlib').gzipSync(raw).toString('base64');tests.push(checkReject('wrong decoded bytes',()=>c.__sl(payload,raw.length+1)));}
{const c=fresh();tests.push(checkReject('corrupt gzip',()=>c.__sl('AAAA',3)));}
{const c=fresh();const raw=Buffer.from([255]);const payload=require('zlib').gzipSync(raw).toString('base64');tests.push(checkReject('invalid UTF8',()=>c.__sl(payload,1)));}
process.stdout.write(JSON.stringify({restored,moduleObservation,tests}));
'''


class RuntimeTests(unittest.TestCase):
    def test_actual_pinned_pako_before_module_restoration_and_error_guards(self):
        node = shutil.which('node.exe') or shutil.which('node')
        self.assertIsNotNone(node, 'Node runtime unavailable')
        codec = Path(P.__file__).resolve().parents[1] / 'public/_publication' / P.CODEC_FILE
        self.assertEqual(hashlib.sha256(codec.read_bytes()).hexdigest(), P.CODEC_SHA256)
        values = ['한국어 😀 " & <기록>\n둘째 줄', '앞\t뒤\n끝 ' + chr(0xa0)]
        run = subprocess.run([node, '-e', NODE_PROGRAM], input=json.dumps({'codec': str(codec), 'runtime': P.pooled_runtime([]), 'values': values}),
                             text=True, encoding='utf8', capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result['restored'], values)
        self.assertEqual(result['moduleObservation'], values)
        self.assertTrue(all(case['rejected'] for case in result['tests']), result['tests'])
        self.assertGreaterEqual(len(result['tests']), 20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    current = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(A.__file__), Path(P.__file__))}
    report = {'schema': 'starrail-publication-attributes-adversarial-tests.v1',
              'status': 'PASS' if result.wasSuccessful() else 'FAIL', 'testsRun': result.testsRun,
              'inputModuleHashes': INPUT_HASHES, 'moduleHashesAfterRun': current,
              'moduleStableDuringRun': current == INPUT_HASHES, 'failures': [{'test': str(test), 'traceback': trace} for test, trace in result.failures],
              'errors': [{'test': str(test), 'traceback': trace} for test, trace in result.errors], 'log': stream.getvalue(),
              'runtimeBoundary': 'Pinned pako and production runtime in Node; mock DOM targets. No browser or site/build writes.'}
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(stream.getvalue(), end='')
    raise SystemExit(0 if result.wasSuccessful() and current == INPUT_HASHES else 1)


if __name__ == '__main__':
    main()
