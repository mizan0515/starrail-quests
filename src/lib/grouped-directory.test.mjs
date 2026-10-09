import test from 'node:test';
import assert from 'node:assert/strict';
import {renderDirectoryGroup} from './grouped-directory.mjs';

test('large groups retain every subject once across CVA batch boundaries',()=>{
 const items=Array.from({length:73},(_,i)=>({id:'record-'+i,name:'원문 '+i,summary:'독립 구절 '+i,searchText:'전체 본문 '+i,axis:i%2?'person':'concept',kind:'원문',url:'/starrail-quests/문서/source-'+i+'.html'}));
 const html=renderDirectoryGroup(items,'records','test','concept');
 for(const [i,item] of items.entries()){
  assert.equal(html.split(`data-directory-entry="${item.id}"`).length-1,1);
  assert.equal(html.split(`id="test-entry-${item.id}"`).length-1,1);
  assert.match(html,new RegExp(`data-directory-entry="${item.id}"[^>]*data-directory-search="원문 ${i} 원문 전체 본문 ${i}"${i%2?' hidden':''}>`));
 }
 assert.equal((html.match(/data-directory-entry=/g)||[]).length,73);
 assert.equal((html.match(/<h4 class="cva-item-title">/g)||[]).length,73);
});
test('directory identities are unique and source strings remain escaped',()=>{
 const item={id:'source',name:'<b>원문</b>',summary:'A & B',url:'/starrail-quests/문서/source.html'};
 assert.match(renderDirectoryGroup([item],'all','scope'),/&lt;b&gt;원문&lt;\/b&gt;/);
 assert.throws(()=>renderDirectoryGroup([item,item],'all','scope'),/Invalid directory subject/);
 assert.throws(()=>renderDirectoryGroup([{...item,url:''}],'all','scope'),/Invalid directory subject/);
});
