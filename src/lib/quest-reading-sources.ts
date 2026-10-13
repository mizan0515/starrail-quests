import fs from 'node:fs';
import path from 'node:path';
import {deepScenes, timelineRows} from './deep-timeline.ts';

export type ReadingSource = {
 id:string; title:string; url:string; kind:string; missions:string[];
 occurrences:number; roles:Record<string,number>;
};
const read=(file:string)=>JSON.parse(fs.readFileSync(path.resolve(file),'utf8'));
const quests=new Map<string,any>(read('data/catalog.json').filter((d:any)=>d.category==='퀘스트').map((d:any)=>[d.id,d]));
const versions=read('data/versioned-timeline-text.json');
const labels:Record<string,string>={HASH_ONLY_SCREEN_TEXT:'화면 문구',LUA_ARGUMENT_SCREEN_TEXT:'화면 문구',NATIVE_CHOICES:'선택지',FRESH_NATIVE_TIMELINE:'연출 원문',PUBLIC_JSON_TIMELINE:'연출 원문'};

// Metadata only. Bodies, original anchors and the append-only scene catalogue stay in their readers.
export function sceneReadingSource(scene:any):ReadingSource {
 const rows=timelineRows(scene), roles:Record<string,number>={};
 for(const row of rows){const role=row.role||(['HASH_ONLY_SCREEN_TEXT','LUA_ARGUMENT_SCREEN_TEXT'].includes(scene.kind)?'SCREEN_TEXT':'SPOKEN');roles[role]=(roles[role]||0)+1;}
 return {id:scene.id,title:scene.title,url:'대화/연출-'+scene.id+'.html',kind:labels[scene.kind]||'연출 원문',
  missions:[...new Set<string>(scene.owners.map((o:any)=>o.canonicalMission))].filter(id=>quests.has(id)),occurrences:rows.length,roles};
}
export const readingSources:ReadingSource[]=[...deepScenes.map(sceneReadingSource),...versions.records.map((record:any)=>({
 id:record.id,title:record.title,url:record.url,kind:'판본 비교',missions:quests.has(record.proof.owner.mission)?[record.proof.owner.mission]:[],
 occurrences:2,roles:{VERSION_COMPARISON_REFERENCE:2},
}))];
const byUrl=new Map(readingSources.map(source=>['/'+source.url,source]));
const byMission=new Map<string,ReadingSource[]>();
for(const source of readingSources)for(const id of source.missions){const sources=byMission.get(id)||[];sources.push(source);byMission.set(id,sources);}
export const questReadingSources=(id:string)=>byMission.get(id)||[];
export const questReadingTitle=(id:string)=>quests.get(id)?.title;
export function groupReadingSources(sources:ReadingSource[]){
 const groups=new Map<string,ReadingSource[]>();
 for(const source of sources){const list=groups.get(source.kind)||[];list.push(source);groups.set(source.kind,list);}
 return [...groups].map(([kind,records])=>({kind,records,occurrences:records.reduce((n,r)=>n+r.occurrences,0)}));
}
export function nearbyReadingSources(sources:ReadingSource[],currentUrl:string,limit=8){
 const index=sources.findIndex(source=>source.url===currentUrl);
 const start=index<0?0:Math.max(0,Math.min(index-Math.floor(limit/2),sources.length-limit));
 return sources.slice(start,start+limit);
}
export function readingSourceRoute(route:string){
 const source=byUrl.get(route);
 if(source)return {title:source.title,kind:source.kind,url:source.url,missions:source.missions};
 const mission=route.match(/^\/문서\/(quest-[0-9]+)\.html$/)?.[1];
 if(mission&&quests.has(mission))return {title:questReadingTitle(mission),kind:'임무',url:route.slice(1),missions:[mission]};
 if(/^\/(?:문서|대사|대상|맥락)\/[^/]+\.html$/.test(route)||/^\/대화\/(?:context-[0-9a-f]{16}|범위-range-[0-9a-f]{16})\.html$/.test(route))
  return {title:'현재 원문',kind:route.includes('/범위-')?'설정 범위 참조':'원문',url:route.slice(1),missions:[]};
 return null;
}
export function readingRoleSummary(source:ReadingSource){
 const labels:Record<string,string>={SPOKEN:'대사',SCREEN_TEXT:'화면 문구',NATIVE_CHOICE:'선택지',NON_SPOKEN_OPTION_REFERENCE:'선택지 참조',VERSION_COMPARISON_REFERENCE:'판본 원문'};
 return Object.entries(source.roles).map(([role,count])=>`${labels[role]||'원문'} ${count.toLocaleString('ko-KR')}`).join(' · ');
}
