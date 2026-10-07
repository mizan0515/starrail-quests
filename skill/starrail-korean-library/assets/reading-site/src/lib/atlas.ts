import atlas from '../../editorial/context-atlas.json';
import {href,docUrl} from './data';
export {atlas};
export const atlasUrl=(id:string)=>href(`맥락/${id}.html`);
export const evidenceUrl=(e:any)=>`${docUrl(e.id)}#${e.anchor}`;
export const axisName=(axis:string)=>atlas.axes.find(x=>x.id===axis)?.name||'세력·종족';
export const atlasNode=(id:string)=>atlas.nodes.find(x=>x.id===id)!;
// Longer names win. Only the first occurrence of each term and up to three terms
// per paragraph are annotated; the original text remains in the DOM unchanged.
const terms=atlas.nodes.flatMap(n=>n.terms.filter(t=>t.length>1&&!['생명','감정','선주','나부','파벌','헤르타','우주정거장','사냥단','티탄'].includes(t)).map(term=>({term,id:n.id}))).sort((a,b)=>b.term.length-a.term.length);
const termMap=new Map(terms.map(t=>[t.term,t.id]));
const termPattern=new RegExp(terms.map(t=>t.term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|'),'g');
export function annotate(text:string){
  const pieces:{text:string;id?:string}[]=[],seen=new Set<string>();let start=0;
  for(const match of text.matchAll(termPattern)){
    const id=termMap.get(match[0])!;
    if(seen.has(id)||seen.size>=3)continue;
    if(match.index!>start)pieces.push({text:text.slice(start,match.index)});
    pieces.push({text:match[0],id});seen.add(id);start=match.index!+match[0].length;
  }
  if(start<text.length)pieces.push({text:text.slice(start)});
  return pieces;
}
