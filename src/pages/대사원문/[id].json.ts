import fs from 'node:fs';import path from 'node:path';import {dialogueData} from '../../lib/explorer';
export function getStaticPaths(){return dialogueData.pages.map(p=>({params:{id:p.id}}));}
export function GET({params}){return new Response(fs.readFileSync(path.resolve('data/dialogues',params.id+'.json'),'utf8'),{headers:{'Content-Type':'application/json; charset=utf-8'}});}
