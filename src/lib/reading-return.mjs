/** Preserve a reading location and one validated catalogue return, without chains. */
export function safeReadingReturn(value, {origin, base}) {
  if (typeof value !== 'string' || !value || !origin || typeof base !== 'string') return null;
  const siteBase=base.replace(/\/$/, '');
  function parse(candidate) {
    if (typeof candidate !== 'string' || !candidate || /[\\\u0000-\u0020\u007f]/.test(candidate)) return null;
    try {
      // URL accepts malformed percent escapes; reject them before resolving.
      decodeURI(candidate);
      const rawPath=decodeURIComponent(candidate.split(/[?#]/,1)[0]);
      if (rawPath.split('/').some(segment=>segment==='.'||segment==='..')) return null;
      const url=new URL(candidate, origin);
      if (url.origin!==origin || url.username || url.password || /%2f|%5c/i.test(url.pathname)) return null;
      const pathname=decodeURIComponent(url.pathname);
      if (pathname.includes('%') || pathname.includes('\\') || !pathname.startsWith(siteBase+'/')) return null;
      return {url, relative:pathname.slice(siteBase.length+1)};
    } catch {return null;}
  }
  const reading=parse(value);
  if (!reading || !/^(?:문서|대사|대상)\/[^/]+\.html$/.test(reading.relative)) return null;
  const nested=reading.url.searchParams.get('from');
  reading.url.searchParams.delete('from');
  const catalogue=parse(nested);
  if (catalogue && /^(?:index\.html|versions\/[^/]+\.html|quests\/[^/]+\.html|설정집\.html)$/.test(catalogue.relative)) {
    catalogue.url.searchParams.delete('from');
    reading.url.searchParams.set('from',catalogue.url.pathname+catalogue.url.search+catalogue.url.hash);
  }
  return reading.url.pathname+reading.url.search+reading.url.hash;
}
