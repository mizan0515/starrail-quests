"""Independent attribute-only reader for the published DOM contract.

No producer imports, pool expansion, text substitution or script execution.
Original-body checks still consume only literal HTML text and anchors.
"""
from html.parser import HTMLParser as BaseHTMLParser
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

CLASSES = dict(zip(('qzA', 'qzB', 'qzC', 'qzD', 'qzE'),
                   ('original-body', 'original-row', 'original-paragraph', 'original-text', 'source-section')))
ATTRIBUTES = dict(zip(('data-r' + str(i) for i in range(16)), (
    'data-reading-template', 'data-reading-kind', 'data-reading-variant', 'data-reading-link',
    'data-pagefind-weight', 'data-source-link-variant', 'data-speaker', 'data-passage',
    'data-pagefind-ignore', 'data-cva-profile', 'data-context-key', 'data-context-talk',
    'data-deep-talk', 'data-deep-role', 'data-source-kind-value', 'data-directory-search')))
FRAME_NAMES = frozenset(('data-reading-template', 'data-reading-kind', 'data-reading-variant',
                         'data-cva', 'data-cva-profile', 'data-source-link-variant'))
_default = None


class Contract:
    def __init__(self, config, bundles):
        if config.get('classes') != CLASSES or config.get('attributes') != ATTRIBUTES:
            raise ValueError('Unknown published attribute vocabulary')
        frames = config.get('frames')
        if not isinstance(frames, list) or len(frames) > 256:
            raise ValueError('Invalid published frame count')
        for frame in frames:
            names = set()
            if not isinstance(frame, list) or not frame:
                raise ValueError('Empty published frame')
            for pair in frame:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError('Invalid published frame pair')
                name, value = pair
                if name not in FRAME_NAMES or name in names or not (value is None or isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]+', value)):
                    raise ValueError('Frame contains nonconstant or original attributes')
                names.add(name)
        if not isinstance(bundles, dict) or len(bundles) > 128:
            raise ValueError('Invalid published class count')
        for marker, value in bundles.items():
            if not re.fullmatch(r'c(?:0|[1-9][0-9]*)', marker) or not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_ -]+', value):
                raise ValueError('Invalid published class bundle')
        self.frames, self.bundles = frames, bundles

    @classmethod
    def from_publication(cls, root):
        report = json.loads((root / '.codex-work/publication-build-report.json').read_text('utf8'))['rowContract']
        relative = unquote(report['url']).removeprefix('/starrail-quests/')
        if relative == report['url'] or '..' in Path(relative).parts or Path(relative).is_absolute():
            raise ValueError('Invalid published runtime path')
        raw = (root / 'dist' / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != report['sha256'] or len(raw) != report['bytes']:
            raise ValueError('Actual published attribute runtime differs')
        source = raw.decode('utf8')
        config = re.findall(r'const c=(\{[^\n]+\});', source)
        bundles = re.findall(r'const bundles=(\{[^\n]+\});', source)
        if len(config) != 1 or len(bundles) != 1:
            raise ValueError('Ambiguous published attribute runtime')
        return cls(json.loads(config[0]), json.loads(bundles[0]))

    def attributes(self, pairs):
        attrs = dict(pairs)
        if len(attrs) != len(pairs):
            raise ValueError('Duplicate published attributes')
        for name in list(attrs):
            if re.fullmatch(r'c[0-9]+', name):
                if name not in self.bundles or 'class' in attrs or attrs[name] is not None:
                    raise ValueError('Unknown or conflicting published class bundle')
                attrs['class'] = self.bundles[name]
                del attrs[name]
        if 'data-rf' in attrs:
            slot = attrs.pop('data-rf')
            if not isinstance(slot, str) or not re.fullmatch(r'0|[1-9][0-9]*', slot) or int(slot) >= len(self.frames):
                raise ValueError('Unknown published attribute frame')
            for name, value in self.frames[int(slot)]:
                if name in attrs:
                    raise ValueError('Conflicting published frame attribute')
                attrs[name] = value
        for short, name in ATTRIBUTES.items():
            if short in attrs:
                if name in attrs:
                    raise ValueError('Conflicting published attribute alias')
                attrs[name] = attrs.pop(short)
        if 'class' in attrs:
            attrs['class'] = ' '.join(CLASSES.get(name, name) for name in attrs['class'].split())
        return list(attrs.items())


class HTMLParser(BaseHTMLParser):
    def __init__(self, *args, contract=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._attribute_contract = contract
        start, empty = self.handle_starttag, self.handle_startendtag
        self.handle_starttag = lambda tag, attrs: start(tag, self._canonical(attrs))
        # Base startend dispatches to handle_starttag itself; avoid decoding twice.
        if type(self).handle_startendtag is not BaseHTMLParser.handle_startendtag:
            self.handle_startendtag = lambda tag, attrs: empty(tag, self._canonical(attrs))

    def _canonical(self, attrs):
        global _default
        compact = any(name in ATTRIBUTES or name == 'data-rf' or re.fullmatch(r'c[0-9]+', name)
                      or name == 'class' and any(v in CLASSES for v in (value or '').split()) for name, value in attrs)
        if not compact:
            return attrs
        if self._attribute_contract is None:
            if _default is None:
                _default = Contract.from_publication(Path(__file__).resolve().parents[1])
            self._attribute_contract = _default
        return self._attribute_contract.attributes(attrs)
