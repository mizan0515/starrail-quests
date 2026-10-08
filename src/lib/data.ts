import fs from 'node:fs';
import path from 'node:path';
import originalCatalog from '../../data/catalog.json';
import versionEvidence from '../../editorial/mission-versions.json';
import aliases from '../../data/aliases.json';
import resolvedTopics from '../../data/topics.json';
import editedTopics from '../../editorial/topics.json';
import stats from '../../data/stats.json';
import dialogueSupplements from '../../data/mission-dialogue-supplements.json';
export const missionDialogue=dialogueSupplements.missions as Record<string,any[]>;
export const missionCoverage=(dialogueSupplements as any).coverage as Record<string,any>;
export const missionStructureUrl=(source:string)=>`https://github.com/${dialogueSupplements.evidence.repository}/blob/${dialogueSupplements.evidence.commit}/${source}`;
export const missionPassageKind=(row:any):'gap'|'choice'|'dialogue'=>row.label==='대사 누락'||typeof row.text!=='string'||!row.text.trim()||(row.text==='한국어 본문 미수록'&&row.hash===''&&/^MessageItemConfig:\d+\.(?:MainText|OptionText)$/.test(row.source||''))?'gap':row.label==='선택지'||row.displayKind==='choice'||row.displayKind==='선택지'?'choice':'dialogue';
export const missionSectionLinked=(id:string,section:any)=>{
 const chain=section.relatedDocument?.ownership||missionCoverage[id]?.sourceOwnership?.[section.source]||section.ownership;
 return chain?.[0]?.kind==='EXPLICIT_MAIN_MISSION_ID';
};
export const missionMessages=Object.fromEntries(Object.entries(missionCoverage).map(([id,coverage])=>{
 const references=new Map<string,any>();
 for(const ref of coverage.relatedDocuments||[]){const previous=references.get(ref.id);if(!previous||(previous.ownership?.[0]?.kind!=='EXPLICIT_MAIN_MISSION_ID'&&ref.ownership?.[0]?.kind==='EXPLICIT_MAIN_MISSION_ID'))references.set(ref.id,ref);}
 return [id,[...references.values()].flatMap((ref:any)=>{
 const document=JSON.parse(fs.readFileSync(path.resolve('data/documents',ref.id+'.json'),'utf8'));
 return document.sections.map(s=>({...s,anchor:`mission-message-${document.id}-${s.anchor}`,sourceTitle:document.title,relatedDocument:ref,originalDocumentUrl:document.url}));
 })];})) as Record<string,any[]>;
export const missionReading=Object.fromEntries(originalCatalog.filter(d=>d.category==='퀘스트').map(d=>{
 const original=JSON.parse(fs.readFileSync(path.resolve('data/documents',d.id+'.json'),'utf8'));
 const sections=[...original.sections,...(missionDialogue[d.id]||[]),...(missionMessages[d.id]||[])];
 const linked=sections.filter(s=>missionSectionLinked(d.id,s)),reference=sections.filter(s=>!missionSectionLinked(d.id,s));
 const rows=linked.flatMap(s=>s.rows),choiceCount=rows.filter(r=>missionPassageKind(r)==='choice').length,gapCount=rows.filter(r=>missionPassageKind(r)==='gap').length,dialogueCount=rows.length-choiceCount-gapCount;
 return [d.id,{dialogueCount,choiceCount,gapCount,sceneCount:linked.filter(s=>s.rows.length).length,referenceRows:reference.reduce((n,s)=>n+s.rows.length,0),referenceSceneCount:reference.filter(s=>s.rows.length).length,messageRows:(missionMessages[d.id]||[]).reduce((n,s)=>n+s.rows.length,0),state:dialogueCount?'dialogue-linked':choiceCount?'choices-only':'overview-only'}];
})) as Record<string,{dialogueCount:number,choiceCount:number,gapCount:number,sceneCount:number,referenceRows:number,referenceSceneCount:number,messageRows:number,state:string}>;
const versionMap=versionEvidence.missions as Record<string,string>;
// Keep the original resolved citations while consuming the editorial text directly.
const topics=resolvedTopics.map(topic=>{
 const edited=editedTopics.find(item=>item.id===topic.id);
 if(!edited||edited.sections.length!==topic.sections.length)throw new Error(`Topic structure mismatch: ${topic.id}`);
 return {...topic,title:edited.title,deck:edited.deck,caution:edited.caution,sections:topic.sections.map((section,index)=>({...section,title:edited.sections[index].title,text:edited.sections[index].text}))};
});
const partVersions=new Map<string,Set<string>>();
for(const [id,parent] of Object.entries(aliases)){if(versionMap[id]){if(!partVersions.has(parent))partVersions.set(parent,new Set());partVersions.get(parent)!.add(versionMap[id]);}}
export const catalog=originalCatalog.map(d=>{const observed=d.category==='퀘스트'?[...new Set([versionMap[d.id]||'unknown',...(partVersions.get(d.id)||[])])]:[];const addedDialogue=(missionDialogue[d.id]||[]).reduce((count,s)=>count+s.rows.length,0);return {...d,count:d.count+addedDialogue+(missionReading[d.id]?.messageRows||0),addedDialogue,...missionReading[d.id],versions:[...observed,...(observed.some(v=>/^\d+\.\d+$/.test(v)&&Number(v)<=2.6)?['early']:[])]};});
export {topics,stats,versionEvidence};
export const versionLabel=(v:string)=>v==='early'?'1.0~2.6':v==='unknown'?'버전 미확인':v;
export const versions=[...new Set(catalog.flatMap(d=>d.versions))].sort((a,b)=>a==='early'?1:b==='early'?-1:a==='unknown'?1:b==='unknown'?-1:b.localeCompare(a,undefined,{numeric:true}));
export const kinds={main:'개척 임무',continuance:'개척 후문',companion:'동행 임무',adventure:'모험 임무',daily:'일일 임무'};
export const href=(p:string)=>`${import.meta.env.BASE_URL.replace(/\/$/,'')}/${p}`;
export const doc=(id:string)=>JSON.parse(fs.readFileSync(path.resolve('data/documents',id+'.json'),'utf8'));
export const docUrl=(id:string)=>href('문서/'+id+'.html');
export const topicUrl=(id:string)=>href('설정/'+id+'.html');
