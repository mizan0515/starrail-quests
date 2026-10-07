import {catalog} from '../lib/data';
export function GET(){return new Response(JSON.stringify(Object.fromEntries(catalog.filter(d=>d.category==='퀘스트').map(d=>[d.id,d.versions]))),{headers:{'Content-Type':'application/json; charset=utf-8'}});}
