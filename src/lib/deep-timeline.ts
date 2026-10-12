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
export const deepScenes=[...deepTimeline.scenes.slice(0,retainedSceneCount),...sdfTimeline.scenes,...deepTimeline.scenes.slice(retainedSceneCount),...luaTimeline.scenes,...freshTimeline.scenes.map((scene:any)=>({...scene,kind:'FRESH_NATIVE_TIMELINE'})),...snapshotTimeline.scenes.map((scene:any)=>({...scene,kind:'PUBLIC_JSON_TIMELINE'}))];
export const deepCounts={scenes:deepScenes.length,rows:deepTimeline.counts.rows+sdfTimeline.counts.rows+luaTimeline.counts.rows+freshTimeline.counts.occurrences.included_SPOKEN+freshTimeline.counts.occurrences.included_SCREEN_TEXT+freshTimeline.counts.occurrences.included_NON_SPOKEN_OPTION_REFERENCE+snapshotTimeline.counts.occurrences.included_SPOKEN+snapshotTimeline.counts.occurrences.included_SCREEN_TEXT+snapshotTimeline.counts.occurrences.included_NON_SPOKEN_OPTION_REFERENCE};
export const deepMissionScenes=new Map<string,any[]>();
for(const scene of deepScenes)for(const mission of new Set(scene.owners.map(owner=>owner.canonicalMission))){const list=deepMissionScenes.get(mission)||[];list.push(scene);deepMissionScenes.set(mission,list);}
export {deepTimeline,luaTimeline,freshTimeline,snapshotTimeline,attribution as deepAttribution};
