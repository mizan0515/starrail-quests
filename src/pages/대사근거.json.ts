import {dialogueData} from '../lib/explorer';
export function GET(){return new Response(JSON.stringify(dialogueData.evidence),{headers:{'Content-Type':'application/json; charset=utf-8'}});}
