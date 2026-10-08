import {renderTopology,topologyFromRelations} from './topology.mjs';
import {readerDisclosure,sourceLink} from './reader.mjs';
import {renderCvaModule} from './cva.mjs';
import {createHash} from 'node:crypto';
export const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function safeHref(value){const s=String(value);if(!/^(?:https?:\/\/|\/|#)/.test(s)||s.startsWith('//'))throw Error('Unsupported reading URL');return escapeHtml(s);}
export function paragraphRuns(value){return String(value).split(/(\n\s*\n)/).reduce((out,text,i)=>{if(i%2)out[out.length-1].separator=text;else out.push({text,separator:''});return out;},[]);}
export const cvaId=(scope,value)=>'cva-'+String(scope).replace(/[^a-zA-Z0-9_-]/g,'-').slice(0,28)+'-'+createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0,12);
export function cvaBatches(items,render){return Array.from({length:Math.ceil(items.length/24)},(_,i)=>render(items.slice(i*24,(i+1)*24),i)).join('');}
export function readingMedia(items){
 if(!items.length)return '';
 return `<section class="rw-media rw-app not-content" aria-label="게임 이미지">${cvaBatches(items,batch=>{
 const media=batch.map((im,i)=>{
  if(!im.alt||!im.caption||!im.sourceUrl||!Number.isInteger(im.width)||!Number.isInteger(im.height)||im.width<1||im.height<1)throw Error('Game image requires identity, dimensions and source');
  safeHref(im.url);safeHref(im.sourceUrl);if(im.bodyUrl)safeHref(im.bodyUrl);
  return {id:'game-image-'+i,src:im.url,alt:im.alt,width:im.width,height:im.height,sourceUrl:im.sourceUrl};
 });
 return renderCvaModule({id:cvaId('media',batch),type:'gallery',variant:'grid',media,props:{title:'',body:'',caption:''},items:batch.map((im,i)=>({id:'image-'+i,title:im.caption,body:im.description||'',image:media[i].id})),itemExtras:batch.map(im=>im.bodyUrl?sourceLink(im.bodyUrl,'이 대상의 원문 읽기 ↗',{reading:true}):'')});
 })}</section>`;
}
export function createReadingKit({inline=escapeHtml,evidence=()=>''}={}){
 const provenance=item=>item.kind==='inference'?'편집자의 해석':item.evidence?.some(e=>e.quote===item.text)?'원문 인용':'원문에 근거한 요약';
 const E=escapeHtml,link=n=>`<a class="rw-target" data-reading-link href="${safeHref(n.url)}"><small>${E(n.kind||'')}</small><strong>${E(n.name)}</strong></a>`;
 const proof=items=>items?.length?readerDisclosure(`원문 근거 ${items.length}`,evidence(items),{className:'rw-proof'}):'';
 const section=s=>`<section class="rw-section rw-app not-content" id="${E(s.id)}"><header><h2>${E(s.title)}</h2>${s.deck?`<p class="rw-deck">${E(s.deck)}</p>`:''}</header>${s.items.map((item,i)=>{
 const quoted=provenance(item)==='원문 인용',body=renderCvaModule({id:cvaId(s.id+'-'+i,item.text),type:quoted?'quote':'text',variant:quoted?'editorial':'prose',props:{title:'',body:item.text,eyebrow:provenance(item)+(item.speaker?' · '+item.speaker:''),...(quoted?{cite:''}:{})}});
 return `<article class="rw-reading-unit">${item.title?`<h3>${E(item.title)}</h3>`:''}${body.replace(E(item.text)+'</',inline(item.text)+'</')}${proof(item.evidence)}</article>`;
 }).join('')}</section>`;
 const relations=items=>{if(!items.length)return '';const mapped=items.map((r,i)=>({...r,id:r.id||'relation-'+i,reasonClaimId:r.reasonClaimId||'claim-'+i,from:{...r.from,id:r.from.id||'from-'+i},to:{...r.to,id:r.to.id||'to-'+i}}));return renderTopology(topologyFromRelations(mapped,{id:cvaId('relations',mapped),title:'관계와 원문'}),{escape:E,href:safeHref,inline,evidence});};
 const timeline=(items,{ordered=false,note=''}={})=>`<div class="rw-timeline rw-cva-bridge rw-app not-content" data-order="${ordered?'source':'independent'}">${cvaBatches(items,batch=>renderCvaModule({id:cvaId('events',batch),type:ordered?'scene-composition':'cards',variant:ordered?'scene-rail':'list',props:{title:'',body:note,...(ordered?{relationLabel:'원문에서 확인한 사건 순서',caption:''}:{})},items:batch.map((p,i)=>({id:'event-'+i,title:p.title,body:p.text,label:p.when||''})),itemExtras:batch.map(p=>proof(p.evidence))}))}${!items.length&&note?`<p class="rw-deck">${E(note)}</p>`:''}</div>`;
 const comparison=panels=>`<div class="rw-comparison rw-cva-bridge rw-app not-content">${cvaBatches(panels,batch=>renderCvaModule({id:cvaId('compare',batch),type:'comparison',variant:'columns',orientation:'horizontal',props:{title:'',body:''},items:batch.map((p,i)=>({id:'record-'+i,title:p.title,body:p.text,label:provenance(p)+(p.speaker?' · '+p.speaker:'')})),itemExtras:batch.map(p=>proof(p.evidence))}))}</div>`;
 const containment=c=>`<div class="rw-containment rw-cva-bridge rw-app not-content">${cvaBatches(c.children,batch=>renderCvaModule({id:cvaId('scope',[c.parent,batch]),type:'scene-composition',variant:'nested-world',props:{title:c.parent,body:'',relationLabel:'원문에 명시된 포함 범위',caption:''},items:batch.map((n,i)=>({id:'member-'+i,title:typeof n==='string'?n:n.name,body:''})),itemTitles:batch.map(n=>typeof n==='string'?E(n):link(n))}))}${proof(c.evidence)}</div>`;
 const process=(items,{kind='steps',label='',returnLabel=''}={})=>{if(kind==='cycle'&&!returnLabel)throw Error('Cycle needs an evidenced return label');return `<section class="rw-process rw-cva-bridge rw-app not-content" data-kind="${E(kind)}">${label?`<h2>${E(label)}</h2>`:''}${!items.length&&returnLabel?`<p>${E(returnLabel)}</p>`:''}${cvaBatches(items,batch=>renderCvaModule({id:cvaId('process',batch),type:'scene-composition',variant:kind==='cycle'?'feedback-ring':'quest-route',props:{title:'',body:'',relationLabel:kind==='cycle'?returnLabel:'함께 읽는 순서',caption:''},items:batch.map((p,i)=>({id:'step-'+i,title:p.title,body:p.text,label:provenance(p)})),itemExtras:batch.map(p=>proof(p.evidence))}))}</section>`;};
 const source=blocks=>`<div class="rw-original rw-app not-content">${blocks.map(block=>`<section id="${E(block.id)}">${block.title?`<h2>${E(block.title)}</h2>`:''}${paragraphRuns(block.text).map(p=>`<p>${E(p.text)}</p>`).join('')}</section>`).join('')}</div>`;
 const topology=t=>renderTopology(t,{escape:E,href:safeHref,inline,evidence});
 const network=(items,options)=>{const t=topologyFromRelations(items,options);return t?topology(t):'';};
 const directory=items=>items.length?`<section class="rw-directory rw-cva-bridge rw-app not-content" aria-label="관련 본문">${cvaBatches(items,batch=>renderCvaModule({id:cvaId('directory',batch),type:'cards',variant:'list',props:{title:'',body:''},items:batch.map((n,i)=>({id:'entry-'+i,title:n.name,body:n.summary||'',label:n.kind||''})),itemTitles:batch.map(n=>`<a data-reading-link href="${safeHref(n.url)}">${E(n.name)} <span aria-hidden="true">↗</span></a>`)}))}</section>`:'';
 return {section,relations,timeline,comparison,containment,process,source,topology,network,directory,media:readingMedia};
}
