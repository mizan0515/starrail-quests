import fs from 'node:fs';
import path from 'node:path';
import discoveryRegistry from '../../editorial/directory-discovery.json';
import {applySourceIdentities} from './source-identities.mjs';
import handbook from '../../data/handbook-originals.json';
import {extendExplorer} from './handbook-originals.mjs';
// Preserve the exact source token for 64-bit hashes in older datasets.
const preservedDataset=JSON.parse(fs.readFileSync(path.resolve('data/explorer.json'),'utf8'),(_key:string,value:any,context?:{source:string})=>typeof value==='number'&&!Number.isSafeInteger(value)?context!.source:value);
const dataset=extendExplorer(applySourceIdentities(preservedDataset,discoveryRegistry.identities),handbook);
import dialogueData from '../../data/dialogue-index.json';
import {href,docUrl} from './data';
export {dataset,dialogueData};
export const axes=[{id:'region',name:'지역',question:'역사·장소·생활의 기록',count:dataset.counts.region},{id:'person',name:'인물',question:'과거·행적·발언과 이야기',count:dataset.counts.person},{id:'concept',name:'세계관',question:'우주·세력·법칙과 지역의 개념',count:dataset.counts.concept},{id:'aeon',name:'에이언즈',question:'운명의 길과 신들의 기록',count:dataset.counts.aeon}];
export const entityUrl=(e:any)=>e.axis==='concept'?docUrl(e.id):href('대상/'+e.id+'.html');
export const dialogueUrl=(id:string)=>href('대사/'+id+'.html');
