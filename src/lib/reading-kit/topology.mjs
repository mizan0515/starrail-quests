export function validateTopology(t,hasClaim=()=>true){
 if(!t.nodes?.length||!t.edges?.length)throw Error('Topology needs nodes and edges');
 if(t.presentation!==undefined&&t.presentation!=='relations')throw Error('Unknown topology presentation');
 if(t.layout!==undefined&&!['relations','cycle'].includes(t.layout))throw Error('Unknown source topology layout');
 if(t.layout==='cycle'&&!t.edges.some(e=>e.kind==='return'))throw Error('Cycle layout requires a source return relation');
 const ids=new Set();for(const n of t.nodes){if(ids.has(n.id))throw Error('Duplicate topology node');ids.add(n.id);if(!n.name||!Number.isInteger(n.layer)||n.layer<0||n.layer>3)throw Error('Invalid topology node');if(n.scale&&!t.scaleNote)throw Error('Relative scale needs a scope note');}
 const edgeIds=new Set();for(const e of t.edges){if(!e.id||edgeIds.has(e.id))throw Error('Duplicate or missing topology edge');edgeIds.add(e.id);if(!ids.has(e.from)||!ids.has(e.to)||!e.label||!e.claimId||!hasClaim(e.claimId))throw Error('Invalid topology edge or evidence');if(!['relation','sequence','return'].includes(e.kind||'relation'))throw Error('Invalid topology edge kind');}
 return t;
}
export function topologyFromRelations(relations,{id='relationships',title='관계 한눈에',focusId}={}){
 if(!relations.length)return null;
 const nodes=new Map();for(const r of relations)for(const n of [r.from,r.to])nodes.set(n.id,{...n,layer:0});
 const indegree=new Map([...nodes.keys()].map(id=>[id,0]));for(const r of relations)indegree.set(r.to.id,indegree.get(r.to.id)+1);
 const queue=[...nodes.keys()].filter(id=>!indegree.get(id));let visited=0;
 for(let i=0;i<queue.length;i++){const id=queue[i];visited++;for(const r of relations.filter(r=>r.from.id===id)){nodes.get(r.to.id).layer=Math.max(nodes.get(r.to.id).layer,Math.min(3,nodes.get(id).layer+1));indegree.set(r.to.id,indegree.get(r.to.id)-1);if(!indegree.get(r.to.id))queue.push(r.to.id);}}
 if(visited!==nodes.size)for(const n of nodes.values())n.layer=n.id===focusId?0:1;
 return {id,title,presentation:'relations',nodes:[...nodes.values()].map(n=>({...n,focus:n.id===focusId})),edges:relations.map(r=>({id:r.id,from:r.from.id,to:r.to.id,label:r.label,claimId:r.reasonClaimId,reason:r.reason,evidence:r.evidence,kind:'relation',claimKind:r.claimKind||r.kind,speaker:r.speaker||''}))};
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
 const html=renderCvaModule({id:moduleId(t.id,batch),type:'scene-composition',variant:'relationship-ledger',props:{title:'',body:'',relationLabel:'주체 → 관계 → 대상',caption:''},items:batch.map((e,j)=>({id:'relation-'+j,title:name(e.from)+' → '+name(e.to),body:e.reason||e.text||e.label,label:attribution(e)})),itemTitles:batch.map(statement),itemExtras:batch.map(e=>`<div class="rw-relation-band" aria-label="${E(name(e.from)+' → '+e.label+' → '+name(e.to))}" data-relation-from="${E(e.from)}" data-relation-to="${E(e.to)}">${proof(e)}</div>`)});
 return html.replace('<caption>입력한 항목과 관계의 기록</caption>','<caption>각 관계의 주체와 대상 · 출처에서 확인하기</caption>').replace('<th scope="col">대상</th>','<th scope="col">주체 · 관계 · 대상</th>').replace('<th scope="col">명시한 라벨·값</th>','<th scope="col">원문의 성격</th>').replace('<th scope="col">설명</th>','<th scope="col">맥락과 근거</th>');
 }).join('');
 const path=verifiedPath(t),cycle=verifiedCycle(t),ordered=path||cycle?.nodes;
 let diagram='';
 if(ordered&&ordered.length<=24&&!connections.length){
 const incoming=n=>(cycle?.edges||t.edges).filter(e=>e.to===n.id);
 diagram=renderCvaModule({id:moduleId(t.id+'-structure',ordered),type:'scene-composition',variant:cycle?'feedback-ring':'quest-route',props:{title:'',body:t.note||'',relationLabel:cycle?'원문에 설명된 순환 · 각 연결의 발언 주체와 근거':'원문에 명시된 과정의 순서',caption:t.scaleNote||''},items:ordered.map((n,i)=>({id:'node-'+i,title:n.name,body:n.detail||'',label:n.kind||''})),itemTitles:ordered.map(endpoint),itemExtras:ordered.map(n=>incoming(n).map(e=>`<div class="rw-structure-edge">${statement(e)}${proof(e)}</div>`).join(''))});
 if(cycle?.external.length)diagram+=relationModules(cycle.external);
 } else diagram=relationModules(explicit);
 const editorial=connections.length?`<div class="rw-reading-connections">${Array.from({length:Math.ceil(connections.length/24)},(_,i)=>{const batch=connections.slice(i*24,(i+1)*24);return renderCvaModule({id:moduleId(t.id+'-reading',batch),type:'cards',variant:'list',props:{title:'',body:''},items:batch.map((e,j)=>({id:'connection-'+j,title:name(e.to),body:e.reason||e.text||e.label,label:'편집자의 연결 · '+name(e.from)+'에서 이어 읽기'})),itemTitles:batch.map(e=>endpoint(nodes.get(e.to))),itemExtras:batch.map(e=>`<div class="rw-reading-connection"><div class="rw-connection-origin">${endpoint(nodes.get(e.from))}</div><p>${E(e.label)}</p>${proof(e)}</div>`)});}).join('')}</div>`:'';
 return `<section class="rw-map rw-cva-atlas rw-app not-content" id="${E(t.id)}"><header><span class="rw-attribution">관계 표현 · 원문에 근거해 편집</span><h2>${E(t.title==='관계 한눈에'&&!explicit.length?'함께 읽을 설정':t.title)}</h2>${!ordered&&t.note?`<p class="rw-deck">${E(t.note)}</p>`:''}</header>${diagram}${editorial}</section>`;
}
