import {renderTopology,topologyFromRelations} from './topology.mjs';
import {readerDisclosure,sourceLink} from './reader.mjs';
export const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function safeHref(value){const s=String(value);if(!/^(?:https?:\/\/|\/|#)/.test(s)||s.startsWith('//'))throw Error('Unsupported reading URL');return escapeHtml(s);}
export function paragraphRuns(value){return String(value).split(/(\n\s*\n)/).reduce((out,text,i)=>{if(i%2)out[out.length-1].separator=text;else out.push({text,separator:''});return out;},[]);}
export function readingMedia(items){
 if(!items.length)return '';
 return `<section class="rw-media rw-app not-content" aria-label="게임 이미지">${items.map(im=>{
  if(!im.alt||!im.caption||!im.sourceUrl||!Number.isInteger(im.width)||!Number.isInteger(im.height)||im.width<1||im.height<1)throw Error('Game image requires identity, dimensions and source');
  const img=`<img src="${safeHref(im.url)}" alt="${escapeHtml(im.alt)}" width="${im.width}" height="${im.height}" loading="lazy" decoding="async">`;
  return `<figure${im.width/im.height>=1.5?' class="rw-media-wide"':''}>${im.bodyUrl?`<a data-reading-link href="${safeHref(im.bodyUrl)}">${img}</a>`:img}<figcaption><strong>${escapeHtml(im.caption)}</strong>${im.description?`<span>${escapeHtml(im.description)}</span>`:''}${sourceLink(im.sourceUrl,'이미지 출처 ↗')}</figcaption></figure>`;
 }).join('')}</section>`;
}
export function createReadingKit({inline=escapeHtml,evidence=()=>''}={}){
 const provenance=item=>item.kind==='inference'?'편집자의 해석':item.evidence?.some(e=>e.quote===item.text)?'원문 인용':'원문에 근거한 요약';
 const E=escapeHtml,link=n=>`<a class="rw-target" data-reading-link href="${safeHref(n.url)}"><small>${E(n.kind||'')}</small><strong>${E(n.name)}</strong></a>`;
 const proof=items=>items?.length?readerDisclosure(`원문 근거 ${items.length}`,evidence(items),{className:'rw-proof'}):'';
 const section=s=>`<section class="rw-section rw-app not-content" id="${E(s.id)}"><header><h2>${E(s.title)}</h2>${s.deck?`<p class="rw-deck">${E(s.deck)}</p>`:''}</header>${s.items.map(item=>`<article class="rw-reading-unit">${item.title?`<h3>${E(item.title)}</h3>`:''}<span class="rw-attribution">${provenance(item)}${item.speaker?' · '+E(item.speaker):''}</span>${provenance(item)==='원문 인용'?`<blockquote class="rw-quotation">${inline(item.text)}</blockquote>`:`<p>${inline(item.text)}</p>`}${proof(item.evidence)}</article>`).join('')}</section>`;
 const relations=items=>`<div class="rw-relations rw-app not-content">${items.map(r=>`<article class="rw-relation"><div class="rw-edge">${link(r.from)}<div class="rw-verb"><strong>${E(r.label)}</strong><span aria-hidden="true">→</span></div>${link(r.to)}</div><p>${inline(r.reason)}</p>${r.kind==='inference'?'<span class="rw-attribution">편집자의 연결</span>':''}${proof(r.evidence)}</article>`).join('')}</div>`;
 const timeline=(items,{ordered=false,note=''}={})=>`<div class="rw-timeline rw-app not-content" data-order="${ordered?'source':'independent'}">${note?`<p class="rw-deck">${E(note)}</p>`:''}<ol>${items.map(item=>`<li><span class="rw-time">${E(item.when||'')}</span><div><h3>${E(item.title)}</h3><p>${inline(item.text)}</p>${proof(item.evidence)}</div></li>`).join('')}</ol></div>`;
 const comparison=panels=>`<div class="rw-comparison rw-app not-content">${panels.map(p=>`<article><header><h3>${E(p.title)}</h3>${p.speaker?`<span class="rw-attribution">${E(p.speaker)}</span>`:''}</header><span class="rw-attribution">${provenance(p)}</span><p>${inline(p.text)}</p>${proof(p.evidence)}</article>`).join('')}</div>`;
 const containment=c=>`<div class="rw-containment rw-app not-content"><strong>${E(c.parent)}</strong><ul>${c.children.map(n=>`<li>${typeof n==='string'?E(n):link(n)}</li>`).join('')}</ul>${proof(c.evidence)}</div>`;
 const process=(items,{kind='steps',label='',returnLabel=''}={})=>{if(kind==='cycle'&&!returnLabel)throw Error('Cycle needs an evidenced return label');return `<section class="rw-process rw-app not-content" data-kind="${E(kind)}">${label?`<h2>${E(label)}</h2>`:''}<ol>${items.map(item=>`<li><h3>${E(item.title)}</h3><p>${inline(item.text)}</p>${proof(item.evidence)}</li>`).join('')}</ol>${kind==='cycle'?`<p class="rw-return">↺ ${E(returnLabel)}</p>`:''}</section>`;};
 const source=blocks=>`<div class="rw-original rw-app not-content">${blocks.map(block=>`<section id="${E(block.id)}">${block.title?`<h2>${E(block.title)}</h2>`:''}${paragraphRuns(block.text).map(p=>`<p>${E(p.text)}</p>`).join('')}</section>`).join('')}</div>`;
 const topology=t=>renderTopology(t,{escape:E,href:safeHref,inline,evidence});
 const network=(items,options)=>{const t=topologyFromRelations(items,options);return t?topology(t):'';};
 const directory=items=>`<section class="rw-directory rw-app not-content" aria-label="관련 본문">${items.map((n,i)=>`<a data-reading-link href="${safeHref(n.url)}"><span class="rw-directory-number" aria-hidden="true">${String(i+1).padStart(2,'0')}</span><div><strong>${E(n.name)}</strong><p>${E(n.summary)}</p></div><span aria-hidden="true">↗</span></a>`).join('')}</section>`;
 return {section,relations,timeline,comparison,containment,process,source,topology,network,directory,media:readingMedia};
}
