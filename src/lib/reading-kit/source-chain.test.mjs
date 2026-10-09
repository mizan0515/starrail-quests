import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceRelationHubs,renderTopology} from './topology.mjs';
import {escapeHtml} from './render.mjs';
test('conditional source chains use direct pairs and retain possibility without chronology or a return',()=>{
 const nodes=['origin','forms','union'].map(id=>({id,name:id,layer:0})),edges=[{id:'split',from:'origin',to:'forms',label:'분화한다',claimId:'split-proof',kind:'relation',claimKind:'explicit',evidence:[]},{id:'union',from:'forms',to:'union',label:'합쳐질 수도 있다',claimId:'union-proof',kind:'relation',claimKind:'explicit',evidence:[]}];
 assert.deepEqual(sourceRelationHubs(nodes,edges).map(g=>g.parent),['origin','forms']);
 const html=renderTopology({id:'conditional-forms',title:'나뉜 의식',nodes,edges},{escape:escapeHtml,href:escapeHtml,inline:escapeHtml,evidence:()=>''});
 assert.equal((html.match(/data-hub-shape="pair"/g)||[]).length,2);assert.ok(html.includes('합쳐질 수도 있다'));assert.ok(!html.includes('data-process-kind='));assert.ok(!html.includes('원문에 명시된 과정의 순서'));assert.ok(!html.includes('rw-process-return'));
});
