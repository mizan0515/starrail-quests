import test from 'node:test';
import assert from 'node:assert/strict';
import {relationConnector} from './relation-layout.mjs';
const rect=(left,top,width,height)=>({left,top,width,height,right:left+width,bottom:top+height});
const endpoints=p=>{const values=p.match(/-?\d+(?:\.\d+)?/g).map(Number);return {start:values.slice(0,2),end:values.slice(-2)};};
test('incoming actor connects from its actual card edge to the focus, including unequal heights',()=>{
 const focus=rect(330,190,150,110),card=rect(0,0,300,170);
 assert.deepEqual(endpoints(relationConnector({focus,card,direction:'incoming'})),{start:[302,85],end:[328,245]});
});
test('outgoing action connects from the focus to the actual target edge',()=>{
 const focus=rect(330,190,150,110),card=rect(510,280,300,240);
 assert.deepEqual(endpoints(relationConnector({focus,card,direction:'outgoing'})),{start:[482,245],end:[508,400]});
});
test('IDs choose direction independently of the geometric side of a node',()=>{
 const focus=rect(330,190,150,110),card=rect(0,0,300,170);
 assert.deepEqual(endpoints(relationConnector({focus,card,direction:'outgoing'})),{start:[328,245],end:[302,85]});
});
test('fan ports connect only the measured parent and direct child, with reversible direction',()=>{
 const focus=rect(180,0,200,100),card=rect(0,150,240,160);
 assert.deepEqual(endpoints(relationConnector({focus,card,direction:'outgoing',layout:'fan'})),{start:[280,102],end:[120,148]});
 assert.deepEqual(endpoints(relationConnector({focus,card,direction:'incoming',layout:'fan'})),{start:[120,148],end:[280,102]});
});
test('hidden, overlapping, unsupported and incomplete geometry draws no invented connector',()=>{
 const focus=rect(100,100,100,100);
 for(const card of [rect(0,0,0,100),rect(150,150,100,100),{left:0},null])assert.equal(relationConnector({focus,card,direction:'incoming'}),null);
 assert.equal(relationConnector({focus,card:rect(300,0,100,100),direction:'unknown'}),null);
 assert.equal(relationConnector({focus,card:rect(0,90,100,100),direction:'outgoing',layout:'fan'}),null);
});
