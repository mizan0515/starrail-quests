import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import originalCatalog from '../../data/catalog.json';
import versionEvidence from '../../editorial/mission-versions.json';
import aliases from '../../data/aliases.json';
import resolvedTopics from '../../data/topics.json';
import editedTopics from '../../editorial/topics.json';
import stats from '../../data/stats.json';
import dialogueSupplements from '../../data/mission-dialogue-supplements.json';
import videoCaptions from '../../data/official-video-captions.json';
import timelineDialogue from '../../data/timeline-mission-dialogue.json';
import {partitionMissionSections,missionRowLinked} from './mission-scope.mjs';
const missionPartIds=Object.fromEntries(originalCatalog.filter(d=>d.category==='퀘스트').map(d=>{const original=JSON.parse(fs.readFileSync(path.resolve('data/documents',d.id+'.json'),'utf8'));return [d.id,(original.missionParts||[d.id]).map(id=>id.replace(/^quest-/,''))];})) as Record<string,string[]>;
const captionScenes:Record<string,any[]>={};
for(const [id,scenes] of Object.entries(videoCaptions.missions)){
 const target=aliases[id]||id;
 if(!missionPartIds[target]?.includes(id.replace(/^quest-/,'')))throw Error('Caption owner is not a preserved mission part: '+id);
 (captionScenes[target]??=[]).push(...scenes);
}
export const missionDialogue=Object.fromEntries([...new Set([...Object.keys(dialogueSupplements.missions),...Object.keys(captionScenes),...Object.keys(timelineDialogue.missions)])].map(id=>[id,[...(dialogueSupplements.missions[id]||[]),...(captionScenes[id]||[]),...(timelineDialogue.missions[id]||[])]])) as Record<string,any[]>;
export const missionCoverage=(dialogueSupplements as any).coverage as Record<string,any>;
export const missionStructureUrl=(source:string)=>`https://github.com/${dialogueSupplements.evidence.repository}/blob/${dialogueSupplements.evidence.commit}/${source}`;
export const missionPassageKind=(row:any):'gap'|'choice'|'dialogue'|'caption'=>row.label==='대사 누락'||typeof row.text!=='string'||!row.text.trim()||(row.text==='한국어 본문 미수록'&&row.hash===''&&/^MessageItemConfig:\d+\.(?:MainText|OptionText)$/.test(row.source||''))?'gap':row.officialCaptionSource?'caption':row.label==='선택지'||row.displayKind==='choice'||row.displayKind==='선택지'?'choice':'dialogue';
// This exact source row is an authoring notice reused by two original Acts.
export const missionSourceNotice=(row:any)=>String(row.talk_id)==='999999999'&&row.text==='스토리 및 연출 콘텐츠는 제작 중입니다, 기대해주세요!';
export const missionSectionLinked=(id:string,section:any)=>{
 return section.rows.every(row=>missionRowLinked(section,row,{...missionCoverage[id],missionIds:missionPartIds[id]}));
};
export const missionSections=(id:string,sections:any[])=>partitionMissionSections(sections,{...missionCoverage[id],missionIds:missionPartIds[id]});
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
 const {primary:linked,reference}=missionSections(d.id,sections);
 const rows=linked.flatMap(s=>s.rows),choiceCount=rows.filter(r=>missionPassageKind(r)==='choice').length,gapCount=rows.filter(r=>missionPassageKind(r)==='gap').length,captionCount=rows.filter(r=>missionPassageKind(r)==='caption').length,dialogueCount=rows.length-choiceCount-gapCount-captionCount;
 return [d.id,{dialogueCount,choiceCount,gapCount,captionCount,sceneCount:linked.filter(s=>s.rows.length).length,referenceRows:reference.reduce((n,s)=>n+s.rows.length,0),referenceSceneCount:reference.filter(s=>s.rows.length).length,messageRows:(missionMessages[d.id]||[]).reduce((n,s)=>n+s.rows.length,0),state:dialogueCount?'dialogue-linked':captionCount?'captions-linked':choiceCount?'choices-only':'overview-only'}];
})) as Record<string,{dialogueCount:number,choiceCount:number,gapCount:number,captionCount:number,sceneCount:number,referenceRows:number,referenceSceneCount:number,messageRows:number,state:string}>;
const versionMap=versionEvidence.missions as Record<string,string>;
// Keep the original resolved citations while consuming the editorial text directly.
const topics=resolvedTopics.map(topic=>{
 const edited=editedTopics.find(item=>item.id===topic.id);
 if(!edited||edited.sections.length!==topic.sections.length)throw new Error(`Topic structure mismatch: ${topic.id}`);
 if(edited.relations.length!==edited.relationEvidence.length)throw new Error(`Topic relation evidence mismatch: ${topic.id}`);
 return {...topic,title:edited.title,deck:edited.deck,caution:edited.caution,relations:edited.relations,relationEvidence:edited.relationEvidence,sections:topic.sections.map((section,index)=>({...section,title:edited.sections[index].title,text:edited.sections[index].text}))};
});
const partVersions=new Map<string,Set<string>>();
for(const [id,parent] of Object.entries(aliases)){if(versionMap[id]){if(!partVersions.has(parent))partVersions.set(parent,new Set());partVersions.get(parent)!.add(versionMap[id]);}}
export const displayMissionTitle=(d:any)=>{
 if(d.category!=='퀘스트'||!/^quest-\d+$/.test(d.id))return d.title;
 const fallback=`임무 ${d.id.slice(6)} · 제목 미확인`;
 if(typeof d.title!=='string'||!d.title.trim())return fallback;
 if(d.title==='한국어 본문 미수록'){
  const titleHash=d.title_hash===undefined?JSON.parse(fs.readFileSync(path.resolve('data/documents',d.id+'.json'),'utf8')).title_hash:d.title_hash;
  if(titleHash==='')return fallback;
 }
 return d.title;
};
export const catalog=originalCatalog.map(d=>{const observed=d.category==='퀘스트'?[...new Set([versionMap[d.id]||'unknown',...(partVersions.get(d.id)||[])])]:[];const addedDialogue=(missionDialogue[d.id]||[]).reduce((count,s)=>count+s.rows.length,0);return {...d,title:displayMissionTitle(d),count:d.count+addedDialogue+(missionReading[d.id]?.messageRows||0),addedDialogue,...missionReading[d.id],versions:[...observed,...(observed.some(v=>/^\d+\.\d+$/.test(v)&&Number(v)<=2.6)?['early']:[])]};});
export const readingCatalogVersion=createHash('sha256').update(JSON.stringify(catalog)).digest('hex').slice(0,12);
export {topics,stats,versionEvidence};
export const versionLabel=(v:string)=>v==='early'?'1.0~2.6':v==='unknown'?'버전 미확인':v;
export const versions=[...new Set(catalog.flatMap(d=>d.versions))].sort((a,b)=>a==='early'?1:b==='early'?-1:a==='unknown'?1:b==='unknown'?-1:b.localeCompare(a,undefined,{numeric:true}));
export const kinds={main:'개척 임무',continuance:'개척 후문',companion:'동행 임무',adventure:'모험 임무',daily:'일일 임무'};
export const href=(p:string)=>`${import.meta.env.BASE_URL.replace(/\/$/,'')}/${p}`;
export const doc=(id:string)=>{const original=JSON.parse(fs.readFileSync(path.resolve('data/documents',id+'.json'),'utf8'));return {...original,title:displayMissionTitle(original)};};
export const docUrl=(id:string)=>href('문서/'+id+'.html');
export const topicUrl=(id:string)=>href('설정/'+id+'.html');
