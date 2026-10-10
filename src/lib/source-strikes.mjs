import {escapeHtml} from './reading-kit/render.mjs';
/** Render only sourced strike intervals. All original characters stay escaped. */
export function validateStrikeRanges(text,ranges=[]){
 const length=Array.from(text).length;let end=0;
 for(const range of ranges){if(!Array.isArray(range)||range.length!==2||!range.every(Number.isSafeInteger)||range[0]<end||range[0]<0||range[0]>=range[1]||range[1]>length)throw Error('Invalid source strike interval');end=range[1];}
 return ranges;
}
export function escapeSourceRun(value,offset=0,ranges=[]){
 const chars=Array.from(value),last=offset+chars.length,cuts=new Set([offset,last]);
 for(const [start,end] of ranges){if(start>offset&&start<last)cuts.add(start);if(end>offset&&end<last)cuts.add(end);}
 const ordered=[...cuts].sort((a,b)=>a-b);let html='';
 for(let i=1;i<ordered.length;i++){
  const from=ordered[i-1],to=ordered[i],escaped=escapeHtml(chars.slice(from-offset,to-offset).join(''));
  html+=ranges.some(([start,end])=>start<=from&&to<=end)?'<s>'+escaped+'</s>':escaped;
 }
 return html;
}
