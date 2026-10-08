/* Authored scene compositions. Text stays text, and native links/details work offline. */
(function (global) {
  'use strict';
  const variants = [
    'chapter-cover', 'scene-rail', 'branch-stage', 'merge-stage', 'character-orbit', 'relationship-ledger',
    'item-dossier', 'loadout-slots', 'crafting-recipe', 'nested-world', 'quest-route', 'parallel-lanes',
    'phase-ladder', 'feedback-ring', 'before-after', 'evidence-focus', 'story-montage', 'world-atlas',
    'spotlight-index', 'editorial-intro'
  ];

  function render(block, context = {}) {
    if (!global.CVA_COMPONENTS) throw new Error('CVA 공통 컴포넌트를 먼저 불러와 주세요.');
    if (!block || block.type !== 'scene-composition' || !variants.includes(block.variant)) throw new Error('등록된 장면 구도가 필요합니다.');
    if (typeof block.id !== 'string' || !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(block.id)) throw new Error('장면 모듈 ID가 올바르지 않습니다.');
    const C = global.CVA_COMPONENTS, e = C.escape, p = block.props || {}, items = p.items;
    if (!Array.isArray(items) || items.length > 24) throw new Error('장면 항목은 24개 이하의 목록이어야 합니다.');
    const orientation = block.orientation || 'original';
    if (!['original', 'vertical', 'horizontal'].includes(orientation)) throw new Error('장면을 읽는 방향이 올바르지 않습니다.');
    const id = index => block.id + '-scene-' + index;
    const ordinal = index => String(index + 1).padStart(2, '0');
    const value = entry => entry.value !== undefined && entry.value !== null && entry.value !== '' ? '<p class="sc-value">' + e(entry.value) + '</p>' : '';
    const head = () => C.heading({ eyebrow: p.eyebrow || '', title: p.title || '', body: p.body || '', level: context.index === 0 ? 1 : 2 });
    const leadMedia = () => p.image ? '<div class="sc-lead-media">' + C.media(p.image) + '</div>' : '';
    const empty = () => '<p class="sc-empty">항목을 추가하면 이 구도에서 내용을 이어 읽을 수 있습니다.</p>';
    const copy = (entry, index, { title = true, number = false, role = '', disclose = false } = {}) => '<div class="sc-copy">' +
      (number ? '<span class="sc-number" aria-label="읽는 순서 ' + (index + 1) + '">' + ordinal(index) + '</span>' : '') +
      (role && role !== entry.label ? '<p class="sc-role">' + e(role) + '</p>' : '') + C.badge(entry.label || '') +
      (title ? '<h3 class="sc-item-title">' + e(entry.title || '') + '</h3>' : '') + value(entry) +
      (entry.body ? (disclose ? '<details class="sc-reading-detail"><summary>장면 설명 읽기</summary><p class="sc-item-body">' + e(entry.body) + '</p></details>' : '<p class="sc-item-body">' + e(entry.body) + '</p>') : '') + '</div>';
    const media = entry => entry.image ? '<div class="sc-node-media">' + C.media(entry.image) + '</div>' : '';
    const card = (entry, index, options = {}) => '<article class="sc-card" id="' + e(id(index)) + '">' + media(entry) + copy(entry, index, options) + '</article>';
    const collection = (className = '', options = {}) => items.length ? '<ol class="sc-collection ' + className + '">' +
      items.map((entry, index) => '<li>' + card(entry, index, options) + '</li>').join('') + '</ol>' : empty();
    const fallback = message => '<p class="sc-fallback">' + e(message) + ' 입력한 항목은 아래 읽기 목록에 모두 보존합니다.</p>' + collection('sc-reading-list', { number: true });
    const readingDirection = () => orientation === 'horizontal' ? '<p class="sc-direction">왼쪽에서 오른쪽으로 읽습니다. 좁은 화면에서는 이 영역 안에서 옆으로 이동할 수 있습니다.</p>' : '';
    const nativeDetails = (entry, index, open = false) => '<details class="sc-detail" id="' + e(id(index)) + '"' + (open ? ' open' : '') +
      '><summary><span class="sc-index">' + ordinal(index) + '</span><span>' + e(entry.title || '') + '</span><span class="sc-disclosure" aria-hidden="true">＋</span></summary>' +
      '<div class="sc-detail-body">' + media(entry) + copy(entry, index, { title: false }) + '</div></details>';
    const rail = className => items.length ? '<ol class="sc-rail ' + className + '">' + items.map((entry, index) =>
      '<li class="sc-rail-entry" id="' + e(id(index)) + '"><div class="sc-rail-node">' +
      (entry.image ? C.media(entry.image) + '<span class="sc-node-order" aria-label="읽는 순서 ' + (index + 1) + '">' + ordinal(index) + '</span>' :
        '<span class="sc-node-token" aria-label="읽는 순서 ' + (index + 1) + '">' + ordinal(index) + '</span>') + '</div>' + copy(entry, index) + '</li>').join('') + '</ol>' : empty();
    const verticalRail = () => items.length ? '<ol class="sc-rail sc-scene-rail sc-event-rail">' + items.map((entry, index) =>
      '<li class="sc-rail-entry' + (entry.image ? ' has-image' : '') + '" id="' + e(id(index)) + '">' +
      copy(entry, index, { number: true }) + '<span class="sc-event-pin" aria-hidden="true"></span>' +
      (entry.image ? '<div class="sc-event-visual">' + C.media(entry.image) + '<p class="sc-photo-caption">' + e(entry.title || '') + '</p></div>' : '') + '</li>').join('') + '</ol>' : empty();
    const stageLink = direction => '<span class="sc-stage-' + direction + '" aria-hidden="true"></span>';
    let body = '';

    switch (block.variant) {
      case 'chapter-cover':
        body = '<div class="sc-cover' + (p.image ? ' has-media' : '') + '">' +
          (p.image ? '<div class="sc-cover-image">' + C.media(p.image) + '</div>' : '') + '<div class="sc-cover-copy">' + head() + '</div></div>' + collection('sc-chapter-index', { number: true, disclose: true });
        break;
      case 'scene-rail':
        body = head() + leadMedia() + readingDirection() + (orientation === 'horizontal' ? rail('sc-scene-rail') : verticalRail());
        break;
      case 'branch-stage':
        body = head() + leadMedia();
        body += items.length === 4 ? '<ol class="sc-stage sc-branch-stage">' + items.map((entry, index) => '<li data-scene-role="' +
          (index === 0 ? 'start' : index === 3 ? 'result' : 'path') + '">' + (index > 0 ? stageLink('in') : '') + card(entry, index, { role: ['시작', '경로 A', '경로 B', '함께 읽는 결과'][index] }) + (index < 3 ? stageLink('out') : '') + '</li>').join('') + '</ol>' :
          fallback('시작·두 경로·결과의 네 항목일 때 분기와 합류를 표시합니다.');
        break;
      case 'merge-stage':
      case 'crafting-recipe': {
        const crafting = block.variant === 'crafting-recipe';
        body = head() + leadMedia();
        const linked = items.length === 3 || items.length === 4;
        body += items.length >= 3 ? '<ol class="sc-stage ' + (crafting ? 'sc-crafting-stage' : 'sc-merge-stage') + (linked ? ' sc-stage-linked' : '') + '" data-input-count="' + (items.length - 1) + '">' + items.map((entry, index) =>
          '<li data-scene-role="' + (index === items.length - 1 ? 'result' : 'input') + '">' + (linked && index === items.length - 1 ? stageLink('in') : '') + card(entry, index, { number: crafting,
            role: index === items.length - 1 ? '명시한 결과' : (crafting ? '조립에 사용하는 항목 ' : '모이는 입력 ') + (index + 1) }) + (linked && index < items.length - 1 ? stageLink('out') : '') + '</li>').join('') + '</ol>' :
          fallback('입력 두 개 이상과 마지막 결과가 있을 때 ' + (crafting ? '조립 과정' : '합류 관계') + '을 표시합니다.');
        break;
      }
      case 'character-orbit':
        body = head() + '<div class="sc-orbit"><div class="sc-orbit-core">' +
          (p.image ? C.media(p.image) + '<p class="sc-core-label">중심 인물</p>' : '<div class="sc-orbit-placeholder"><span>중심 인물</span></div>') + '</div>' +
          (items.length ? '<ul class="sc-orbit-members">' + items.map((entry, index) => '<li>' + card(entry, index) + '</li>').join('') + '</ul>' : empty()) + '</div>';
        break;
      case 'relationship-ledger':
        body = head() + '<div class="sc-ledger">' + leadMedia() + (items.length ? '<div class="sc-ledger-scroll" tabindex="0" role="region" aria-label="관계 기록 표">' +
          '<table><caption>입력한 항목과 관계의 기록</caption><thead><tr><th scope="col">대상</th><th scope="col">명시한 라벨·값</th><th scope="col">설명</th></tr></thead><tbody>' +
          items.map((entry, index) => '<tr id="' + e(id(index)) + '"><th scope="row">' + media(entry) + '<span class="sc-item-title">' + e(entry.title || '') +
            '</span></th><td>' + C.badge(entry.label || '') + value(entry) + '</td><td class="sc-item-body">' + e(entry.body || '') + '</td></tr>').join('') + '</tbody></table></div>' : empty()) + '</div>';
        break;
      case 'item-dossier':
        body = head() + '<div class="sc-dossier"><div class="sc-dossier-image">' + (leadMedia() || '<p class="sc-image-empty">등록된 이미지를 선택하면 항목의 대표 모습이 여기에 놓입니다.</p>') +
          '</div><div class="sc-dossier-records">' + (items.length ? items.map((entry, index) => nativeDetails(entry, index, index === 0)).join('') : empty()) + '</div></div>';
        break;
      case 'loadout-slots':
        body = head() + leadMedia() + (items.length ? '<ol class="sc-slots">' + items.map((entry, index) => '<li><span class="sc-slot-number" aria-label="배치 위치 ' + (index + 1) + '">' +
          ordinal(index) + '</span>' + card(entry, index) + '</li>').join('') + '</ol>' : empty());
        break;
      case 'nested-world':
        body = head() + '<div class="sc-common-scope"><p class="sc-scope-label">모든 항목이 함께 속하는 하나의 범위</p>' + leadMedia() +
          collection('sc-scope-members') + '</div>';
        break;
      case 'quest-route':
        body = head() + leadMedia() + readingDirection() + rail('sc-quest-rail');
        break;
      case 'parallel-lanes':
        body = head() + leadMedia() + (items.length ? '<ul class="sc-lanes">' + items.map((entry, index) => '<li><span class="sc-lane-key">' + ordinal(index) + '</span>' +
          '<article id="' + e(id(index)) + '">' + media(entry) + copy(entry, index) + '</article></li>').join('') + '</ul>' : empty());
        break;
      case 'phase-ladder':
        body = head() + leadMedia() + readingDirection() + collection('sc-ladder', { number: true });
        break;
      case 'feedback-ring':
        body = head() + '<div class="sc-feedback' + (items.length >= 2 ? ' has-cycle' : '') + '">' + leadMedia() + collection('sc-ring-members', { number: true }) + '</div>';
        break;
      case 'before-after':
        body = head() + leadMedia() + (items.length === 2 ? '<ol class="sc-before-after">' + items.map((entry, index) => '<li>' + card(entry, index, { role: index === 0 ? '이전 상태' : '이후 상태' }) + '</li>').join('') + '</ol>' :
          fallback('두 항목이 있을 때 같은 대상의 이전·이후를 나란히 표시합니다.'));
        break;
      case 'evidence-focus':
        body = '<div class="sc-evidence">' + head() + '<div class="sc-evidence-image">' + (leadMedia() || '<p class="sc-image-empty">기존 이미지와 화면을 선택해 설명의 근거를 함께 놓으세요.</p>') +
          '</div><div class="sc-evidence-notes">' + (items.length ? items.map((entry, index) => nativeDetails(entry, index, index === 0)).join('') : empty()) + '</div></div>';
        break;
      case 'story-montage':
        body = head() + leadMedia() + collection('sc-montage', { disclose: true });
        break;
      case 'world-atlas':
        body = '<div class="sc-atlas">' + head() + '<div class="sc-atlas-overview">' + (leadMedia() || '<p class="sc-image-empty">전체를 보여주는 기존 이미지를 선택하세요. 실측 좌표는 임의로 만들지 않습니다.</p>') +
          '</div>' + collection('sc-atlas-entries', { number: true }) + '</div>';
        break;
      case 'spotlight-index':
        body = head() + leadMedia() + (items.length ? '<nav class="sc-spotlight-nav" aria-label="장면 바로 이동">' + items.map((entry, index) =>
          '<a href="#' + e(id(index)) + '"><span>' + ordinal(index) + '</span><span>' + e(entry.title || '장면 ' + (index + 1)) + '</span></a>').join('') + '</nav><ol class="sc-spotlights">' +
          items.map((entry, index) => '<li>' + card(entry, index, { number: true }) + '</li>').join('') + '</ol>' : empty());
        break;
      case 'editorial-intro':
        body = '<div class="sc-editorial"><div class="sc-editorial-heading">' + head() + '</div><div class="sc-editorial-image">' + leadMedia() + '</div>' +
          '<div class="sc-editorial-records">' + collection('sc-editorial-list', { number: true }) + '</div></div>';
        break;
    }

    return '<div class="cva-scene sc-' + block.variant + '" data-scene-layout="' + block.variant + '" data-scene-direction="' + orientation + '">' + body +
      '<footer class="sc-semantic-footer"><p class="sc-relation-label"><span>관계·읽는 기준</span>' + e(p.relationLabel || '관계 문구를 입력하면 이 배치의 의미를 함께 읽을 수 있습니다.') + '</p>' +
      (p.caption ? '<p class="sc-source-caption">' + e(p.caption) + '</p>' : '') + '</footer></div>';
  }

  global.CVA_SCENE_RENDERER = { version: '1.0', render };
})(window);
