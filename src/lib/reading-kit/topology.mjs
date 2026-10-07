export function validateTopology(t,hasClaim=()=>true){
 if(!t.nodes?.length||!t.edges?.length)throw Error('Topology needs nodes and edges');
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
 return {id,title,nodes:[...nodes.values()].map(n=>({...n,focus:n.id===focusId})),edges:relations.map(r=>({id:r.id,from:r.from.id,to:r.to.id,label:r.label,claimId:r.reasonClaimId,reason:r.reason,evidence:r.evidence,kind:'relation',claimKind:r.kind}))};
}
export function renderTopology(t,{escape,href,inline,evidence}){
 validateTopology(t);const E=escape,layers=Math.max(...t.nodes.map(n=>n.layer))+1;
 const group=Array.from({length:layers},(_,i)=>t.nodes.filter(n=>n.layer===i));const height=Math.max(260,...group.map(g=>g.length*160+40));
 const positions=new Map();for(const [i,g]of group.entries())for(const [j,n]of g.entries())positions.set(n.id,{x:(i+.5)/layers*1000,y:(j+.5)/g.length*height});
 const marker='arrow-'+String(t.id).replace(/[^a-zA-Z0-9_-]/g,'-');
 const paths=t.edges.map(e=>{const a=positions.get(e.from),b=positions.get(e.to),half=500/layers-17,back=e.kind==='return';let d;
 if(back)d=`M ${a.x} ${a.y+65} C ${a.x} ${height-5}, ${b.x} ${height-5}, ${b.x} ${b.y+65}`;
 else {const x=a.x+half,y=b.x-half,mid=(x+y)/2;d=`M ${x} ${a.y} C ${mid} ${a.y}, ${mid} ${b.y}, ${y} ${b.y}`;}
 return `<path d="${d}" class="${back?'rw-back-edge':''}" marker-end="url(#${marker})"/>`;}).join('');
 const name=id=>t.nodes.find(n=>n.id===id).name;
 const nodes=t.nodes.map(n=>{const p=positions.get(n.id),incoming=t.edges.filter(e=>e.to===n.id);return `<div class="rw-map-node${n.focus?' rw-map-focus':''}${n.scale?' rw-map-'+E(n.scale):''}${n.form==='plural'?' rw-map-plural':''}" style="--x:${p.x/10}%;--y:${p.y/height*100}%;--node-width:${100/layers}%" data-node="${E(n.id)}"><small>${E(n.kind||'')}</small>${n.url?`<a data-reading-link href="${href(n.url)}">${E(n.name)}</a>`:`<strong>${E(n.name)}</strong>`}${incoming.map(e=>`<a class="rw-map-incoming" href="#${E(t.id)}-edge-${E(e.id)}" data-reading-link>${E(name(e.from))} <span aria-hidden="true">→</span> ${E(e.label)}</a>`).join('')}${n.detail?`<p>${E(n.detail)}</p>`:''}</div>`;}).join('');
 const edges=t.edges.map(e=>`<details class="rw-map-evidence" id="${E(t.id)}-edge-${E(e.id)}"><summary>${E(name(e.from))} <span aria-hidden="true">→</span> ${E(e.label)} <span aria-hidden="true">→</span> ${E(name(e.to))}</summary>${e.claimKind==='inference'?'<span class="rw-attribution">편집자의 연결</span>':''}<p>${inline(e.reason||e.text||e.label)}</p>${evidence(e.evidence||[])}</details>`).join('');
 return `<section class="rw-map" id="${E(t.id)}"><header><h2>${E(t.title)}</h2>${t.note?`<p class="rw-deck">${E(t.note)}</p>`:''}</header><div class="rw-map-canvas" style="--map-height:${height}px"><svg viewBox="0 0 1000 ${height}" preserveAspectRatio="none" aria-hidden="true" focusable="false"><defs><marker id="${marker}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z"/></marker></defs>${paths}</svg>${nodes}</div>${t.scaleNote?`<p class="rw-scale-note">${E(t.scaleNote)}</p>`:''}<div class="rw-map-sources">${edges}</div></section>`;
}
