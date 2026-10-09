/** Metadata text only. Original rows and their HTML readers keep their own formatting. */
export function metadataText(value) {
  return String(value ?? '')
    .replace(/<br\s*\/?\s*>/gi, ' ')
    .replace(/<\/?(?:color|size|b|i|u|s|br|sprite|style|font)(?:\s[^>]*|=[^>]*|\s*\/?)>/gi, '')
    .replace(/\{RUBY_B#[^}]*\}|\{RUBY_E#?\}/g, '')
    .replace(/&nbsp;|&#160;/g, ' ')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
    .replace(/\s+/g, ' ').trim();
}

const unknown = new Set(['분류 미확인', '챕터 미지정', '한국어 본문 미수록']);
export function sourceDescription(parts, excerpt = '', limit = 190) {
  const labels = [...new Set(parts.map(metadataText).filter(text => text && !unknown.has(text)))];
  const prefix = labels.join(' · ');
  const prefixChars = Array.from(prefix);
  if (prefixChars.length > limit) return prefixChars.slice(0, limit - 1).join('') + '…';
  const source = metadataText(excerpt);
  const available = Math.max(0, limit - Array.from(prefix).length - 9);
  if (!source || unknown.has(source) || available < 24) return prefix;
  const chars = Array.from(source);
  const sample = chars.length > available ? chars.slice(0, available - 1).join('') + '…' : source;
  return `${prefix}. 원문 구절: ${sample}`;
}

export function documentDescription(document, reading) {
  const sections = document.sections || [];
  const rows = sections.flatMap(section => section.rows || []);
  const source = rows.find(row => row.label === '이야기' && row.text)?.text || rows.find(row => row.text && row.text !== '한국어 본문 미수록')?.text;
  if (document.category === '퀘스트') {
    const content = reading?.dialogueCount || reading?.captionCount ? '대사와 선택지 원문' : reading?.choiceCount ? '선택지 원문과 임무 목표' : '임무 개요와 진행 목표';
    return sourceDescription([document.title, document.kind || document.category, document.world, document.chapter, content], source || document.stages?.[0]?.description || document.stages?.[0]?.title);
  }
  return sourceDescription([document.title, document.category, document.world, document.collection, source ? '한국어 원문' : '자료 정보'], source);
}

/** URLs remain query-free while the reader's from/speaker/filter URLs remain intact. */
export function canonicalPageUrl(value, site = 'https://mizan0515.github.io') {
  const url = new URL(value, site);
  url.search = '';
  url.hash = '';
  url.pathname = url.pathname.endsWith('/') ? url.pathname + 'index.html' : /\.html$/.test(url.pathname) ? url.pathname : url.pathname + '.html';
  return url.href;
}
