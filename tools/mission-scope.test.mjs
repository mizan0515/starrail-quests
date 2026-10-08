import test from 'node:test';
import assert from 'node:assert/strict';
import {partitionMissionSections,missionRowLinked} from '../src/lib/mission-scope.mjs';
test('a shared task scope preserves excluded original rows and their original deep links',()=>{
 const rows=[{talk_id:1,text:'인사말'},{talk_id:2,text:'임무 대사'},{talk_id:3,text:'다른 분기의 대사'}];
 const sections=[{source:'NPC.json',anchor:'scene-1',rows}],before=JSON.stringify(sections);
 const coverage={sourceOwnership:{'NPC.json':[{kind:'EXPLICIT_MAIN_MISSION_ID'}]},sourceTalkScopes:{'NPC.json':{talkIds:[2],pointers:['/TaskList/1']}}};
 const {primary,reference}=partitionMissionSections(sections,coverage);
 assert.equal(primary.length,1);assert.equal(reference.length,1);
 assert.deepEqual(primary[0].rows.map(r=>r.text),['임무 대사']);
 assert.deepEqual(reference[0].rows.map(r=>r.text),['인사말','다른 분기의 대사']);
 assert.deepEqual([...primary[0].rows,...reference[0].rows].map(r=>r.readerRowAnchor).sort(),['scene-1-row-1','scene-1-row-2','scene-1-row-3']);
 assert.equal(reference[0].anchor,'scene-1-reference');assert.equal(JSON.stringify(sections),before);
 assert.deepEqual(reference[0].talkScope,coverage.sourceTalkScopes['NPC.json']);
});
test('scope IDs alone cannot promote a foreign or directory-only source',()=>{
 const section={source:'shared.json',rows:[{talk_id:2,text:'원문'}]};
 assert.equal(missionRowLinked(section,section.rows[0],{sourceTalkScopes:{'shared.json':{talkIds:[2]}}}),false);
 assert.equal(missionRowLinked(section,section.rows[0],{sourceOwnership:{'shared.json':[{kind:'MISSION_DIRECTORY_CONVENTION'}]},sourceTalkScopes:{'shared.json':{talkIds:[2]}}}),false);
});
test('removing or aliasing a required shared-file scope fails before publishing',()=>{
 const section={source:'shared.json',rows:[{talk_id:2,text:'임무 대사'}]};
 const coverage={sourceOwnership:{'shared.json':[{kind:'EXPLICIT_MAIN_MISSION_ID'},{kind:'EXPLICIT_SUBMISSION_FINISH_SCOPE',target:'shared.json'}]},sourceTalkScopes:{'wrong-path.json':{talkIds:[2]}}};
 assert.throws(()=>missionRowLinked(section,section.rows[0],coverage),/Missing proved dialogue scope/);
 coverage.sourceOwnership['shared.json'].push({kind:'EXPLICIT_JSON_PATH'});
 assert.throws(()=>missionRowLinked(section,section.rows[0],coverage),/Missing proved dialogue scope/);
 coverage.sourceTalkScopes['shared.json']={talkIds:[2]};
 assert.equal(missionRowLinked(section,section.rows[0],coverage),true);
});
test('a fully owned source and explicit message proof preserve all original rows',()=>{
 const section={source:'all.json',anchor:'all',rows:[{talk_id:2,text:'첫 줄'},{text:'기록'}]};
 const coverage={sourceOwnership:{'all.json':[{kind:'EXPLICIT_MAIN_MISSION_ID'}]}};
 const full=partitionMissionSections([section],coverage);assert.equal(full.primary[0].rows.length,2);assert.equal(full.reference.length,0);
 const message={...section,relatedDocument:{ownership:[{kind:'EXPLICIT_MAIN_MISSION_ID'}]}};
 assert.equal(missionRowLinked(message,message.rows[1],{sourceTalkScopes:{'all.json':{talkIds:[2]}}}),true);
});
test('a scoped parent proves its explicit child path without imposing the parent talk IDs on the child',()=>{
 const section={source:'Act.json',rows:[{talk_id:99,text:'명시적으로 호출한 연출의 원문'}]};
 const coverage={sourceOwnership:{'Act.json':[{kind:'EXPLICIT_MAIN_MISSION_ID'},{kind:'EXPLICIT_SUBMISSION_FINISH_SCOPE',target:'NPC.json'},{kind:'EXPLICIT_JSON_PATH',target:'Act.json'}]},sourceTalkScopes:{'NPC.json':{talkIds:[2]}}};
 assert.equal(missionRowLinked(section,section.rows[0],coverage),true);
});
