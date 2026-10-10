import {annotate,atlasUrl} from './atlas';
import {paragraphRuns,escapeHtml as E} from './reading-kit/render.mjs';
import {validateStrikeRanges,escapeSourceRun} from './source-strikes.mjs';

/** One escaped source template for source pages, scenes and version comparisons. */
export function sourceParagraphs(text:string,anchor:string,strikeRanges:number[][]=[]):string {
 validateStrikeRanges(text,strikeRanges);let cursor=0;
 const paragraphs:any[][]=[[]];
 annotate(text).forEach((part,termIndex)=>paragraphRuns(part.text).forEach((run,index)=>{
  if(index)paragraphs.push([]);
  const value=run.text+run.separator;paragraphs[paragraphs.length-1].push({...part,text:value,termIndex,sourceOffset:cursor});cursor+=Array.from(value).length;
 }));
 return `<p class="original-body rw-source-body" id="${E(anchor)}" data-pagefind-weight="1">${paragraphs.map(parts=>`<span class="original-paragraph">${parts.map(part=>part.id?`<a class="context-term" id="${E(anchor)}-term-${part.termIndex}" href="${E(atlasUrl(part.id))}" data-context-key="${E(part.id)}" data-context-excerpt="${E(text.slice(0,220))}" aria-label="${E(part.text)} · 배경과 연결 보기">${escapeSourceRun(part.text,part.sourceOffset,strikeRanges)}</a>`:escapeSourceRun(part.text,part.sourceOffset,strikeRanges)).join('')}</span>`).join('')}</p>`;
}
