import fs from 'node:fs';
import path from 'node:path';
const deepTimeline=JSON.parse(fs.readFileSync(path.resolve('data/deep-timeline-dialogue.json'),'utf8'));
const attribution=JSON.parse(fs.readFileSync(path.resolve('data/deep-dialogue-attribution.json'),'utf8'));
const sdfTimeline=JSON.parse(fs.readFileSync(path.resolve('data/sdf-timeline-text.json'),'utf8'));
const originals=new Map<string,any>();
function original(reference:any){
 if(!originals.has(reference.file))originals.set(reference.file,JSON.parse(fs.readFileSync(path.resolve(reference.file),'utf8')));
 let row=originals.get(reference.file);
 for(const token of reference.pointer.split('/').slice(1)){const key=token.replaceAll('~1','/').replaceAll('~0','~');row=row[key];}
 return row;
}
export const deepRows=(scene:any)=>scene.kind==='HASH_ONLY_SCREEN_TEXT'?scene.rows.map((row:any)=>({...row,speaker:'화면 문구',isChoice:false})):scene.rows.map((reference:any)=>{
 const proof=deepTimeline.joins[String(reference.talkId)];
 const row=original(proof.preservedSource);
 return {...row,deepReference:reference,deepKoreanProof:proof,isChoice:['NON_SPOKEN_OPTION_REFERENCE','NATIVE_CHOICE'].includes(reference.role),url:'대사/'+path.basename(proof.preservedSource.file,'.json')+'.html#talk-'+reference.talkId};
});
export const deepScenes=[...deepTimeline.scenes,...sdfTimeline.scenes];
export const deepCounts={scenes:deepScenes.length,rows:deepTimeline.counts.rows+sdfTimeline.counts.rows};
export const deepMissionScenes=new Map<string,any[]>();
for(const scene of deepScenes)for(const mission of new Set(scene.owners.map(owner=>owner.canonicalMission))){const list=deepMissionScenes.get(mission)||[];list.push(scene);deepMissionScenes.set(mission,list);}
export {deepTimeline,attribution as deepAttribution};
