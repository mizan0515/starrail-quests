import fs from 'node:fs';
import path from 'node:path';
const deepTimeline=JSON.parse(fs.readFileSync(path.resolve('data/deep-timeline-dialogue.json'),'utf8'));
const attribution=JSON.parse(fs.readFileSync(path.resolve('data/deep-dialogue-attribution.json'),'utf8'));
const sdfTimeline=JSON.parse(fs.readFileSync(path.resolve('data/sdf-timeline-text.json'),'utf8'));
const luaTimeline=JSON.parse(fs.readFileSync(path.resolve('data/lua-timeline-dialogue.json'),'utf8'));
const freshTimeline=JSON.parse(fs.readFileSync(path.resolve('data/native-fresh-timeline-dialogue.json'),'utf8'));
const snapshotTimeline=JSON.parse(fs.readFileSync(path.resolve('data/public-snapshot-timeline-dialogue.json'),'utf8'));
export const timelineRows=(scene:any)=>['FRESH_NATIVE_TIMELINE','PUBLIC_JSON_TIMELINE'].includes(scene.kind)?[...scene.rows,...scene.optionReferences].sort((a:any,b:any)=>a.start-b.start||(BigInt(a.track.pathID)<BigInt(b.track.pathID)?-1:BigInt(a.track.pathID)>BigInt(b.track.pathID)?1:0)||a.trackClipIndex-b.trackClipIndex):scene.rows;
const originals=new Map<string,any>();
function original(reference:any){
 if(!originals.has(reference.file))originals.set(reference.file,JSON.parse(fs.readFileSync(path.resolve(reference.file),'utf8')));
 let row=originals.get(reference.file);
 for(const token of reference.pointer.split('/').slice(1)){const key=token.replaceAll('~1','/').replaceAll('~0','~');row=row[key];}
 return row;
}
export const deepRows=(scene:any)=>scene.kind==='HASH_ONLY_SCREEN_TEXT'?scene.rows.map((row:any)=>({...row,speaker:'화면 문구',isChoice:false})):timelineRows(scene).map((reference:any)=>{
 const proof=(scene.kind==='PUBLIC_JSON_TIMELINE'?snapshotTimeline:scene.kind==='FRESH_NATIVE_TIMELINE'?freshTimeline:scene.kind==='LUA_ARGUMENT_SCREEN_TEXT'?luaTimeline:deepTimeline).joins[String(reference.talkId)];
 const row=original(proof.preservedSource);
 return {...row,deepReference:reference,deepKoreanProof:proof,isChoice:['NON_SPOKEN_OPTION_REFERENCE','NATIVE_CHOICE'].includes(reference.role),url:'대사/'+path.basename(proof.preservedSource.file,'.json')+'.html#talk-'+reference.talkId};
});
// Existing catalogue positions remain stable; closed append-only deltas follow them.
const appendedChoiceScenes=(deepTimeline.evidence.nativeChoiceDeltas||[]).reduce((n:number,d:any)=>n+d.scenes,0);
const retainedSceneCount=deepTimeline.scenes.length-appendedChoiceScenes;
const retainedChoices=(deepTimeline.evidence.nativeChoiceDeltas||[]).filter((d:any)=>d.cohortSha256===freshTimeline.evidence.frozenCohortSha256).reduce((n:number,d:any)=>n+d.scenes,0);
const retainedFreshScenes=freshTimeline.counts.sceneCount;
const freshScenes=freshTimeline.scenes.map((scene:any)=>({...scene,kind:'FRESH_NATIVE_TIMELINE'}));
export const deepScenes=[...deepTimeline.scenes.slice(0,retainedSceneCount),...sdfTimeline.scenes,...deepTimeline.scenes.slice(retainedSceneCount,retainedSceneCount+retainedChoices),...luaTimeline.scenes,...freshScenes.slice(0,retainedFreshScenes),...snapshotTimeline.scenes.map((scene:any)=>({...scene,kind:'PUBLIC_JSON_TIMELINE'})),...deepTimeline.scenes.slice(retainedSceneCount+retainedChoices),...freshScenes.slice(retainedFreshScenes)];
export const deepCounts={scenes:deepScenes.length,rows:deepScenes.reduce((n:number,scene:any)=>n+timelineRows(scene).length,0)};
export const deepMissionScenes=new Map<string,any[]>();
for(const scene of deepScenes)for(const mission of new Set(scene.owners.map(owner=>owner.canonicalMission))){const list=deepMissionScenes.get(mission)||[];list.push(scene);deepMissionScenes.set(mission,list);}
export {deepTimeline,luaTimeline,freshTimeline,snapshotTimeline,attribution as deepAttribution};
