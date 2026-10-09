import fs from 'node:fs';import path from 'node:path';import {createReadingGraph} from '../src/lib/reading-kit/graph.mjs';
import {writeReadingGraph} from '../src/lib/reading-kit/write.mjs';
import {pathToFileURL} from 'node:url';
import {atlasComparison} from '../src/lib/atlas-comparison.mjs';
export function claimAttribution(item,evidence){
 const speaker=item.speaker||[...new Set(evidence.map(e=>e.speaker||(e.status==='원문 서술'?'':e.status)).filter(Boolean))].join(' · ');
 return {kind:item.status?.includes('편집')?'inference':speaker?'attributed':'explicit',speaker};
}
export function relationEndpoints(contextId,relation){
 const direction=relation.direction??'outgoing';
 if(!['incoming','outgoing'].includes(direction))throw Error('Unknown relation direction '+direction);
 if(!contextId||typeof relation.target!=='string'||!relation.target||contextId===relation.target)throw Error('Invalid relation endpoint');
 return direction==='incoming'?{from:relation.target,to:contextId}:{from:contextId,to:relation.target};
}
export async function buildReadingGraph(){
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),base='/starrail-quests',atlas=read('editorial/context-atlas.json'),explorer=read('data/explorer.json');
const documents=fs.readdirSync('data/documents').filter(n=>n.endsWith('.json')).map(n=>read('data/documents/'+n));
const sources=documents.map(d=>({id:d.id,title:d.title,kind:d.category,url:base+'/문서/'+d.id+'.html',blocks:d.sections.flatMap(s=>s.rows.map((r,i)=>({id:s.anchor+'-row-'+(i+1),anchor:s.anchor,hash:r.hash,text:r.text,url:base+'/문서/'+d.id+'.html#'+s.anchor+'-row-'+(i+1),locator:{documentId:d.id,section:s.anchor,row:i+1,stringHash:r.hash,talkId:r.talk_id||null}})))}));
const entities=explorer.entries.map(e=>({id:e.id,name:e.name,kind:e.axis,url:base+'/'+(e.axis==='concept'?'문서':'대상')+'/'+e.id+'.html'}));
for(const n of atlas.nodes)if(!entities.some(e=>e.id===n.id))entities.push({id:n.id,name:n.name,kind:n.axis,url:base+'/맥락/'+n.id+'.html'});
const g=createReadingGraph({game:'starrail',sources,entities}),clusters=[],relations=[],events=[];

const refs=es=>es.map(e=>({sourceId:e.id,anchor:e.anchor,hash:e.hash,quote:e.quote,title:e.title,speaker:e.speaker||(e.status==='원문 서술'?'':e.status)||''}));
for(const n of atlas.nodes){const id='atlas/'+n.id;const sections=[{id:'overview',title:n.name+'의 기록',claimIds:n.evidence.map(e=>g.claim(e.quote,refs([e]),claimAttribution(e,[e])))}];for(const [i,r] of n.links.entries())relations.push({id:id+'/relation-'+i,clusterId:id,...relationEndpoints(n.id,r),label:r.verb,kind:claimAttribution(r,[r.evidence]).kind,...(r.structure?{structure:r.structure}:{}),reasonClaimId:g.claim(r.why,refs([r.evidence]),claimAttribution(r,[r.evidence]))});for(const [i,t] of n.timeline.entries())events.push({id:id+'/event-'+i,clusterId:id,title:t.title,when:t.when,claimId:g.claim(t.text,refs([t.evidence]),claimAttribution(t,[t.evidence])),order:i});const topology=n.topology?{...n.topology,edges:n.topology.edges.map(e=>{const {text,evidence,...edge}=e;return {...edge,claimId:g.claim(text,refs(evidence),claimAttribution(e,evidence))};})}:null;const comparison=atlasComparison(atlas,n);clusters.push({id,entityId:n.id,title:n.name,url:base+'/맥락/'+n.id+'.html',question:n.question,overview:n.intro,sections,topology,comparisons:comparison.panels.map(p=>({title:p.label,claimId:g.claim(p.text,refs([p.evidence]),claimAttribution(p,[p.evidence]))})),timeNote:n.timeNote,timeOrdered:n.id!=='bronya',topic:n.topic});}
const graph=g.output({clusters,relations,events});await writeReadingGraph(graph,'public/reading-data');console.log(JSON.stringify({readingGraph:'PASS',sources:sources.length,entities:entities.length,claims:graph.claims.length,evidence:graph.evidence.length,clusters:clusters.length}));

}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href)await buildReadingGraph();
