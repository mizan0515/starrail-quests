import fs from 'node:fs';
import path from 'node:path';
import originalCatalog from '../../data/catalog.json';
import versionEvidence from '../../editorial/mission-versions.json';
import aliases from '../../data/aliases.json';
import resolvedTopics from '../../data/topics.json';
import editedTopics from '../../editorial/topics.json';
import stats from '../../data/stats.json';
const versionMap=versionEvidence.missions as Record<string,string>;
// Keep the original resolved citations while consuming the editorial text directly.
const topics=resolvedTopics.map(topic=>{
 const edited=editedTopics.find(item=>item.id===topic.id);
 if(!edited||edited.sections.length!==topic.sections.length)throw new Error(`Topic structure mismatch: ${topic.id}`);
 return {...topic,title:edited.title,deck:edited.deck,caution:edited.caution,sections:topic.sections.map((section,index)=>({...section,title:edited.sections[index].title,text:edited.sections[index].text}))};
});
const partVersions=new Map<string,Set<string>>();
for(const [id,parent] of Object.entries(aliases)){if(versionMap[id]){if(!partVersions.has(parent))partVersions.set(parent,new Set());partVersions.get(parent)!.add(versionMap[id]);}}
export const catalog=originalCatalog.map(d=>({...d,versions:d.category==='퀘스트'?[...new Set([versionMap[d.id]||'unknown',...(partVersions.get(d.id)||[])])]:[]}));
export {topics,stats,versionEvidence};
export const versionLabel=(v:string)=>v==='early'?'2.6 및 이전 · 세부 버전 미확인':v==='unknown'?'버전 미확인':v;
export const versions=[...new Set(catalog.flatMap(d=>d.versions))].sort((a,b)=>a==='early'?1:b==='early'?-1:a==='unknown'?1:b==='unknown'?-1:b.localeCompare(a,undefined,{numeric:true}));
export const kinds={main:'개척 임무',continuance:'개척 후문',companion:'동행 임무',adventure:'모험 임무',daily:'일일 임무'};
export const href=(p:string)=>`${import.meta.env.BASE_URL.replace(/\/$/,'')}/${p}`;
export const doc=(id:string)=>JSON.parse(fs.readFileSync(path.resolve('data/documents',id+'.json'),'utf8'));
export const docUrl=(id:string)=>href('문서/'+id+'.html');
export const topicUrl=(id:string)=>href('설정/'+id+'.html');
