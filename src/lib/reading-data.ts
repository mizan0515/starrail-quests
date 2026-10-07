import graph from '../../public/reading-data/graph.json';
import {resolveCluster} from './reading-kit/graph.mjs';
import {createReadingKit,escapeHtml} from './reading-kit/render.mjs';
export const readingGraph=graph;
export const readingCluster=(id:string)=>resolveCluster(graph,'atlas/'+id);
export const readingKit=createReadingKit({evidence:items=>items.map(e=>`<blockquote>${escapeHtml(e.quote)}</blockquote><a href="${escapeHtml(e.url)}" data-reading-link>${escapeHtml(e.title)} ↗</a>`).join('')});
export const readingClaim=(id:string)=>{const claim=graph.claims.find(c=>c.id===id)!;return {...claim,evidence:claim.evidenceIds.map(id=>graph.evidence.find(e=>e.id===id))};};
