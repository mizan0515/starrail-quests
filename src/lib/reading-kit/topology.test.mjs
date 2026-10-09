import test from 'node:test';
import assert from 'node:assert/strict';
import {validateTopology, topologyFromRelations, relationStructureGroups, focusRelationLayout, sourceRelationHubs} from './topology.mjs';
import {createReadingKit, escapeHtml, safeHref} from './render.mjs';

const base = () => ({
  id: 'flow', title: '관계',
  nodes: [{id: 'a', name: 'A', url: '/a', layer: 0}, {id: 'b', name: 'B', url: '/b', layer: 1}],
  edges: [{id: 'e', from: 'a', to: 'b', label: '변환', claimId: 'c', reason: '실제 근거', evidence: [{quote: '원문', url: '/source#e'}]}],
});
const kit = () => createReadingKit({evidence: es => es.map(e => `<a href="${safeHref(e.url)}">${escapeHtml(e.quote)}</a>`).join('')});
const withoutModels = html => html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '');
const attribute = (attrs, name) => attrs.match(new RegExp(`(?:^|\\s)${name}="([^"]*)"`))?.[1];

// Read actual generated element boundaries; embedded model text is not visible UI.
function elements(html, tag, matches = () => true) {
  const stack = [], found = [];
  const tokens = new RegExp(`<(/?)${tag}\\b([^>]*)>`, 'g');
  for (const m of html.matchAll(tokens)) {
    if (!m[1]) stack.push({start: m.index, body: m.index + m[0].length, attrs: m[2]});
    else {
      const open = stack.pop();
      assert.ok(open, `Unexpected closing ${tag}`);
      if (matches(open.attrs)) found.push({...open, html: html.slice(open.start, m.index + m[0].length), inner: html.slice(open.body, m.index)});
    }
  }
  assert.equal(stack.length, 0, `Unclosed ${tag}`);
  return found.sort((a, b) => a.start - b.start);
}
const byClass = (html, tag, cls) => elements(html, tag, attrs => (attribute(attrs, 'class') || '').split(/\s+/).includes(cls));
const visibleText = html => html.replace(/<[^>]+>/g, '').replace(/&(?:amp|lt|gt|quot|#39);/g, entity => ({'&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'"}[entity])).replace(/\s+/g, ' ').trim();
const models = html => [...html.matchAll(/<script\b[^>]*data-cva-model\b[^>]*>([\s\S]*?)<\/script>/g)].flatMap(m => JSON.parse(m[1]).modules);
const variants = html => models(html).map(m => m.variant);
const relationCards = html => elements(html, 'article', attrs =>
  attribute(attrs, 'data-cva-item-index') !== undefined && (attribute(attrs, 'class') || '').split(/\s+/).includes('cva-item'));
function endpointIdentity(html) {
  const links = elements(html, 'a', attrs => /\bdata-reading-link\b/.test(attrs));
  const names = links.length ? links : elements(html, 'strong');
  assert.equal(names.length, 1, 'One endpoint name distinct from its kind label');
  return visibleText(names[0].inner);
}

function statements(html) {
  return byClass(withoutModels(html), 'span', 'rw-edge-statement').map(statement => {
    const subject = byClass(statement.inner, 'span', 'rw-edge-subject');
    const predicate = byClass(statement.inner, 'span', 'rw-edge-predicate');
    const object = byClass(statement.inner, 'span', 'rw-edge-object');
    assert.equal(subject.length, 1); assert.equal(predicate.length, 1); assert.equal(object.length, 1);
    assert.ok(subject[0].start < predicate[0].start && predicate[0].start < object[0].start, 'The subject, predicate and object must occur in that order');
    const arrows = byClass(statement.inner, 'span', 'rw-edge-arrow');
    assert.equal(arrows.length, 2);
    for (const arrow of arrows) assert.equal(attribute(arrow.attrs, 'aria-hidden'), 'true');
    return {subject: endpointIdentity(subject[0].inner), predicate: visibleText(predicate[0].inner), object: endpointIdentity(object[0].inner)};
  });
}
const expectedStatements = t => t.edges.map(e => ({subject: t.nodes.find(n => n.id === e.from).name, predicate: e.label, object: t.nodes.find(n => n.id === e.to).name}));
const node = id => ({id, name: id.toUpperCase(), url: '/' + id, layer: 0});
const edge = (id, from, to, label, kind = 'relation') => ({id, from, to, label, kind, claimId: 'claim-' + id, reason: '설명 ' + id, evidence: [{quote: '인용 ' + id, url: '/source#' + id}]});

function assertProofNear(container, t, e) {
  const proofs = byClass(container, 'details', 'rw-relation-proof');
  assert.equal(proofs.length, 1, `One nearby proof for ${e.id}`);
  assert.equal(attribute(proofs[0].attrs, 'id'), `${t.id}-edge-${e.id}`);
  assert.equal(visibleText(elements(proofs[0].inner, 'summary')[0].inner), `원문 근거 ${e.evidence?.length || 0}개`);
  assert.ok(proofs[0].inner.includes(escapeHtml(e.reason || e.text || e.label)));
  for (const source of e.evidence || []) {
    assert.ok(proofs[0].inner.includes(`href="${safeHref(source.url)}"`));
    assert.ok(proofs[0].inner.includes(escapeHtml(source.quote)));
  }
}

test('missing endpoints and unsupported evidence fail', () => {
  const t = base(); t.edges[0].to = 'missing';
  assert.throws(() => validateTopology(t), /edge or evidence/);
  assert.throws(() => validateTopology(base(), () => false), /edge or evidence/);
  const checked = [];
  assert.doesNotThrow(() => validateTopology(base(), id => { checked.push(id); return id === 'c'; }));
  assert.deepEqual(checked, ['c']);
});

test('invalid topology identities, layers and claims are rejected', () => {
  const cases = [
    t => { t.nodes = []; }, t => { t.edges = []; },
    t => { t.nodes.push({...t.nodes[0]}); }, t => { t.nodes[0].name = ''; },
    ...[-1, 0.5, 4, undefined, '1'].map(layer => t => { t.nodes[0].layer = layer; }),
    t => { t.edges.push({...t.edges[0]}); }, t => { t.edges[0].id = ''; },
    t => { t.edges[0].from = 'missing'; }, t => { t.edges[0].label = ''; },
    t => { delete t.edges[0].claimId; }, t => { t.edges[0].kind = 'invented-order'; },
    t => { t.presentation = 'unknown'; }, t => { t.layout = 'unknown'; },
    t => { t.layout = 'cycle'; },
  ];
  for (const mutate of cases) { const t = base(); mutate(t); assert.throws(() => validateTopology(t)); }
});

test('relative scale requires explicit scope', () => {
  const t = base(); t.nodes[1].scale = 'compact';
  assert.throws(() => validateTopology(t), /scope note/);
  t.scaleNote = '상대적인 크기; 수치 미확인';
  assert.doesNotThrow(() => validateTopology(t));
});

test('split and convergence preserve every edge and shared endpoint', () => {
  const endpoint = id => ({id, name: id, url: '/' + id});
  const relations = [['a', 'b'], ['a', 'c'], ['b', 'd'], ['c', 'd']].map(([a, b], i) => ({id: String(i), from: endpoint(a), to: endpoint(b), label: '관계', reasonClaimId: 'c', reason: '근거', evidence: [{quote: '원문 ' + i, url: '/source#' + i}]}));
  const before = JSON.stringify(relations), t = topologyFromRelations(relations), html = kit().topology(t);
  assert.equal(t.nodes.length, 4); assert.equal(t.edges.length, 4);
  assert.equal(t.nodes.find(n => n.id === 'd').layer, 2);
  assert.deepEqual(statements(html), expectedStatements(t));
  assert.deepEqual(variants(html), ['list']);
  assert.equal(JSON.stringify(relations), before);
});

test('actual CVA relation list has named actors, endpoint links and nearby individual evidence', () => {
  const t = base(), html = kit().topology(t), visible = withoutModels(html);
  assert.deepEqual(variants(html), ['list']);
  assert.ok(visible.includes('data-cva')); assert.ok(visible.includes('data-cva-profile="forma"'));
  assert.ok(visible.includes('rw-edge-subject'));
  assert.ok(visible.includes('원문에 명시된 관계'));
  assert.ok(!visible.includes('<table')); assert.ok(!visible.includes('관계·읽는 기준'));
  assert.deepEqual(statements(html), expectedStatements(t));
  const rows = relationCards(visible);
  assert.equal(rows.length, 1); assertProofNear(rows[0].inner, t, t.edges[0]);
  assert.ok(rows[0].inner.includes('data-reading-link href="/a"'));
  assert.ok(rows[0].inner.includes('data-reading-link href="/b"'));
  assert.ok(!visible.includes('<svg')); assert.ok(!visible.includes('<text'));
});

test('Scar incoming actions preserve Jinhsi and Christoforo as subjects', () => {
  for (const [subject, predicate] of [['금희', '체포한다'], ['크리스토포로', '흑조를 통한 이동 방법을 설명한다']]) {
    const t = {id: 'scar-map', title: '스카의 관계', nodes: [{id: 'source', name: subject, url: '/subject', layer: 0}, {id: 'target', name: '스카', url: '/scar', layer: 1, focus: true}], edges: [edge('incoming', 'source', 'target', predicate)]};
    const before = JSON.stringify(t), html = kit().topology(t), visible = withoutModels(html);
    assert.deepEqual(statements(html), [{subject, predicate, object: '스카'}]);
    const band = byClass(visible, 'div', 'rw-relation-band')[0];
    assert.equal(attribute(band.attrs, 'aria-label'), `${subject} → ${predicate} → 스카`);
    assert.equal(attribute(band.attrs, 'data-relation-from'), 'source');
    assert.equal(attribute(band.attrs, 'data-relation-to'), 'target');
    assertProofNear(band.inner, t, t.edges[0]);
    assert.equal(JSON.stringify(t), before);
  }
});

test('split, convergence and return edges preserve all directions without inferring a cycle', () => {
  const t = base(); t.nodes.push({id: 'c', name: 'C', layer: 1});
  t.edges.push(edge('split', 'a', 'c', '나누다'), edge('merge', 'c', 'b', '합류하다'), edge('return', 'b', 'a', '돌아가다', 'return'));
  const html = kit().topology(t), rows = relationCards(withoutModels(html));
  assert.deepEqual(statements(html), expectedStatements(t));
  assert.deepEqual(variants(html), ['list']);
  assert.equal(rows.length, t.edges.length);
  rows.forEach((row, i) => assertProofNear(row.inner, t, t.edges[i]));
});

test('nominal faction membership is preserved without inventing a verb', () => {
  const t = {id: 'membership', title: '소속', nodes: [{id: 'scar', name: '스카', layer: 0}, {id: 'fractsidus', name: '잔성회', layer: 1}], edges: [edge('role', 'scar', 'fractsidus', '잔성회 간부')]};
  const html = kit().topology(t);
  assert.deepEqual(statements(html), [{subject: '스카', predicate: '잔성회 간부', object: '잔성회'}]);
  assert.equal(byClass(withoutModels(html), 'span', 'rw-edge-predicate').length, 1);
  assert.deepEqual(variants(html), ['list']);
});

test('ordinary relations retain each attributed speaker and source beside its own statement', () => {
  const source = {id: 'c', name: '크리스토포로', url: '/people/christoforo.html', kind: '인물'}, focus = {id: 'a', name: '아비디우스', url: '/people/avidius.html', kind: '인물'}, target = {id: 'g', name: '갈브레나', url: '/people/galbrena.html', kind: '인물'};
  const input = [
    {id: 'form', from: source, to: focus, label: '형체를 제공했다고 말한다', reasonClaimId: 'claim-1', claimKind: 'attributed', speaker: '크리스토포로', reason: '크리스토포로의 설명', evidence: [{quote: '원문 1', url: '/quest#scene-42'}]},
    {id: 'wish', from: focus, to: target, label: '힘과 소원을 맡긴다', reasonClaimId: 'claim-2', claimKind: 'attributed', speaker: '아비디우스', reason: '아비디우스의 부탁', evidence: [{quote: '원문 2', url: '/quest#scene-41'}]},
  ];
  const before = JSON.stringify(input), t = topologyFromRelations(input, {id: 'structure', focusId: 'a'}), html = kit().network(input, {id: 'structure', focusId: 'a'}), visible = withoutModels(html);
  assert.deepEqual(statements(html), expectedStatements(t));
  assert.equal(byClass(visible, 'div', 'rw-relation-band').length, 2);
  assert.equal(byClass(visible, 'small', 'rw-node-kind').length, 7);
  for (const kind of byClass(visible, 'small', 'rw-node-kind')) assert.equal(visibleText(kind.inner), '인물');
  assert.equal(byClass(visible, 'span', 'rw-edge-predicate').filter(p => visibleText(p.inner) === '형체를 제공했다고 말한다').length, 1);
  const rows = byClass(visible, 'article', 'sc-card');
  assert.deepEqual(variants(html), ['character-orbit']);
  assert.ok(visible.includes('rw-focus-name')); assert.ok(!visible.includes('중심 인물'));
  rows.forEach((row, i) => {
    assertProofNear(row.inner, t, t.edges[i]);
    assert.ok(row.inner.includes(escapeHtml('발언·기록에 따른 관계 · ' + input[i].speaker)));
    assert.ok(!row.inner.includes(input[1 - i].evidence[0].url));
  });
  assert.ok(!visible.includes('rw-map-incoming')); assert.ok(!visible.includes('rw-map-canvas')); assert.ok(!visible.includes('<svg'));
  assert.equal(JSON.stringify(input), before);
});

test('only an explicit complete sequence chooses the canonical quest-route and ordered items', () => {
  const t = {id: 'journey', title: '확인된 순서', nodes: [node('c'), node('a'), node('b')], edges: [edge('ab', 'a', 'b', '먼저 이동한다', 'sequence'), edge('bc', 'b', 'c', '다음에 도착한다', 'sequence')]};
  const before = JSON.stringify(t), html = kit().topology(t), visible = withoutModels(html);
  assert.deepEqual(variants(html), ['quest-route']);
  assert.ok(visible.includes('data-process-kind="sequence"'));
  assert.equal(byClass(visible,'p','rw-process-return').length,0);
  assert.deepEqual(models(html)[0].props.items.map(item => item.title), ['A', 'B', 'C']);
  assert.equal(models(html)[0].props.relationLabel, '원문에 명시된 과정의 순서');
  assert.deepEqual(statements(html), expectedStatements(t));
  for (const url of ['/a', '/b', '/c']) assert.ok(visible.includes(`data-reading-link href="${url}"`));
  const bands = byClass(visible, 'div', 'rw-structure-edge');
  assert.equal(bands.length, 2); bands.forEach((band, i) => assertProofNear(band.inner, t, t.edges[i]));
  assert.equal(JSON.stringify(t), before);
});

test('branched or incomplete sequence declarations remain a relation ledger', () => {
  const candidates = [
    {id: 'branched', title: '갈라짐', nodes: [node('a'), node('b'), node('c')], edges: [edge('ab', 'a', 'b', '분리', 'sequence'), edge('ac', 'a', 'c', '분리', 'sequence')]},
    {id: 'incomplete', title: '일부 순서', nodes: [node('a'), node('b'), node('c')], edges: [edge('ab', 'a', 'b', '이동', 'sequence')]},
  ];
  for (const t of candidates) {
    const html = kit().topology(t);
    assert.deepEqual(variants(html), ['list']);
    assert.deepEqual(statements(html), expectedStatements(t));
  }
});

test('explicit cycle layout plus a source return edge chooses feedback-ring and preserves the closing proof', () => {
  const t = {id: 'cycle', title: '원문의 순환', layout: 'cycle', note: '원문에서 확인한 귀환', nodes: [node('a'), node('b'), node('c')], edges: [edge('ab', 'a', 'b', '시작한다', 'sequence'), edge('bc', 'b', 'c', '이어진다', 'sequence'), edge('ca', 'c', 'a', '처음으로 돌아온다', 'return')]};
  const html = kit().topology(t), visible = withoutModels(html);
  assert.deepEqual(variants(html), ['feedback-ring']);
  assert.deepEqual(models(html)[0].props.items.map(item => item.title), ['A', 'B', 'C']);
  assert.equal(models(html)[0].props.relationLabel, '원문에 설명된 순환 · 각 연결의 발언 주체와 근거');
  // Each cycle stage shows its outgoing action; the original C → A return closes it.
  assert.deepEqual(statements(html), expectedStatements(t));
  assert.ok(visible.includes('data-process-kind="cycle"'));
  assert.equal(visibleText(byClass(visible,'p','rw-process-return')[0].inner),'↶ C → 처음으로 돌아온다 → A');
  const bands = byClass(visible, 'div', 'rw-structure-edge');
  assert.equal(bands.length, 3);
  t.edges.forEach((e, i) => assertProofNear(bands[i].inner, t, e));
});

test('return edges and mutually directed relations alone do not declare a cycle', () => {
  const t = {id: 'return-only', title: '귀환 관계', nodes: [node('a'), node('b')], edges: [edge('ab', 'a', 'b', '보낸다'), edge('ba', 'b', 'a', '돌려준다', 'return')]};
  const html = kit().topology(t);
  assert.deepEqual(variants(html), ['list']);
  assert.deepEqual(statements(html), expectedStatements(t));
  const relations = [
    {id: 'ab', from: node('a'), to: node('b'), label: '영향을 준다', reasonClaimId: 'ab', reason: 'A의 기록', evidence: [{quote: 'A 원문', url: '/a#source'}]},
    {id: 'ba', from: node('b'), to: node('a'), label: '영향을 준다', reasonClaimId: 'ba', reason: 'B의 기록', evidence: [{quote: 'B 원문', url: '/b#source'}]},
  ];
  const derived = topologyFromRelations(relations, {focusId: 'a'});
  assert.equal(derived.layout, undefined); assert.ok(derived.edges.every(e => e.kind === 'relation'));
  const mutual = kit().topology(derived);
  assert.deepEqual(variants(mutual), ['character-orbit']);
  assert.deepEqual(statements(mutual), expectedStatements(derived));
});

test('one explicit cycle with direct incoming sources preserves the core and each feeder proof once', () => {
  const t = {id: 'fed-cycle', title: '원문의 순환과 유입', layout: 'cycle',
    nodes: ['x', 'c', 'y', 'b', 'a'].map(node),
    edges: [edge('xa', 'x', 'a', '첫 기록이 유입된다'),
      edge('ab', 'a', 'b', '변환한다', 'sequence'),
      edge('yb', 'y', 'b', '두 번째 기록이 유입된다'),
      edge('bc', 'b', 'c', '이어진다', 'sequence'),
      edge('ca', 'c', 'a', '원래 상태로 돌아간다', 'return')]};
  const before = JSON.stringify(t), html = kit().topology(t), visible = withoutModels(html);
  assert.deepEqual(variants(html), ['feedback-ring', 'list']);
  assert.deepEqual(models(html)[0].props.items.map(item => item.title), ['A', 'B', 'C']);
  const core = [t.edges[1], t.edges[3], t.edges[4]], feeders = [t.edges[0], t.edges[2]];
  assert.deepEqual(statements(html), [...core, ...feeders].map(e => ({
    subject: t.nodes.find(n => n.id === e.from).name, predicate: e.label,
    object: t.nodes.find(n => n.id === e.to).name})));
  const bands = byClass(visible, 'div', 'rw-structure-edge');
  assert.equal(bands.length, core.length);
  bands.forEach((band, i) => assertProofNear(band.inner, t, core[i]));
  const rows = relationCards(visible);
  assert.equal(rows.length, feeders.length);
  rows.forEach((row, i) => assertProofNear(row.inner, t, feeders[i]));
  const proofs = byClass(visible, 'details', 'rw-relation-proof');
  assert.equal(proofs.length, t.edges.length);
  assert.deepEqual(proofs.map(p => attribute(p.attrs, 'id')).sort(),
    t.edges.map(e => `${t.id}-edge-${e.id}`).sort());
  for (const n of t.nodes) assert.ok(visible.includes(`data-reading-link href="${n.url}"`));
  assert.equal(JSON.stringify(t), before);
});

test('cycle declarations with an outgoing fork, unrelated component or two return edges retain all ledger evidence', () => {
  const cycle = () => ({id: 'bounded-cycle', title: '관계 전체', layout: 'cycle',
    nodes: ['a', 'b', 'c'].map(node), edges: [edge('ab', 'a', 'b', '시작', 'sequence'),
      edge('bc', 'b', 'c', '진행', 'sequence'), edge('ca', 'c', 'a', '귀환', 'return')]});
  const cases = [
    t => { t.nodes.push(node('x')); t.edges.push(edge('bx', 'b', 'x', '외부로 갈라진다')); },
    t => { t.nodes.push(node('x'), node('y')); t.edges.push(edge('xy', 'x', 'y', '별개 기록')); },
    t => { t.edges[0].kind = 'return'; },
  ];
  for (const mutate of cases) {
    const t = cycle(); mutate(t);
    const before = JSON.stringify(t), html = kit().topology(t), visible = withoutModels(html);
    assert.deepEqual(variants(html), ['list']);
    assert.deepEqual(statements(html), expectedStatements(t));
    const rows = relationCards(visible);
    assert.equal(rows.length, t.edges.length);
    rows.forEach((row, i) => assertProofNear(row.inner, t, t.edges[i]));
    assert.equal(byClass(visible, 'details', 'rw-relation-proof').length, t.edges.length);
    assert.equal(JSON.stringify(t), before);
  }
});

test('a disconnected cycle declaration keeps every relation in a ledger', () => {
  const t = {id: 'disconnected', title: '두 관계', layout: 'cycle', nodes: ['a', 'b', 'c', 'd'].map(node), edges: [edge('ab', 'a', 'b', '이동'), edge('ba', 'b', 'a', '귀환', 'return'), edge('cd', 'c', 'd', '이동'), edge('dc', 'd', 'c', '귀환', 'return')]};
  const html = kit().topology(t);
  assert.deepEqual(variants(html), ['list']);
  assert.deepEqual(statements(html), expectedStatements(t));
});

test('editorial reading connections retain sources without an actor-action diagram or authored speaker', () => {
  const relation = {id: 'reading', from: {id: 'borisin', name: '보리인과 여우족', url: '/borisin'}, to: {id: 'paths', name: '에이언즈·운명의 길·파벌', url: '/paths'}, label: '단륜사의 신앙과 비살생', reasonClaimId: 'reason', claimKind: 'inference', speaker: '군 교재', reason: '두 기록을 함께 읽는 이유', evidence: [{quote: '보존된 인용', url: '/book#row'}]};
  const html = kit().network([relation], {id: 'structure'}), visible = withoutModels(html);
  assert.ok(visible.includes('함께 읽을 기록')); assert.ok(visible.includes('rw-reading-connection'));
  assert.ok(visible.includes('편집자의 연결 · 보리인과 여우족에서 이어 읽기'));
  assert.ok(!visible.includes('군 교재')); assert.deepEqual(statements(html), []);
  assert.deepEqual(variants(html), ['grid']);
  assert.ok(!visible.includes('rw-relation-band')); assert.ok(!visible.includes('rw-relation-direction')); assert.ok(!visible.includes('rw-relation-band-line'));
  assert.ok(visible.includes('data-reading-link href="/paths"'));
  const editorial = byClass(visible, 'div', 'rw-reading-connection')[0], proof = byClass(editorial.inner, 'details', 'rw-relation-proof')[0];
  assert.ok(!editorial.inner.includes('rw-connection-origin'), 'The reading origin is already in the attribution label');
  assert.equal(attribute(proof.attrs, 'id'), 'structure-edge-reading');
  assert.ok(proof.inner.includes('연결의 원문 근거 1개')); assert.ok(proof.inner.includes('두 기록을 함께 읽는 이유'));
  assert.ok(proof.inner.includes('href="/book#row"')); assert.ok(proof.inner.includes('보존된 인용'));
});

test('an editorial edge interrupts an otherwise declared action sequence', () => {
  const t = {id: 'mixed', title: '원문과 연결', nodes: [node('a'), node('b'), node('c')], edges: [edge('ab', 'a', 'b', '이동', 'sequence'), {...edge('bc', 'b', 'c', '함께 읽기', 'sequence'), claimKind: 'inference'}]};
  const html = kit().topology(t), visible = withoutModels(html);
  assert.deepEqual(variants(html), ['list', 'grid']);
  assert.deepEqual(statements(html), [expectedStatements(t)[0]]);
  assert.equal(byClass(visible, 'div', 'rw-relation-band').length, 1);
  assert.equal(byClass(visible, 'div', 'rw-reading-connection').length, 1);
  assert.ok(visible.includes('id="mixed-edge-ab"')); assert.ok(visible.includes('id="mixed-edge-bc"'));
});

test('source text and endpoint identity escape safely without changing the input', () => {
  const t = base(); t.nodes[0].name = '<주체 & 이름>'; t.nodes[1].name = '대상 "인물"';
  t.edges[0].label = '말한다 <직접 인용>'; t.edges[0].reason = '<b>원문의 태그</b> & 설명'; t.edges[0].evidence[0].quote = '<script>원문에 있는 문자열</script>';
  const before = JSON.stringify(t), html = kit().topology(t), visible = withoutModels(html);
  assert.deepEqual(statements(html), expectedStatements(t));
  assert.ok(visible.includes('&lt;b&gt;원문의 태그&lt;/b&gt; &amp; 설명'));
  assert.ok(visible.includes('&lt;script&gt;원문에 있는 문자열&lt;/script&gt;'));
  assert.ok(!visible.includes('<script>원문')); assert.equal(JSON.stringify(t), before);
});

test('relation batches preserve all 25 statements and source proofs within the CVA item limit', () => {
  const t = {id: 'many', title: '모든 관계', nodes: [node('a'), node('b')], edges: Array.from({length: 25}, (_, i) => edge('e' + i, i % 2 ? 'b' : 'a', i % 2 ? 'a' : 'b', '관계 ' + i))};
  const html = kit().topology(t), visible = withoutModels(html), modules = models(html);
  assert.deepEqual(variants(html), ['list', 'list']);
  assert.deepEqual(modules.map(m => m.props.items.length), [24, 1]);
  assert.deepEqual(statements(html), expectedStatements(t));
  const rows = relationCards(visible);
  assert.equal(rows.length, 25); rows.forEach((row, i) => assertProofNear(row.inner, t, t.edges[i]));
  assert.equal(new Set(byClass(visible, 'details', 'rw-relation-proof').map(p => attribute(p.attrs, 'id'))).size, 25);
});

test('attributed source speakers stay visible in proof and empty networks stay empty', () => {
  const t = base(); t.edges[0].claimKind = 'attributed'; t.edges[0].speaker = '파수인';
  const html = kit().topology(t), proof = byClass(withoutModels(html), 'details', 'rw-relation-proof')[0];
  assert.ok(proof.inner.includes('발언·기록에 따른 관계 · 파수인'));
  assert.equal(topologyFromRelations([]), null); assert.equal(kit().network([]), '');
});

test('reviewed membership is nested under its actual group and preserves the original direction and proof', () => {
  const t = {id:'affiliation',title:'소속',nodes:[node('kafka'),node('hunters')],edges:[{...edge('member','kafka','hunters','소속'),structure:'membership'}]};
  const html=kit().topology(t),visible=withoutModels(html);
  assert.deepEqual(variants(html),['nested-world']);
  assert.deepEqual(statements(html),expectedStatements(t));
  assert.deepEqual(relationStructureGroups(t.edges).map(g=>g.parent),['hunters']);
  assert.ok(visible.indexOf('HUNTERS')<visible.indexOf('KAFKA'));
  assert.equal(byClass(visible,'details','rw-relation-proof').length,1);
  assertProofNear(byClass(visible,'div','rw-relation-band')[0].inner,t,t.edges[0]);
});

test('containment and membership require reviewed source metadata, and ordinary location or reading links do not acquire it', () => {
  const t=base();t.edges[0].structure='containment';
  const html=kit().topology(t);
  assert.deepEqual(variants(html),['nested-world']);assert.deepEqual(statements(html),expectedStatements(t));
  assert.equal(relationStructureGroups(t.edges)[0].parent,'a');
  for(const invalid of ['location','birthplace','invented']){t.edges[0].structure=invalid;assert.throws(()=>validateTopology(t));}
  t.edges[0].structure='membership';t.edges[0].claimKind='inference';assert.throws(()=>validateTopology(t));
  t.edges[0].claimKind='explicit';t.edges[0].kind='sequence';assert.throws(()=>validateTopology(t));
  assert.deepEqual(relationStructureGroups([{...edge('place','a','b','출신 지역')}]),[]);
});

test('large source scopes keep all members, directions and proofs across the CVA item boundary', () => {
  for (const structure of ['membership','containment']) {
    const t={id:'large-'+structure,title:'전체 구성',nodes:[node('group'),...Array.from({length:25},(_,i)=>node('member-'+i))],edges:Array.from({length:25},(_,i)=>({...edge('e'+i,structure==='membership'?'member-'+i:'group',structure==='membership'?'group':'member-'+i,'역할 '+i),structure}))};
    const before=JSON.stringify(t),html=kit().topology(t),visible=withoutModels(html);
    assert.deepEqual(variants(html),['nested-world','nested-world']);
    assert.deepEqual(models(html).map(m=>m.props.items.length),[24,1]);
    assert.deepEqual(statements(html),expectedStatements(t));
    const proofs=byClass(visible,'details','rw-relation-proof');
    assert.equal(proofs.length,25);assert.equal(new Set(proofs.map(p=>attribute(p.attrs,'id'))).size,25);
    byClass(visible,'div','rw-relation-band').forEach((row,i)=>assertProofNear(row.inner,t,t.edges[i]));
    assert.equal(JSON.stringify(t),before);
  }
});

test('source actions around a declared focus use directional orbit or hub without sequence numbers', () => {
  const incoming=edge('in','a','b','설명한다'),outgoing=edge('out','b','c','부탁한다');
  const t={id:'focus-shape',title:'인물의 관계',nodes:[node('a'),{...node('b'),focus:true},node('c')],edges:[incoming,outgoing]};
  assert.equal(focusRelationLayout(t.nodes,t.edges).variant,'character-orbit');
  const html=kit().topology(t),visible=withoutModels(html);
  assert.deepEqual(statements(html),expectedStatements(t));
  assert.ok(visible.includes('data-relation-direction="incoming"'));assert.ok(visible.includes('data-relation-direction="outgoing"'));
  assert.ok(!visible.includes('sc-number'));assert.ok(!visible.includes('sc-stage-result'));
  t.edges=[edge('one','b','a','돕는다'),edge('two','b','c','방문한다')];
  const hub=kit().topology(t);
  assert.deepEqual(variants(hub),['hub']);assert.deepEqual(statements(hub),expectedStatements(t));
  assert.equal(byClass(withoutModels(hub),'details','rw-relation-proof').length,2);
  t.edges.push(edge('unrelated','a','c','별개 행동'));assert.equal(focusRelationLayout(t.nodes,t.edges),null);
});

test('source trees use direct hubs without adding a join, containment, cycle or temporal order', () => {
 const t={id:'formation',title:'기억의 형성',nodes:['material','field','bubble','meme'].map(node),edges:[edge('field','material','field','응집하여 공간을 형성한다'),edge('bubble','material','bubble','집합체를 이룬다'),edge('meme','field','meme','잠재의식 조각이 쌓여 형성한다')]};
 const before=JSON.stringify(t),html=kit().topology(t),visible=withoutModels(html);
 assert.deepEqual(variants(html),['hub','hub']);assert.deepEqual(statements(html),expectedStatements(t));
 assert.ok(visible.includes('data-hub-shape="fan"'));assert.ok(visible.includes('data-hub-shape="pair"'));
 assert.equal(byClass(visible,'details','rw-relation-proof').length,3);
 assert.ok(!visible.includes('sc-number'));assert.ok(!visible.includes('sc-common-scope'));assert.equal(JSON.stringify(t),before);
 assert.deepEqual(sourceRelationHubs(t.nodes,t.edges).map(g=>g.parent),['material','field']);
 const focused=structuredClone(t);focused.nodes.find(n=>n.id==='material').focus=true;
 assert.deepEqual(sourceRelationHubs(focused.nodes,focused.edges).map(g=>g.parent),['material','field']);
 for(const change of [x=>x.edges.push(edge('join','bubble','meme','별도 연결')),x=>x.edges.push(edge('return','meme','material','귀환')),x=>x.edges[0].claimKind='inference',x=>x.edges[0].kind='sequence',x=>x.nodes.find(n=>n.id==='field').focus=true]){const x=structuredClone(t);change(x);assert.equal(sourceRelationHubs(x.nodes,x.edges),null);}
});

test('large direct hubs reserve one item for the actual center and retain every branch proof', () => {
 const t={id:'large-tree',title:'관계 전체',nodes:[node('root'),...Array.from({length:25},(_,i)=>node('child-'+i)),node('leaf')],edges:[...Array.from({length:25},(_,i)=>edge('direct-'+i,'root','child-'+i,'직접 관계 '+i)),edge('branch','child-0','leaf','별도 직접 관계')]};
 const before=JSON.stringify(t),html=kit().topology(t),visible=withoutModels(html);
 assert.deepEqual(models(html).map(m=>m.props.items.length),[24,3,2]);
 assert.deepEqual(statements(html),expectedStatements(t));
 assert.equal(byClass(visible,'details','rw-relation-proof').length,26);
 assert.equal(new Set(byClass(visible,'details','rw-relation-proof').map(p=>attribute(p.attrs,'id'))).size,26);
 assert.equal(JSON.stringify(t),before);
});

test('three or more direct targets use one side branch with every original statement and proof', () => {
 for(const direction of ['incoming','outgoing']){
  const t={id:'side-branch-'+direction,title:'관계',nodes:[{...node('focus'),focus:true},...['a','b','c'].map(node)],edges:['a','b','c'].map((id,i)=>edge('e'+i,direction==='incoming'?id:'focus',direction==='incoming'?'focus':id,'원문 관계 '+i))};
  const before=JSON.stringify(t),html=kit().topology(t),visible=withoutModels(html);
  assert.deepEqual(variants(html),['hub']);
  assert.ok(visible.includes('data-hub-shape="branch"'));
  assert.ok(visible.includes('--rw-hub-rows:3'));
  assert.deepEqual(statements(html),expectedStatements(t));
  assert.equal(byClass(visible,'details','rw-relation-proof').length,3);
  byClass(visible,'div','rw-relation-band').forEach((row,i)=>assertProofNear(row.inner,t,t.edges[i]));
  assert.equal(JSON.stringify(t),before);
 }
});
