/* The page renderer uses validated models and original Forma engines, never raw user HTML. */
(function (global) {
  'use strict';

  function dependencies() {
    if (!global.CVA_COMPONENTS || !global.CVA_MODULES) throw new Error('CVA 컴포넌트와 모듈 정의를 먼저 불러와 주세요.');
    return global.CVA_COMPONENTS;
  }
  function empty() { return '<p class="cva-empty">아직 항목이 없습니다. 내용을 추가하면 여기에 표시됩니다.</p>'; }
  function originalGraphLayout(html) {
    // Read only the numeric grid positions emitted by the known original engine.
    // User text is already escaped; no text, node, relation or engine is rebuilt.
    let columns = 1;
    const opening = /<div class="wf-node-wrap" style="--node-col:(\d+);--node-row:(\d+)">/g;
    const sizes = new Map();
    const positions = html.matchAll(opening);
    for (const position of positions) {
      const column = Number(position[1]);
      const row = Number(position[2]);
      if (Number.isInteger(column) && column >= 1 && column <= 200 && Number.isInteger(row) && row >= 1 && row <= 200) {
        columns = Math.max(columns, row);
        sizes.set(column, (sizes.get(column) || 0) + 1);
      }
    }
    return { columns, html: html.replace(opening, (markup, column) => {
      const size = sizes.get(Number(column));
      return size >= 1 && size <= 200 ? markup.replace(' style=', ' data-cva-rank-size="' + size + '" style=') : markup;
    }) };
  }
  function content(block, context) {
    const C = dependencies(), e = C.escape, p = block.props;
    const head = body => C.heading({ eyebrow: p.eyebrow, title: p.title, body: body === undefined ? p.body : body, level: block.type === 'hero' && context.index === 0 ? 1 : 2 });
    const list = render => p.items.length ? p.items.map(render).join('') : empty();
    switch (block.type) {
      case 'scene-composition':
        if (!global.CVA_SCENE_RENDERER) throw new Error('장면 중심 표현 엔진을 먼저 불러와 주세요.');
        return global.CVA_SCENE_RENDERER.render(block, context);
      case 'hero': return '<div class="cva-hero-copy">' + head() + (p.actionLabel ? '<div class="cva-actions">' + C.button(p.actionLabel, { target: context.nextId }) + '</div>' : '') + '</div>' + C.media(p.image, { caption: p.caption });
      case 'text': return head('') + (p.body ? '<div class="cva-body">' + e(p.body) + '</div>' : '');
      case 'metrics': return head() + '<div class="cva-items">' + list(entry => C.panel(entry)) + '</div>';
      case 'cards': return head() + '<div class="cva-items">' + list(entry => C.panel(entry)) + '</div>';
      case 'split': return '<div class="cva-split-layout"><div class="cva-split-copy">' + head() + '</div>' + C.media(p.image, { caption: p.caption }) + '</div>';
      case 'timeline': return head() + (p.items.length ? '<ol class="cva-items cva-timeline-list">' + list((entry, index) => '<li class="cva-step">' +
        '<span class="cva-axis" aria-hidden="true"></span><div class="cva-step-copy"><span class="cva-step-number" aria-label="읽는 순서 ' + (index + 1) + '">' + String(index + 1).padStart(2, '0') + '</span>' + C.badge(entry.label) +
        '<h3 class="cva-item-title">' + e(entry.title) + '</h3>' + (entry.body ? '<p class="cva-item-body">' + e(entry.body) + '</p>' : '') +
        (entry.value !== undefined && entry.value !== '' ? '<p class="cva-value">' + e(entry.value) + '</p>' : '') + '</div>' + C.media(entry.image) + '</li>') + '</ol>' : empty());
      case 'flow': return head() + '<ol class="cva-items cva-flow-list">' + list((entry, index) => {
        const fork = block.variant === 'fork-join', hub = block.variant === 'hub';
        const role = fork ? index === 0 ? '시작' : index === 3 ? '합류 뒤 결과' : '경로 ' + (index === 1 ? 'A' : 'B') : hub ? index === 0 ? '중심' : '연결 대상' : '순서 ' + (index + 1);
        const part = fork ? index === 0 ? 'start' : index === 3 ? 'end' : 'path' : hub && index === 0 ? 'start' : 'path';
        return '<li class="cva-node cva-node-' + part + '"><p class="cva-flow-role">' + role + '</p>' + C.badge(entry.label) +
          '<h3 class="cva-item-title">' + e(entry.title) + '</h3>' + (entry.body ? '<p class="cva-item-body">' + e(entry.body) + '</p>' : '') + C.media(entry.image) +
          (index > 0 && p.relationLabel ? '<p class="cva-flow-relation">' + e(p.relationLabel) + '</p>' : '') + '</li>';
      }) + '</ol>';
      case 'comparison': {
        if (!p.items.length) return head() + empty();
        if (block.variant === 'columns') return head() + '<div class="cva-comparison cva-items">' + list(entry => C.panel(entry)) + '</div>';
        const rows = [['명시한 라벨', 'label'], ['명시한 값', 'value'], ['설명', 'body']];
        return head() + '<div class="cva-comparison"><table class="cva-comparison-table"><caption>' + e(p.title || '동일한 기준으로 비교') + '</caption><thead><tr><th scope="col">비교 항목</th>' +
          p.items.map(entry => '<th scope="col">' + e(entry.title) + '</th>').join('') + '</tr></thead><tbody>' + rows.map(([label, key]) => '<tr><th scope="row">' + label + '</th>' +
            p.items.map(entry => '<td>' + e(entry[key] === undefined ? '' : entry[key]) + '</td>').join('') + '</tr>').join('') + '</tbody></table>' +
          (p.items.some(entry => entry.image) ? '<div class="cva-items cva-comparison-media">' + p.items.map(entry => C.media(entry.image, { caption: entry.title })).join('') + '</div>' : '') + '</div>';
      }
      case 'gallery': return head() + '<div class="cva-items">' + list(entry => entry.image ? C.media(entry.image, { className: 'cva-item', title: entry.title, body: entry.body, label: entry.label }) : C.panel(entry)) + '</div>' + (p.caption ? '<p class="cva-caption">' + e(p.caption) + '</p>' : '');
      case 'quote': return head('') + C.quote(p.body, p.cite);
      case 'evidence': return '<div class="cva-evidence-layout"><div class="cva-evidence-copy">' + head() +
        (p.cite ? '<p class="cva-cite">' + e(p.cite) + '</p>' : '') + '</div>' + C.media(p.image, { caption: p.caption }) + '</div>';
      case 'accordion': return head() + '<div class="cva-items">' + list((entry, index) => '<details class="cva-item"' + (index === 0 ? ' open' : '') + '><summary class="cva-item-title">' + e(entry.title) + '</summary>' +
        '<div class="cva-item-copy">' + C.badge(entry.label) + (entry.body ? '<p class="cva-item-body">' + e(entry.body) + '</p>' : '') + C.media(entry.image) + '</div></details>') + '</div>';
      case 'cta': return head() + (p.actionLabel ? '<div class="cva-actions">' + C.button(p.actionLabel, { target: context.firstId }) + '</div>' : '');
      case 'forma-pattern': {
        if (!global.FW_CONTENT || !global.FormaWeb || !global.FW_CATALOG) throw new Error('Forma 원본 표현 엔진을 먼저 불러와 주세요.');
        const pattern = global.FW_CATALOG.patterns.find(entry => entry.id === p.patternId);
        if (!pattern) throw new Error('원본 카탈로그에 있는 표현 ID가 필요합니다.');
        const section = global.CVA_MODULES.sectionFor(block);
        // Only the rendered namespace changes; the stored model remains unchanged. Item IDs and
        // explicit relation arrays remain the author's original data; duplicate
        // modules therefore keep working without sharing fragment targets.
        section.id = 'cva-original-' + block.id;
        const html = global.FormaWeb.renderSection(section, context.index, false);
        const layout = originalGraphLayout(html);
        // The original renderer uses toolkit-root assets; this canvas is one directory below it.
        return '<div class="cva-forma-render fw" data-orientation="' + (block.orientation || 'original') + '" style="--cva-vertical-columns:' + layout.columns +
          '" data-pattern-id="' + e(pattern.id) + '" data-original-engine="' + e(pattern.engine) + '" data-original-variant="' + e(pattern.variant) + '">' + layout.html.replace(/\bsrc="assets\//g, 'src="../assets/') + '</div>';
      }
      default: throw new Error('등록된 모듈 렌더러가 없습니다.');
    }
  }
  function blockHTML(block, context) {
    const C = dependencies(), e = C.escape;
    const selected = context.selectedId === block.id;
    return '<section id="' + e(block.id) + '" class="cva-module cva-module-' + block.type + (selected ? ' cva-module-selected' : '') +
      '" data-block-id="' + e(block.id) + '" data-variant="' + e(block.variant) + '" data-orientation="' + (block.orientation || 'original') + '"' + (context.editable ? ' data-editable="true"' : '') +
      (selected ? ' data-selected="true"' : '') + '>' + content(block, context) + '</section>';
  }
  function renderDocument(documentModel, { editable = false, selectedId = null } = {}) {
    dependencies();
    const doc = global.CVA_MODULES.normalizeDocument(documentModel);
    const e = global.CVA_COMPONENTS.escape;
    const firstId = doc.modules[0] ? doc.modules[0].id : 'cva-page-top';
    const html = doc.modules.map((block, index) => blockHTML(block, { index, editable: Boolean(editable), selectedId, firstId, nextId: doc.modules[index + 1] ? doc.modules[index + 1].id : firstId })).join('');
    return '<article id="cva-page-top" class="cva-page" data-cva data-cva-profile="' + doc.profile + '" aria-label="' + e(doc.title) + '"><div class="cva-module-list">' +
      (html || global.CVA_COMPONENTS.heading({ title: doc.title, body: doc.description, level: 1 }) + empty()) + '</div><span id="cva-page-end" class="cva-page-end"></span></article>';
  }
  function renderBlock(block, { profile = 'forma', editable = false, selectedId = null, nextId = 'cva-page-top', firstId = 'cva-page-top' } = {}) {
    dependencies();
    const doc = global.CVA_MODULES.normalizeDocument({ schema: 'cva.page.v2', title: '', description: '', profile, modules: [block] });
    return blockHTML(doc.modules[0], { index: 0, editable: Boolean(editable), selectedId, nextId, firstId });
  }

  global.CVA_RENDERER = { version: '2.2', renderDocument, renderBlock };
})(window);
