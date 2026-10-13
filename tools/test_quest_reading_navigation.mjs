import assert from 'node:assert/strict';
import test from 'node:test';
import {deepScenes,timelineRows} from '../src/lib/deep-timeline.ts';
import {readingSources,questReadingSources,readingSourceRoute,nearbyReadingSources,readingRoleSummary} from '../src/lib/quest-reading-sources.ts';
import {safeReadingReturn,sourceReadingOrigin} from '../src/lib/reading-return.mjs';

test('metadata preserves every original scene URL and its exact explicit owner set',()=>{
 assert.equal(readingSources.length,deepScenes.length+1);
 for(let i=0;i<deepScenes.length;i++){
  const scene=deepScenes[i],source=readingSources[i];
  assert.equal(source.id,scene.id);assert.equal(source.url,'대화/연출-'+scene.id+'.html');
  assert.deepEqual(source.missions,[...new Set(scene.owners.map(o=>o.canonicalMission))]);
  assert.equal(source.occurrences,timelineRows(scene).length);
 }
});
test('all 840 separately stored option references contribute to accurate source counts',()=>{
 let additional=0;
 for(const scene of deepScenes.filter(s=>s.optionReferences)){
  const source=readingSources.find(r=>r.id===scene.id);
  assert.equal(source.occurrences,scene.rows.length+scene.optionReferences.length);
  additional+=source.occurrences-scene.rows.length;
 }
 assert.equal(additional,840);
});
test('four option-only sources each display one choice reference rather than zero',()=>{
 for(const id of ['fresh-timeline-23e2ed7a0fb2136a1e39','fresh-timeline-26b4fe9268524d79a7af','snapshot-timeline-15220f00c4dcd1e59200','snapshot-timeline-4445bcb7cbae1a36ba9e']){
  const source=readingSources.find(r=>r.id===id);assert.equal(source.occurrences,1);assert.equal(readingRoleSummary(source),'선택지 참조 1');
 }
});
test('old per-quest source catalogue remains the complete prefix, with version comparison appended',()=>{
 for(const mission of new Set(readingSources.flatMap(r=>r.missions))){
  const originals=deepScenes.filter(s=>s.owners.some(o=>o.canonicalMission===mission)).map(s=>s.id);
  assert.deepEqual(questReadingSources(mission).slice(0,originals.length).map(r=>r.id),originals);
 }
 const version=questReadingSources('quest-2021901').at(-1);
 assert.equal(version.id,'versioned-talk-202196417');assert.equal(version.roles.VERSION_COMPARISON_REFERENCE,2);
 assert.deepEqual(version.missions,['quest-2021901']);
});
test('79 ownerless sources remain globally addressable without invented quest associations',()=>{
 const orphan=readingSources.filter(r=>!r.missions.length);assert.equal(orphan.length,79);
 for(const source of orphan)assert.deepEqual(readingSourceRoute('/'+source.url).missions,[]);
 assert.equal(questReadingSources('quest-999999999').length,0);
 assert.deepEqual(readingSourceRoute('/대화/범위-range-0123456789abcdef.html').missions,[]);
 assert.deepEqual(readingSourceRoute('/대화/context-0123456789abcdef.html').missions,[]);
 assert.equal(readingSourceRoute('/대화/연출-timeline-0123456789abcdef.html'),null);
});
test('screen sources retain their screen role and do not add spoken counts',()=>{
 for(let i=0;i<deepScenes.length;i++)if(['HASH_ONLY_SCREEN_TEXT','LUA_ARGUMENT_SCREEN_TEXT'].includes(deepScenes[i].kind)){
  assert.equal(readingSources[i].roles.SCREEN_TEXT,deepScenes[i].rows.length);assert.equal(readingSources[i].roles.SPOKEN,undefined);
 }
});
test('bounded neighbouring links include the current source while complete quest metadata remains available',()=>{
 const sources=questReadingSources('quest-2021901');assert.equal(sources.length,143);
 for(const source of sources){const nearby=nearbyReadingSources(sources,source.url);assert.ok(nearby.length<=8);assert.ok(nearby.includes(source));}
 assert.equal(questReadingSources('quest-1054403').length,56);
 assert.equal(questReadingSources('quest-8016202').length,11);
});
test('version and range original anchors retain a validated quest return without chains',()=>{
 const options={origin:'https://example.test',base:'/starrail-quests'};
 const quest='/starrail-quests/문서/quest-2021901.html?speaker=운리#reading-link-4';
 for(const route of ['/대화/판본-202196417.html#talk-202196417-previous','/대화/판본-202196417.html#talk-202196417-current','/대화/범위-range-0123456789abcdef.html#talk-202196417']){
  const current='/starrail-quests'+route;
  assert.equal(decodeURI(safeReadingReturn(current,options)),current);
  assert.equal(decodeURI(sourceReadingOrigin(current,quest,options)),quest);
 }
 for(const invalid of ['https://outside.test/starrail-quests/문서/quest-2021901.html','/starrail-quests/문서/../문서/quest-2021901.html','/starrail-quests/문서%2fquest-2021901.html'])assert.equal(safeReadingReturn(invalid,options),null);
});
