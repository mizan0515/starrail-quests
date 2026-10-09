import atlas from '../../editorial/context-atlas.json';
import explorer from '../../data/explorer.json';
import {href,docUrl} from './data';
import {escapeHtml} from './reading-kit/render.mjs';
export {atlas};
export const atlasUrl=(id:string)=>{const e=explorer.entries.find(e=>e.id===id);return e?e.axis==='concept'?docUrl(e.id):href(`대상/${e.id}.html`):href(`맥락/${id}.html`);};
export const evidenceUrl=(e:any)=>`${docUrl(e.id)}#${e.anchor}`;
export const axisName=(axis:string)=>atlas.axes.find(x=>x.id===axis)?.name||'세력·종족';
export const atlasNode=(id:string)=>atlas.nodes.find(x=>x.id===id)||explorer.entries.find(x=>x.id===id)!;
// Longer names win. Only the first occurrence of each term and up to three terms
// per paragraph are annotated; the original text remains in the DOM unchanged.
// Ordinary preservation of memories also uses 보존. The atlas alias is useful
// for search, but only the proper names 클리포트/보천파 qualify for auto-linking.
const curatedTerms=atlas.nodes.flatMap(n=>n.terms.filter(t=>t.length>1&&!['보존','생명','감정','선주','나부','파벌','헤르타','우주정거장','사냥단','티탄'].includes(t)).map(term=>({term,id:n.id})));
const completeTerms=explorer.entries.filter(e=>e.axis!=='person'||e.nameVerified).filter(e=>!e.name.startsWith('개척자')&&!e.name.includes('{')).flatMap(e=>[...new Set([e.name,e.name.replace('•','·')])].filter(t=>t.length>=(e.axis==='concept'?4:2)).map(term=>({term,id:e.id})));
const termMap=new Map<string,string>();for(const t of [...curatedTerms,...completeTerms])if(!termMap.has(t.term))termMap.set(t.term,t.id);
const terms=[...termMap].map(([term,id])=>({term,id})).sort((a,b)=>b.term.length-a.term.length);
const termPattern=new RegExp(terms.map(t=>t.term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|'),'g');
export function annotate(text:string){
  const pieces:{text:string;id?:string}[]=[],seen=new Set<string>();let start=0;
  for(const match of text.matchAll(termPattern)){
    const at=match.index!,after=at+match[0].length;
    // A short proper name inside a Korean verb is not a mention of that entity.
    // Keep explicit names with normal particles, but reject 좋아하다 → 아하.
    if(at>0&&/[\p{L}\p{N}]/u.test(text[at-1]))continue;
    if(/[\p{L}\p{N}]/u.test(text[after]||'')){
      const tail=text.slice(after);
      if(!/^(?:은|는|이|가|을|를|의|에|에서|에게|와|과|도|로|으로|부터|까지|께서|씨(?:가|는|의|도|를)?)(?=$|[^\p{L}\p{N}])/u.test(tail))continue;
    }
    const id=termMap.get(match[0])!;
    if(seen.has(id)||seen.size>=3)continue;
    if(match.index!>start)pieces.push({text:text.slice(start,match.index)});
    pieces.push({text:match[0],id});seen.add(id);start=match.index!+match[0].length;
  }
  if(start<text.length)pieces.push({text:text.slice(start)});
  return pieces;
}
export const readingInline=(text:string)=>annotate(String(text)).map(piece=>piece.id?`<a class="setting-entity-link" data-reading-link href="${escapeHtml(atlasUrl(piece.id))}">${escapeHtml(piece.text)}</a>`:escapeHtml(piece.text)).join('');
