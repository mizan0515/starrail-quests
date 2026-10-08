export function validateTopology(t,hasClaim=()=>true){
 if(!t.nodes?.length||!t.edges?.length)throw Error('Topology needs nodes and edges');
 if(t.presentation!==undefined&&t.presentation!=='relations')throw Error('Unknown topology presentation');
 if(t.layout!==undefined&&!['relations','cycle'].includes(t.layout))throw Error('Unknown source topology layout');
 if(t.layout==='cycle'&&!t.edges.some(e=>e.kind==='return'))throw Error('Cycle layout requires a source return relation');
 const ids=new Set();for(const n of t.nodes){if(ids.has(n.id))throw Error('Duplicate topology node');ids.add(n.id);if(!n.name||!Number.isInteger(n.layer)||n.layer<0||n.layer>3)throw Error('Invalid topology node');if(n.scale&&!t.scaleNote)throw Error('Relative scale needs a scope note');}
 const edgeIds=new Set();for(const e of t.edges){if(!e.id||edgeIds.has(e.id))throw Error('Duplicate or missing topology edge');edgeIds.add(e.id);if(!ids.has(e.from)||!ids.has(e.to)||!e.label||!e.claimId||!hasClaim(e.claimId))throw Error('Invalid topology edge or evidence');if(!['relation','sequence','return'].includes(e.kind||'relation'))throw Error('Invalid topology edge kind');if(e.structure!==undefined&&(!['membership','containment'].includes(e.structure)||e.claimKind==='inference'||(e.kind||'relation')!=='relation'))throw Error('Invalid source relationship structure');}
 return t;
}
export function topologyFromRelations(relations,{id='relationships',title='관계 한눈에',focusId}={}){
 if(!relations.length)return null;
 const nodes=new Map();for(const r of relations)for(const n of [r.from,r.to])nodes.set(n.id,{...n,layer:0});
 const indegree=new Map([...nodes.keys()].map(id=>[id,0]));for(const r of relations)indegree.set(r.to.id,indegree.get(r.to.id)+1);
 const queue=[...nodes.keys()].filter(id=>!indegree.get(id));let visited=0;
 for(let i=0;i<queue.length;i++){const id=queue[i];visited++;for(const r of relations.filter(r=>r.from.id===id)){nodes.get(r.to.id).layer=Math.max(nodes.get(r.to.id).layer,Math.min(3,nodes.get(id).layer+1));indegree.set(r.to.id,indegree.get(r.to.id)-1);if(!indegree.get(r.to.id))queue.push(r.to.id);}}
 if(visited!==nodes.size)for(const n of nodes.values())n.layer=n.id===focusId?0:1;
 return {id,title,presentation:'relations',nodes:[...nodes.values()].map(n=>({...n,focus:n.id===focusId})),edges:relations.map(r=>({id:r.id,from:r.from.id,to:r.to.id,label:r.label,claimId:r.reasonClaimId,reason:r.reason,evidence:r.evidence,kind:'relation',claimKind:r.claimKind||r.kind,speaker:r.speaker||'',...(r.structure?{structure:r.structure}:{})}))};
}
import {readerDisclosure} from './reader.mjs';
import {renderCvaModule} from './cva.mjs';
import {createHash} from 'node:crypto';
const moduleId=(id,value)=>'cva-'+String(id).replace(/[^a-zA-Z0-9_-]/g,'-').slice(0,28)+'-'+createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0,12);
function verifiedPath(t){
 if(!t.edges.every(e=>e.kind==='sequence')||t.edges.length!==t.nodes.length-1)return null;
 const start=t.nodes.filter(n=>!t.edges.some(e=>e.to===n.id));if(start.length!==1)return null;
 const order=[start[0]];while(order.length<t.nodes.length){const outgoing=t.edges.filter(e=>e.from===order.at(-1).id);if(outgoing.length!==1||order.some(n=>n.id===outgoing[0].to))return null;order.push(t.nodes.find(n=>n.id===outgoing[0].to));}
 return order;
}
function verifiedCycle(t){
 const returns=t.edges.filter(e=>e.kind==='return');
 if(t.layout!=='cycle'||returns.length!==1)return null;
 const ordered=[t.nodes.find(n=>n.id===returns[0].to)],edges=[];
 while(ordered.length<=t.nodes.length){const next=t.edges.filter(e=>e.from===ordered.at(-1).id);if(next.length!==1)return null;const edge=next[0];edges.push(edge);if(edge.to===ordered[0].id)break;if(ordered.some(n=>n.id===edge.to))return null;ordered.push(t.nodes.find(n=>n.id===edge.to));}
 if(ordered.length<2||edges.length!==ordered.length||edges.at(-1).to!==ordered[0].id||!edges.includes(returns[0]))return null;
 const cycleIds=new Set(ordered.map(n=>n.id)),external=t.edges.filter(e=>!edges.includes(e));
 // An explicit cycle may have direct incoming sources. Outgoing forks and
 // unrelated components retain the complete relationship ledger.
 if(external.some(e=>cycleIds.has(e.from)||!cycleIds.has(e.to))||t.nodes.some(n=>!cycleIds.has(n.id)&&!external.some(e=>e.from===n.id)))return null;
 return {nodes:ordered,edges,external};
}
// Group only relationships explicitly reviewed as membership or inclusion.
// A place of birth, location, shared keyword or a target's kind is insufficient.
export function relationStructureGroups(edges){
 const groups=new Map();
 for(const e of edges){
  if(!e.structure||e.claimKind==='inference')continue;
  const parent=e.structure==='membership'?e.to:e.from;
  const key=e.structure+'\0'+parent;
  if(!groups.has(key))groups.set(key,{parent,structure:e.structure,edges:[]});
  groups.get(key).edges.push(e);
 }
 return [...groups.values()];
}
export function focusRelationLayout(nodes,edges){
 const focus=nodes.filter(n=>n.focus);
 if(focus.length!==1||edges.length<2||edges.length>8||edges.some(e=>(e.kind||'relation')!=='relation'||e.from===e.to||e.from!==focus[0].id&&e.to!==focus[0].id))return null;
 const incoming=edges.some(e=>e.to===focus[0].id),outgoing=edges.some(e=>e.from===focus[0].id);
 return {focus:focus[0],variant:incoming&&outgoing?'character-orbit':'hub'};
}
// A connected source tree is shown as local hubs. Each hub contains only its
// direct edges; neither a shared outcome nor a time sequence is added.
export function sourceRelationHubs(nodes,edges){
 if(nodes.some(n=>n.focus)||edges.length<3||edges.some(e=>(e.kind||'relation')!=='relation'||e.claimKind==='inference'||e.from===e.to))return null;
 const used=new Set(edges.flatMap(e=>[e.from,e.to])),incoming=new Map([...used].map(id=>[id,0])),groups=new Map();
 for(const e of edges){incoming.set(e.to,incoming.get(e.to)+1);if(!groups.has(e.from))groups.set(e.from,[]);groups.get(e.from).push(e);}
 if(groups.size<2||![...groups.values()].some(es=>es.length>1)||[...incoming.values()].some(v=>v>1))return null;
 const roots=[...used].filter(id=>!incoming.get(id));if(roots.length!==1)return null;
 const visited=new Set(),queue=[roots[0]];
 for(let i=0;i<queue.length;i++){if(visited.has(queue[i]))return null;visited.add(queue[i]);queue.push(...(groups.get(queue[i])||[]).map(e=>e.to));}
 if(visited.size!==used.size)return null;
 return [...groups].map(([parent,edges])=>({parent,edges}));
}
export function renderTopology(t,{escape:E,href,inline,evidence}){
 validateTopology(t);
 const nodes=new Map(t.nodes.map(n=>[n.id,n]));
 const name=id=>nodes.get(id).name;
 const endpoint=n=>`${n.kind?`<small class="rw-node-kind">${E(n.kind)}</small>`:''}${n.url?`<a data-reading-link href="${href(n.url)}">${E(n.name)}</a>`:`<strong>${E(n.name)}</strong>`}`;
 const statement=e=>`<span class="rw-edge-statement"><span class="rw-edge-subject">${endpoint(nodes.get(e.from))}</span><span class="rw-edge-arrow" aria-hidden="true"> → </span><span class="rw-edge-predicate">${E(e.label)}</span><span class="rw-edge-arrow" aria-hidden="true"> → </span><span class="rw-edge-object">${endpoint(nodes.get(e.to))}</span></span>`;
 const attribution=e=>(e.claimKind==='inference'?'편집자의 연결':e.claimKind==='attributed'?'발언·기록에 따른 관계':'원문에 명시된 관계')+(e.claimKind!=='inference'&&e.speaker?' · '+e.speaker:'');
 const proof=e=>readerDisclosure(`${e.claimKind==='inference'?'연결의 원문 근거':'원문 근거'} ${e.evidence?.length||0}개`,`<span class="rw-attribution">${E(attribution(e))}</span><p>${inline(e.reason||e.text||e.label)}</p>${evidence(e.evidence||[])}`,{id:t.id+'-edge-'+e.id,className:'rw-relation-proof'});
 const explicit=t.edges.filter(e=>e.claimKind!=='inference'),connections=t.edges.filter(e=>e.claimKind==='inference');
 const relationModules=edges=>Array.from({length:Math.ceil(edges.length/24)},(_,i)=>{
 const batch=edges.slice(i*24,(i+1)*24);
 return renderCvaModule({id:moduleId(t.id,batch),type:'cards',variant:'list',props:{title:'',body:''},items:batch.map((e,j)=>({id:'relation-'+j,title:name(e.from)+' → '+name(e.to),body:e.reason||e.text||e.label,label:attribution(e)})),itemTitles:batch.map(statement),itemExtras:batch.map(e=>`<div class="rw-relation-band" aria-label="${E(name(e.from)+' → '+e.label+' → '+name(e.to))}" data-relation-from="${E(e.from)}" data-relation-to="${E(e.to)}">${proof(e)}</div>`)});
 }).join('');
 const structuredRelations=edges=>{
  const groups=relationStructureGroups(edges),grouped=new Set(groups.flatMap(g=>g.edges));
  let html=groups.flatMap(group=>Array.from({length:Math.ceil(group.edges.length/24)},(_,i)=>({...group,edges:group.edges.slice(i*24,(i+1)*24)}))).map(g=>{
   const member=e=>nodes.get(g.structure==='membership'?e.from:e.to);
   const module=renderCvaModule({id:moduleId(t.id+'-scope',g),type:'scene-composition',variant:'nested-world',orientation:'horizontal',props:{title:name(g.parent),body:'',relationLabel:'',caption:''},items:g.edges.map((e,i)=>({id:'member-'+i,title:member(e).name,body:e.reason||e.text||e.label,label:e.label})),itemTitles:g.edges.map(e=>endpoint(member(e))),itemExtras:g.edges.map(e=>`<div class="rw-relation-band" data-relation-from="${E(e.from)}" data-relation-to="${E(e.to)}">${statement(e)}${proof(e)}</div>`)});
   return `<div class="rw-source-scope" data-relationship-structure="${E(g.structure)}">${module.replace(`<h2 class="cva-title">${E(name(g.parent))}</h2>`,`<h3 class="cva-title">${endpoint(nodes.get(g.parent))}</h3>`).replace('모든 항목이 함께 속하는 하나의 범위',g.structure==='membership'?'소속과 구성':'포함된 대상')}</div>`;
  }).join('');
  const rest=edges.filter(e=>!grouped.has(e)),hubs=sourceRelationHubs(t.nodes,rest);
  if(hubs){
   html+=hubs.flatMap(g=>Array.from({length:Math.ceil(g.edges.length/23)},(_,i)=>({...g,edges:g.edges.slice(i*23,(i+1)*23)}))).map(g=>`<div class="rw-focus-relations" data-relationship-structure="directed-hub" data-hub-shape="${g.edges.length===1?'pair':'fan'}">${renderCvaModule({id:moduleId(t.id+'-direct',g),type:'flow',variant:'hub',orientation:'horizontal',props:{title:'',body:'',relationLabel:''},items:[{id:'focus',title:name(g.parent),body:'',label:nodes.get(g.parent).kind||''},...g.edges.map((e,i)=>({id:'relation-'+i,title:name(e.to),body:e.reason||e.text||e.label,label:attribution(e)}))],itemTitles:[endpoint(nodes.get(g.parent)),...g.edges.map(e=>endpoint(nodes.get(e.to)))],itemExtras:['',...g.edges.map(e=>`<div class="rw-relation-band" data-relation-from="${E(e.from)}" data-relation-to="${E(e.to)}">${statement(e)}${proof(e)}</div>`)]})}</div>`).join('');
   return html;
  }
  const focusLayout=focusRelationLayout(t.nodes,rest);
  if(!focusLayout)return html+relationModules(rest);
  const scopeHtml=html;html='';
  const focus=focusLayout.focus,other=e=>nodes.get(e.from===focus.id?e.to:e.from);
  const direction=e=>e.to===focus.id?'incoming':'outgoing';
  const sides={incoming:rest.filter(e=>direction(e)==='incoming'),outgoing:rest.filter(e=>direction(e)==='outgoing')};
  const relationRow=e=>sides[direction(e)].indexOf(e)+1+Math.floor((Math.max(sides.incoming.length,sides.outgoing.length)-sides[direction(e)].length)/2);
  const extra=e=>`<div class="rw-relation-band" data-relation-direction="${direction(e)}" data-relation-row="${relationRow(e)}" data-relation-from="${E(e.from)}" data-relation-to="${E(e.to)}">${statement(e)}${proof(e)}</div>`;
  if(focusLayout.variant==='character-orbit'){
   const orbit=renderCvaModule({id:moduleId(t.id+'-focus',rest),type:'scene-composition',variant:'character-orbit',orientation:'original',props:{title:'',body:'',relationLabel:'',caption:''},items:rest.map((e,i)=>({id:'relation-'+i,title:other(e).name,body:e.reason||e.text||e.label,label:name(e.from)+' → '+name(e.to)})),itemTitles:rest.map(e=>endpoint(other(e))),itemExtras:rest.map(e=>`<p class="rw-relation-attribution">${E(attribution(e))}</p>${extra(e)}`)});
   html+=`<div class="rw-focus-relations" data-relationship-structure="directed-orbit">${orbit.replace('<div class="sc-orbit-placeholder"><span>중심 인물</span></div>',`<div class="sc-orbit-placeholder"><span class="rw-focus-name">${endpoint(focus)}</span></div>`)}</div>`;
  }else{
   html+=`<div class="rw-focus-relations" data-relationship-structure="directed-hub" data-hub-shape="fan">${renderCvaModule({id:moduleId(t.id+'-focus',rest),type:'flow',variant:'hub',orientation:'horizontal',props:{title:'',body:'',relationLabel:''},items:[{id:'focus',title:focus.name,body:'',label:focus.kind||''},...rest.map((e,i)=>({id:'relation-'+i,title:other(e).name,body:e.reason||e.text||e.label,label:attribution(e)}))],itemTitles:[endpoint(focus),...rest.map(e=>endpoint(other(e)))],itemExtras:['',...rest.map(extra)]})}</div>`;
  }
  return html+scopeHtml;
 };
 const path=verifiedPath(t),cycle=verifiedCycle(t),ordered=path||cycle?.nodes;
 let diagram='';
 if(ordered&&ordered.length<=24&&!connections.length){
 const incoming=n=>(cycle?.edges||t.edges).filter(e=>e.to===n.id);
 diagram=renderCvaModule({id:moduleId(t.id+'-structure',ordered),type:'scene-composition',variant:cycle?'feedback-ring':'quest-route',props:{title:'',body:t.note||'',relationLabel:cycle?'원문에 설명된 순환 · 각 연결의 발언 주체와 근거':'원문에 명시된 과정의 순서',caption:t.scaleNote||''},items:ordered.map((n,i)=>({id:'node-'+i,title:n.name,body:n.detail||'',label:n.kind||''})),itemTitles:ordered.map(endpoint),itemExtras:ordered.map(n=>incoming(n).map(e=>`<div class="rw-structure-edge">${statement(e)}${proof(e)}</div>`).join(''))});
 if(cycle?.external.length)diagram+=structuredRelations(cycle.external);
 } else diagram=structuredRelations(explicit);
 const editorial=connections.length?`<div class="rw-reading-connections rw-cva-bridge">${explicit.length?'<h3 class="rw-reading-connections-title">함께 읽을 기록</h3>':''}${Array.from({length:Math.ceil(connections.length/24)},(_,i)=>{const batch=connections.slice(i*24,(i+1)*24);return renderCvaModule({id:moduleId(t.id+'-reading',batch),type:'cards',variant:'grid',orientation:'horizontal',props:{title:'',body:''},items:batch.map((e,j)=>({id:'connection-'+j,title:name(e.to),body:e.reason||e.text||e.label,label:'편집자의 연결 · '+name(e.from)+'에서 이어 읽기'})),itemTitles:batch.map(e=>endpoint(nodes.get(e.to))),itemExtras:batch.map(e=>`<div class="rw-reading-connection"><p class="rw-reading-topic">${E(e.label)}</p>${proof(e)}</div>`)});}).join('')}</div>`:'';
 return `<section class="rw-map rw-cva-atlas rw-app not-content" id="${E(t.id)}"><header><h2>${E(t.title==='관계 한눈에'&&!explicit.length?'함께 읽을 기록':t.title)}</h2>${!ordered&&t.note?`<p class="rw-deck">${E(t.note)}</p>`:''}</header>${diagram}${editorial}</section>`;
}
