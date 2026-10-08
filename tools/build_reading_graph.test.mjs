import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {relationEndpoints,claimAttribution} from './build_reading_graph.mjs';
const atlas=JSON.parse(fs.readFileSync(new URL('../editorial/context-atlas.json',import.meta.url),'utf8'));
test('incoming has the actual actor on the left while the reading context stays the destination',()=>{
 for(const [id,index,actor] of [['swarm-research',1,'ruan-mei'],['swarm-research',2,'person-1013'],['unknowable-research',1,'person-1013']]){
  const relation=atlas.nodes.find(n=>n.id===id).links[index];
  assert.equal(relation.direction,'incoming');
  assert.deepEqual(relationEndpoints(id,relation),{from:actor,to:id});
  assert.equal(claimAttribution(relation,[relation.evidence]).kind,'attributed');
 }
});
test('all 65 reviewed source/target pairs have an explicit supported direction',()=>{
 const links=atlas.nodes.flatMap(n=>n.links.map(r=>[n.id,r]));assert.equal(links.length,65);
 for(const [id,r] of links){assert.ok(['incoming','outgoing'].includes(r.direction));const pair=relationEndpoints(id,r);
  assert.deepEqual(new Set([pair.from,pair.to]),new Set([id,r.target]));
  assert.deepEqual(pair,r.direction==='incoming'?{from:r.target,to:id}:{from:id,to:r.target});}
});
test('outgoing remains the compatible default and nominal membership keeps its endpoints',()=>{
 assert.deepEqual(relationEndpoints('ipc',{target:'aeon-aeon-1'}),{from:'ipc',to:'aeon-aeon-1'});
 const n=atlas.nodes.find(n=>n.id==='genius-society');assert.deepEqual(relationEndpoints(n.id,n.links[0]),{from:n.id,to:'lore-10222'});
});
test('unknown directions and malformed endpoints stop before graph generation',()=>{
 for(const relation of [{direction:'sideways',target:'herta'},{direction:'Incoming',target:'herta'},{direction:'incoming',target:''},{direction:'incoming',target:'context'}])assert.throws(()=>relationEndpoints('context',relation));
});

test('the two Abundance definitions remain an editorial connection, with no inferred membership',()=>{
 const relation=atlas.nodes.find(n=>n.id==='sanctus-medicus').links[1];
 assert.equal(relation.verb,'풍요의 백성의 정의와 함께 읽는다');
 assert.equal(claimAttribution(relation,[relation.evidence]).kind,'inference');
 assert.deepEqual(relationEndpoints('sanctus-medicus',relation),{from:'sanctus-medicus',to:'lore-10054'});
});
