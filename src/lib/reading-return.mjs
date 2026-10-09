/** Preserve a reading location and one validated catalogue return, without chains. */
const directoryPath=/^(?:index\.html|versions\/[^/]+\.html|quests\/[^/]+\.html|설정집\.html|세력\.html|우주\.html|대사\.html|관점\/(?:region|person|faction|concept|aeon|reference)\.html|유물\.html|우주\/[a-z][a-z0-9-]*\.html|대사\/official-4\.6\.html)$/;

export function isReadingCatalogue(value,{origin,base}){
 const safe=safeReadingReturn(value,{origin,base});
 return !!safe&&directoryPath.test(decodeURIComponent(new URL(safe,origin).pathname).slice(base.replace(/\/$/,'').length+1));
}

export function sourceReadingOrigin(current,inherited,options){
 const original=safeReadingReturn(inherited,options);
 return original&&!isReadingCatalogue(original,options)?original:safeReadingReturn(current,options);
}

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
  const reader=/^(?:(?:문서|대사|대상)\/[^/]+|맥락\/[a-z][a-z0-9-]*|유물\/relic-background-[a-z0-9-]+|우주\/(?:(?:기록|설정)\/)?[a-z][a-z0-9-]*)\.html$/;
  if (!reading || !(reader.test(reading.relative)||directoryPath.test(reading.relative))) return null;
  const nested=reading.url.searchParams.get('from');
  reading.url.searchParams.delete('from');
  const catalogue=parse(nested);
  if (catalogue && directoryPath.test(catalogue.relative)) {
    catalogue.url.searchParams.delete('from');
    reading.url.searchParams.set('from',catalogue.url.pathname+catalogue.url.search+catalogue.url.hash);
  }
  return reading.url.pathname+reading.url.search+reading.url.hash;
}
