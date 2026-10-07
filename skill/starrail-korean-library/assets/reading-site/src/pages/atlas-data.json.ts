import {atlas,atlasUrl,evidenceUrl} from '../lib/atlas';
export function GET(){return new Response(JSON.stringify(Object.fromEntries(atlas.nodes.map(n=>[n.id,{name:n.name,question:n.question,intro:n.intro,url:atlasUrl(n.id),evidence:n.evidence.map(e=>({...e,url:evidenceUrl(e)}))}]))),{headers:{'Content-Type':'application/json; charset=utf-8'}});}
