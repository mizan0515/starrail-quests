import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import test from 'node:test';
import {deepScenes,deepCounts,timelineRows} from '../src/lib/deep-timeline.ts';

// Complete previously published catalogue, including snapshot and Lua readers.
const baselineCount=15267;
const baselineHash='80b6b7f31072ed8f0f153c4ee796811c762e4fe46726fbd4092e6bfc28444b05';
function checkPrefix(scenes){
  assert.equal(createHash('sha256').update(JSON.stringify(scenes.slice(0,baselineCount).map(s=>s.id))).digest('hex'),baselineHash);
}
test('all previous catalogue pages and return positions retain their sequence',()=>checkPrefix(deepScenes));
test('an insertion ahead of previously published readers is rejected',()=>{
  const moved=[deepScenes.at(-1),...deepScenes.slice(0,-1)];
  assert.throws(()=>checkPrefix(moved));
});
test('reader total includes the new clips and choice occurrences',()=>{
  const occurrences=deepScenes.flatMap(timelineRows);
  assert.equal(deepCounts.rows,occurrences.length);
  assert.equal(deepCounts.scenes,deepScenes.length);
  assert.ok(deepScenes.length>baselineCount);
  assert.ok(occurrences.some(row=>row.talkId===154030602&&row.role==='NATIVE_CHOICE'));
  assert.ok(occurrences.some(row=>row.talkId===155242001&&row.role==='SCREEN_TEXT'));
});
