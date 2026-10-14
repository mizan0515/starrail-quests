import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publication_contract_reader import ATTRIBUTES, CLASSES, Contract, HTMLParser


class Reader(HTMLParser):
    def __init__(self, contract=None):
        super().__init__(convert_charrefs=True, contract=contract)
        self.starts, self.text = [], []

    def handle_starttag(self, tag, attrs):
        self.starts.append((tag, dict(attrs)))

    def handle_data(self, value):
        self.text.append(value)


class AttributeContractTests(unittest.TestCase):
    def setUp(self):
        self.config = {'classes': CLASSES, 'attributes': ATTRIBUTES,
                       'frames': [[['data-reading-template', 'row'], ['data-reading-kind', 'choice']]]}
        self.bundles = {'c0': 'qzB choice', 'c1': 'qzA'}
        self.contract = Contract(self.config, self.bundles)

    def test_literal_original_order_speaker_and_anchor(self):
        page = Reader(self.contract)
        page.feed('<div c0 data-rf="0" data-r12="73" data-r13="NATIVE_CHOICE" data-r6="화자" data-r7="choice"><p c1 id="row-73">첫 선택 &amp; 원문</p></div><p id="next">다음</p>')
        page.close()
        row = page.starts[0][1]
        self.assertEqual(row['data-deep-talk'], '73')
        self.assertEqual(row['data-speaker'], '화자')
        self.assertEqual(row['data-reading-kind'], 'choice')
        self.assertEqual(row['class'], 'original-row choice')
        self.assertEqual(page.starts[1][1], {'class': 'original-body', 'id': 'row-73'})
        self.assertEqual(page.text, ['첫 선택 & 원문', '다음'])

    def test_raw_input_needs_no_report_and_empty_tags_work(self):
        page = Reader()
        page.feed('<p class="original-body" id="literal">원문<br/>끝</p>')
        self.assertIsNone(page._attribute_contract)
        self.assertEqual(page.text, ['원문', '끝'])
        self.assertEqual(page.starts[1], ('br', {}))

    def test_pool_script_cannot_create_original_rows(self):
        page = Reader(self.contract)
        page.feed('<script>__sp("<p class=original-body id=lost>없는 원문</p>")</script><div c0></div>')
        self.assertFalse(any('id' in attrs for _, attrs in page.starts))
        self.assertFalse(any('original-body' in attrs.get('class', '').split() for _, attrs in page.starts))

    def test_reject_unknown_and_conflicting_wire_attributes(self):
        for html in ('<p c99>', '<p c0 class="choice">', '<p c0="x">', '<p data-rf="9">',
                     '<p data-rf="0" data-reading-kind="dialogue">', '<p data-r6="a" data-speaker="b">',
                     '<p c0 c0>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Reader(self.contract).feed(html)

    def test_reject_text_id_or_source_in_shared_frames(self):
        for name in ('id', 'data-speaker', 'data-deep-talk', 'href', 'text'):
            bad = copy.deepcopy(self.config)
            bad['frames'] = [[[name, 'injected']]]
            with self.subTest(name=name), self.assertRaises(ValueError):
                Contract(bad, self.bundles)

    def test_reject_unknown_vocabulary_and_nonclass_bundle(self):
        bad = copy.deepcopy(self.config)
        bad['attributes']['data-r6'] = 'id'
        with self.assertRaises(ValueError):
            Contract(bad, self.bundles)
        for bundles in ({'c0': '<p>원문</p>'}, {'class': 'choice'}):
            with self.assertRaises(ValueError):
                Contract(self.config, bundles)

    def test_frozen_primitive_pin_allows_only_attribute_import(self):
        from verify_public_snapshot_timeline import frozen_primitive_reader_sha, PRIMITIVES_SHA
        raw = (Path(__file__).parent / 'verify_fresh_native_timeline.py').read_bytes()
        self.assertEqual(frozen_primitive_reader_sha(raw), PRIMITIVES_SHA)
        self.assertNotEqual(frozen_primitive_reader_sha(raw + b'\n# changed primitive reader\n'), PRIMITIVES_SHA)
        with self.assertRaises(ValueError):
            frozen_primitive_reader_sha(raw.replace(b'from publication_contract_reader import HTMLParser', b'from html.parser import HTMLParser'))


if __name__ == '__main__':
    unittest.main()
