import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {relationEndpoints,claimAttribution} from './build_reading_graph.mjs';
import {atlasComparison,comparisonReaderNode} from '../src/lib/atlas-comparison.mjs';
const atlas=JSON.parse(fs.readFileSync(new URL('../editorial/context-atlas.json',import.meta.url),'utf8'));
test('Preservation uses its own definition and records instead of a homonymous memory policy',()=>{
 const node=atlas.nodes.find(n=>n.id==='preservation');
 const comparison=atlasComparison(atlas,node);
 assert.deepEqual(comparison.panels.map(p=>p.evidence.id),['lore-10008','book-46','book-245']);
 assert.notEqual(comparison,atlas.comparisons['paths-and-factions']);
 for(const panel of comparison.panels)assert.equal(panel.text,panel.evidence.quote);
});
test('all individual comparisons have an explicit owner and missing selections stop generation',()=>{
 for(const node of atlas.nodes){
  assert.ok(Boolean(node.comparison)!==Boolean(node.comparisonTopic),node.id);
  const comparison=atlasComparison(atlas,node);
  assert.equal(comparison,node.comparison||atlas.comparisons[node.comparisonTopic]);
 }
 assert.throws(()=>atlasComparison(atlas,{id:'new-reader',topic:'paths-and-factions'}),/Unspecified comparison scope/);
});
test('broad essays keep their reviewed comparison after a first reader overrides it',()=>{
 for(const topic of Object.keys(atlas.comparisons)){
  const owner=comparisonReaderNode(atlas,null,topic);
  assert.equal(owner.comparisonTopic,topic);
  assert.equal(atlasComparison(atlas,owner),atlas.comparisons[topic]);
 }
 assert.notEqual(comparisonReaderNode(atlas,null,'paths-and-factions').id,'preservation');
});
test('incoming has the actual actor on the left while the reading context stays the destination',()=>{
 for(const [id,index,actor] of [['swarm-research',1,'ruan-mei'],['swarm-research',2,'person-1013'],['unknowable-research',1,'person-1013'],['ruan-mei',0,'person-1013'],['stellaron-hunters',0,'person-1005'],['stellaron-hunters',3,'lore-10021'],['stellaron-hunters',4,'lore-10022'],['stellaron-hunters',5,'lore-10023'],['stellaron-hunters',6,'lore-20025'],['stellaron-hunters',7,'lore-10151'],['genius-society',0,'lore-10222'],['memory-garden',0,'aeon-aeon-2'],['cremators',1,'memory-garden'],['mourning-actors',0,'aeon-aeon-7']]){
  const relation=atlas.nodes.find(n=>n.id===id).links[index];
  assert.equal(relation.direction,'incoming');
  assert.deepEqual(relationEndpoints(id,relation),{from:actor,to:id});
  assert.equal(claimAttribution(relation,[relation.evidence]).kind,['swarm-research','unknowable-research','memory-garden','cremators','mourning-actors'].includes(id)?'attributed':'explicit');
 }
});
test('all 86 reviewed source/target pairs have an explicit supported direction',()=>{
 const links=atlas.nodes.flatMap(n=>n.links.map(r=>[n.id,r]));assert.equal(links.length,86);
 for(const [id,r] of links){assert.ok(['incoming','outgoing'].includes(r.direction));const pair=relationEndpoints(id,r);
  assert.deepEqual(new Set([pair.from,pair.to]),new Set([id,r.target]));
  assert.deepEqual(pair,r.direction==='incoming'?{from:r.target,to:id}:{from:id,to:r.target});}
});
test('outgoing remains the compatible default and membership names the actual member first',()=>{
 assert.deepEqual(relationEndpoints('ipc',{target:'aeon-aeon-1'}),{from:'ipc',to:'aeon-aeon-1'});
 const n=atlas.nodes.find(n=>n.id==='genius-society');assert.deepEqual(relationEndpoints(n.id,n.links[0]),{from:'lore-10222',to:n.id});
});
test('unknown directions and malformed endpoints stop before graph generation',()=>{
 for(const relation of [{direction:'sideways',target:'herta'},{direction:'Incoming',target:'herta'},{direction:'incoming',target:''},{direction:'incoming',target:'context'}])assert.throws(()=>relationEndpoints('context',relation));
});

test('the two Abundance definitions remain an editorial connection, with no inferred membership',()=>{
 const relation=atlas.nodes.find(n=>n.id==='sanctus-medicus').links[1];
 assert.equal(relation.verb,'풍요의 백성의 축복·육체 설명');
 assert.equal(claimAttribution(relation,[relation.evidence]).kind,'inference');
 assert.deepEqual(relationEndpoints('sanctus-medicus',relation),{from:'sanctus-medicus',to:'lore-10054'});
});

test('station reader navigation stays editorial while the personal invitation names Herta',()=>{
 const station=atlas.nodes.find(n=>n.id==='herta').links[0];
 const invitation=atlas.nodes.find(n=>n.id==='ruan-mei').links[0];
 assert.equal(claimAttribution(station,[station.evidence]).kind,'inference');
 assert.deepEqual(relationEndpoints('ruan-mei',invitation),{from:'person-1013',to:'ruan-mei'});
 assert.match(invitation.evidence.quote,/헤르타의 초청을 받아/);
});
test('all reviewed editorial connections remain separate from settings facts and attributed statements',()=>{
 const connections=atlas.nodes.flatMap(n=>n.links).filter(r=>r.status.includes('편집'));
 assert.equal(connections.length,45);
 for(const relation of connections)assert.equal(claimAttribution(relation,[relation.evidence]).kind,'inference');
 const forecast=atlas.nodes.find(n=>n.id==='stellaron-hunters').links[2];
 assert.equal(claimAttribution(forecast,[forecast.evidence]).kind,'inference');
 const guidance=atlas.nodes.find(n=>n.id==='stellaron-hunters').links[1];
 assert.equal(claimAttribution(guidance,[guidance.evidence]).kind,'attributed');
});

test('editorial labels identify the specific records and do not describe editor navigation',()=>{
 const life=atlas.nodes.find(n=>n.id==='herta').links[1];
 assert.equal(life.verb,'창조물의 소멸과 감정 연구 기록');
 assert.equal(claimAttribution(life,[life.evidence]).kind,'inference');
 for(const relation of atlas.nodes.flatMap(n=>n.links).filter(r=>r.status.includes('편집')))
  assert.doesNotMatch(relation.verb,/좁혀 읽|다시 묻|서로 다른 능력|실험 성과와 감정의 간격/);
});
