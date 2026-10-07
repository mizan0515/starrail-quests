import graph from '../../public/reading-data/graph.json';
import {resolveCluster} from './reading-kit/graph.mjs';
import {createReadingKit,escapeHtml} from './reading-kit/render.mjs';
export const readingGraph=graph;
const entityLabels:Record<string,string>={region:'지역',person:'인물',concept:'개념',bridge:'세력·종족',aeon:'에이언즈'};
export const readingCluster=(id:string)=>{
 const cluster=resolveCluster(graph,'atlas/'+id);
 const label=entity=>({...entity,kind:entityLabels[entity.kind]||entity.kind});
 return {...cluster,relations:cluster.relations.map(relation=>({...relation,from:label(relation.from),to:label(relation.to)}))};
};
export const readingKit=createReadingKit({evidence:items=>items.map(e=>`<blockquote>${escapeHtml(e.quote)}</blockquote><a href="${escapeHtml(e.url)}" data-reading-link>${escapeHtml(e.title)} ↗</a>`).join('')});
export const readingClaim=(id:string)=>{const claim=graph.claims.find(c=>c.id===id)!;return {...claim,evidence:claim.evidenceIds.map(id=>graph.evidence.find(e=>e.id===id))};};
