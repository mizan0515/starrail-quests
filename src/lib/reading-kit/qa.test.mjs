import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createReadingGraph} from './graph.mjs';
import {writeReadingGraph} from './write.mjs';
import {verifyGraphDirectory} from './qa.mjs';
test('sharded sources retain evidence hashes and QA rejects a broken source index',async()=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'reading-qa-'));
 try {
  const g=createReadingGraph({game:'test',sources:[{id:'source',title:'원문',url:'/source',blocks:[{id:'row',text:'원문의 구절',url:'/source#row'}]}],entities:[{id:'entity',name:'대상',url:'/entity'}]});
  const claim=g.claim('서술',[{sourceId:'source',quote:'원문의 구절'}]);
  await writeReadingGraph(g.output({clusters:[{id:'cluster',entityId:'entity',sections:[{id:'overview',claimIds:[claim]}]}]}),directory);
  assert.equal(verifyGraphDirectory(directory).blocks,1);
  const file=path.join(directory,'graph.json'),graph=JSON.parse(await fs.readFile(file,'utf8'));
  graph.evidence[0].sourceSha256='0'.repeat(64);
  await fs.writeFile(file,JSON.stringify(graph));
  assert.throws(()=>verifyGraphDirectory(directory));
 } finally {await fs.rm(directory,{recursive:true,force:true});}
});
